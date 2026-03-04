# Retreivr Community Index

A community-maintained metadata index that maps canonical music recordings to publicly available media pages.

This dataset is designed to accelerate deterministic media acquisition in the Retreivr ecosystem while preserving canonical metadata authority.

The index contains **metadata references only** and does not host or distribute media files.

---

# Purpose

Retreivr resolves music recordings through MusicBrainz.  
Transport sources (such as YouTube) must then be discovered to acquire the media.

This repository allows the community to share verified mappings:

MusicBrainz Recording MBID
↓
Public media page identifier

These mappings dramatically reduce repeated search work across users.

---

# What This Repository Stores

The index stores **identifiers and metadata only**.

Examples:

- MusicBrainz recording MBID
- YouTube video ID
- Duration
- Confidence score
- Verification timestamp

Example mapping:
recording_mbid
→ youtube_video_id
→ duration_ms
→ confidence

The dataset **never stores media files or download links**.

---

# What This Repository Does NOT Store

This project intentionally avoids storing:

- Download URLs
- Streaming URLs
- Format URLs
- Cookies
- Authentication tokens
- Private media
- Scraped media files

Only identifiers referencing **public media pages** are permitted.

---

# Repository Structure
musicbrainz/
recording/
/
<recording_mbid>.json

youtube/
recording/
/
<recording_mbid>.json

Prefix directories are based on the first two characters of the MusicBrainz recording MBID.

Example:
musicbrainz/recording/4b/4b9d0f41.json
youtube/recording/4b/4b9d0f41.json

This sharding structure ensures the repository scales efficiently.

---

# Example Record
youtube/recording/4b/4b9d0f41.json

```json
{
  "recording_mbid": "4b9d0f41-3d5e-4649-8137-9a071f7e9667",
  "sources": [
    {
      "type": "youtube",
      "video_id": "dQw4w9WgXcQ",
      "duration_ms": 242000,
      "confidence": 0.97,
      "verified_at": "2026-03-03",
      "channel_type": "official"
    }
  ]
}
```

# How Retreivr Uses This Dataset

When resolving a recording:
	1.	Resolve canonical metadata via MusicBrainz
	2.	Check local cache
	3.	Query the community index
	4.	Use candidate sources as hints for deterministic scoring
	5.	If no match exists, run the normal resolver pipeline

Community entries never override canonical resolution.

They function only as accelerators.


Legal Notes

This repository stores metadata references only.

It does not host or distribute copyrighted material.

Entries reference publicly accessible media pages in the same way that:
	•	MusicBrainz catalogs recordings
	•	search engines index video pages

If a rightsholder requests removal of a mapping, the entry will be removed promptly.

⸻

# Schema

JSON schemas are provided in the /schema directory.

These define:
	•	allowed fields
	•	required metadata
	•	validation rules

Future schema updates will include versioning to maintain compatibility with existing clients.

# License

Dataset licensed under:
Open Data Commons Open Database License (ODbL)
This allows community use while ensuring improvements remain open.

⸻

# Relationship to Retreivr

Retreivr is a deterministic media ingestion engine that:
	•	resolves canonical metadata via MusicBrainz
	•	acquires media from public platforms
	•	produces clean, normalized media libraries

This dataset improves acquisition speed by sharing verified transport mappings.

More information:

https://github.com/sudostacks/retreivr

---

