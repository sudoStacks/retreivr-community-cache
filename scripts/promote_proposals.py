#!/usr/bin/env python3
"""Promote proposal JSONL records into sharded dataset files."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_ROOT = ROOT / "youtube" / "recording"
SCHEMA_PATH = ROOT / "schema" / "schema.json"
POLICY_PATH = ROOT / ".github" / "publish_policy.json"

MBID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass
class ProposalResult:
    status: str
    reason: str | None = None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _schema_version() -> int:
    try:
        schema = _load_json(SCHEMA_PATH)
    except Exception:
        return 1
    value = schema.get("properties", {}).get("schema_version", {}).get("const")
    return value if isinstance(value, int) else 1


def _publish_policy() -> dict[str, Any]:
    try:
        raw = _load_json(POLICY_PATH)
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return raw


def _min_confidence() -> float:
    try:
        return float(_publish_policy().get("minimum_confidence", 0.0))
    except Exception:
        return 0.0


def _allowed_sources() -> set[str]:
    policy = _publish_policy()
    values = policy.get("allowed_sources")
    if isinstance(values, list):
        normalized = {str(item).strip() for item in values if str(item).strip()}
        if normalized:
            return normalized
    return {"youtube"}


def _is_valid_datetime(value: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def _target_path(recording_mbid: str) -> Path:
    mbid = recording_mbid.lower()
    return YOUTUBE_ROOT / mbid[:2] / f"{mbid}.json"


def _source_sort_key(source: dict[str, Any]) -> tuple[float, str]:
    return (-float(source.get("confidence") or 0.0), str(source.get("video_id") or ""))


def _normalize_proposal_source(value: Any) -> str:
    source = str(value or "youtube").strip().lower()
    if source == "youtube_music":
        return "youtube"
    return source


def _validate_proposal(record: Any) -> tuple[bool, str | None]:
    if not isinstance(record, dict):
        return False, "not_object"

    mbid = record.get("recording_mbid")
    if not isinstance(mbid, str) or not MBID_RE.fullmatch(mbid):
        return False, "invalid_recording_mbid"

    source = _normalize_proposal_source(record.get("source"))
    if source not in _allowed_sources():
        return False, "invalid_source"

    video_id = record.get("video_id")
    if not isinstance(video_id, str) or not VIDEO_ID_RE.fullmatch(video_id):
        return False, "invalid_video_id"

    candidate_url = record.get("candidate_url")
    if not isinstance(candidate_url, str) or not candidate_url.strip():
        return False, "missing_candidate_url"

    try:
        confidence = float(record.get("selected_score"))
    except (TypeError, ValueError):
        return False, "invalid_selected_score"
    if confidence < _min_confidence() or confidence > 1:
        return False, "score_below_policy"

    emitted_at = record.get("emitted_at")
    if not isinstance(emitted_at, str) or not _is_valid_datetime(emitted_at):
        return False, "invalid_emitted_at"

    duration_ms = record.get("duration_ms")
    if duration_ms is not None:
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            return False, "invalid_duration_ms"
        if duration_ms <= 0 or duration_ms > 7_200_000:
            return False, "invalid_duration_ms"

    return True, None


def _normalize_new_source(proposal: dict[str, Any]) -> dict[str, Any]:
    duration_ms = proposal.get("duration_ms")
    return {
        "source": _normalize_proposal_source(proposal.get("source")),
        "video_id": proposal["video_id"],
        "duration_ms": int(duration_ms) if isinstance(duration_ms, int) else None,
        "candidate_url": str(proposal.get("candidate_url") or "").strip() or None,
        "candidate_id": str(proposal.get("candidate_id") or proposal["video_id"]).strip() or proposal["video_id"],
        "confidence": float(proposal["selected_score"]),
        "duration_delta_ms": (
            int(proposal["duration_delta_ms"])
            if isinstance(proposal.get("duration_delta_ms"), int)
            else None
        ),
        "retreivr_version": str(proposal.get("retreivr_version") or "").strip() or None,
        "last_verified_at": str(proposal["emitted_at"]).strip(),
        "verified_by": str(proposal.get("verified_by") or "retreivr").strip() or "retreivr",
    }


def _load_or_init_record(path: Path, recording_mbid: str) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {
            "schema_version": _schema_version(),
            "recording_mbid": recording_mbid,
            "updated_at": None,
            "sources": [],
        }, None

    try:
        record = _load_json(path)
    except Exception:
        return {}, "invalid_existing_json"

    if not isinstance(record, dict):
        return {}, "invalid_existing_record"
    if record.get("recording_mbid") != recording_mbid:
        return {}, "existing_mbid_mismatch"
    if not isinstance(record.get("sources"), list):
        return {}, "invalid_existing_sources"
    return record, None


def _merge_source(existing: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    merged = dict(existing)
    changed = False

    max_conf = max(float(existing.get("confidence") or 0.0), float(incoming.get("confidence") or 0.0))
    if float(merged.get("confidence") or 0.0) != max_conf:
        merged["confidence"] = max_conf
        changed = True

    incoming_verified = str(incoming.get("last_verified_at") or "")
    existing_verified = str(existing.get("last_verified_at") or "")
    max_verified = max(existing_verified, incoming_verified)
    if str(merged.get("last_verified_at") or "") != max_verified:
        merged["last_verified_at"] = max_verified
        changed = True

    for key in ("duration_ms", "candidate_url", "candidate_id", "duration_delta_ms", "retreivr_version", "verified_by"):
        incoming_value = incoming.get(key)
        if incoming_verified >= existing_verified and merged.get(key) != incoming_value and incoming_value is not None:
            merged[key] = incoming_value
            changed = True

    if merged.get("source") != incoming.get("source"):
        merged["source"] = incoming.get("source")
        changed = True

    return merged, changed


def _promote_one(proposal: dict[str, Any], dry_run: bool) -> ProposalResult:
    valid, reason = _validate_proposal(proposal)
    if not valid:
        return ProposalResult("skipped", reason=reason)

    recording_mbid = str(proposal["recording_mbid"]).lower()
    source = _normalize_new_source(proposal)
    recording_path = _target_path(recording_mbid)

    record, load_err = _load_or_init_record(recording_path, recording_mbid)
    if load_err is not None:
        return ProposalResult("skipped", reason=load_err)

    sources: list[dict[str, Any]] = record.get("sources", [])
    existing_idx = None
    for idx, item in enumerate(sources):
        if not isinstance(item, dict):
            return ProposalResult("skipped", reason="invalid_existing_source_entry")
        if item.get("video_id") == source["video_id"]:
            existing_idx = idx
            break

    record_changed = False
    status = "added"
    if existing_idx is None:
        sources.append(source)
        record_changed = True
    else:
        merged, updated = _merge_source(sources[existing_idx], source)
        if updated:
            sources[existing_idx] = merged
            record_changed = True
            status = "updated"

    sources.sort(key=_source_sort_key)
    emitted_at = str(proposal.get("emitted_at") or "").strip()
    if record.get("updated_at") != max(str(record.get("updated_at") or ""), emitted_at):
        record["updated_at"] = max(str(record.get("updated_at") or ""), emitted_at) or emitted_at
        record_changed = True
    record["recording_mbid"] = recording_mbid
    record["schema_version"] = _schema_version()
    record["sources"] = sources

    if not record_changed:
        return ProposalResult("skipped", reason="no_change")

    if existing_idx is not None:
        status = "updated"

    if not dry_run:
        _write_json_atomic(recording_path, record)

    return ProposalResult(status=status)


def _iter_jsonl(path: Path) -> tuple[int, dict[str, Any] | None, str | None]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception as exc:
            yield line_no, None, f"invalid_jsonl_line: {exc}"
            continue
        if not isinstance(value, dict):
            yield line_no, None, "invalid_jsonl_record_type"
            continue
        yield line_no, value, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote proposal JSONL records into sharded dataset records.")
    parser.add_argument("proposal_files", nargs="+", help="One or more proposal JSONL files.")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate proposals and print summary without writing files.")
    parser.add_argument(
        "--max-record-writes",
        type=int,
        default=None,
        help="Maximum number of unique recording files to modify in one run.",
    )
    args = parser.parse_args()

    added = 0
    updated = 0
    skipped = 0
    skipped_reasons: Counter[str] = Counter()
    touched_recordings: set[str] = set()

    for proposal_file in args.proposal_files:
        path = Path(proposal_file)
        if not path.exists() or not path.is_file():
            skipped += 1
            skipped_reasons["missing_input_file"] += 1
            print(f"[skip] {proposal_file}: missing input file")
            continue
        if path.suffix != ".jsonl":
            skipped += 1
            skipped_reasons["unsupported_input_format"] += 1
            print(f"[skip] {proposal_file}: expected .jsonl input")
            continue

        for line_no, proposal, parse_error in _iter_jsonl(path):
            if parse_error is not None:
                skipped += 1
                skipped_reasons[parse_error.split(":")[0]] += 1
                print(f"[skip] {proposal_file}:{line_no}: {parse_error}")
                continue

            assert proposal is not None
            mbid = proposal.get("recording_mbid")
            if (
                isinstance(args.max_record_writes, int)
                and args.max_record_writes >= 0
                and isinstance(mbid, str)
                and mbid.lower() not in touched_recordings
                and len(touched_recordings) >= args.max_record_writes
            ):
                skipped += 1
                skipped_reasons["batch_record_limit_reached"] += 1
                print(f"[skip] {proposal_file}:{line_no}: batch_record_limit_reached")
                continue

            result = _promote_one(proposal, dry_run=args.dry_run)
            if result.status == "added":
                added += 1
                if isinstance(mbid, str):
                    touched_recordings.add(mbid.lower())
            elif result.status == "updated":
                updated += 1
                if isinstance(mbid, str):
                    touched_recordings.add(mbid.lower())
            else:
                skipped += 1
                skipped_reasons[result.reason or "unknown"] += 1
                print(f"[skip] {proposal_file}:{line_no}: {result.reason}")

    print("")
    print("Promotion summary")
    print(f"- added: {added}")
    print(f"- updated: {updated}")
    print(f"- skipped: {skipped}")
    if skipped_reasons:
        print("- skipped_reasons:")
        for reason in sorted(skipped_reasons):
            print(f"  - {reason}: {skipped_reasons[reason]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
