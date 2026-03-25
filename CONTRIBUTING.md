Contribution Guidelines

Contributions are welcome.

Requirements:
	•	Valid MusicBrainz recording MBID
	•	Public YouTube video identifier
	•	Confidence at or above the repository publish floor in `.github/publish_policy.json`
	•	Transport mapping data only (do not submit MusicBrainz metadata copies)

Preferred sources:
	•	Official artist uploads
	•	Label uploads
	•	Deterministically verified Retreivr matches

Avoid:
	•	Unofficial uploads when better verified sources exist
	•	Private videos
	•	Geo-blocked or unstable media
	•	Manual edits that bypass schema or CI policy

Preferred automated flow:
	•	Retreivr writes dataset updates to a trusted branch
	•	A same-repo PR is opened
	•	CI validates schema and policy gates
	•	Trusted PR auto-merge handles publication to `main`
