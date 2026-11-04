# Map and review records

Map JSON uses `schema_version: 2`. `screens` are visible-page candidates with `components`, `layouts`, and `elements`. `transitions` are action paths with `from`, `to`, `action`, `trigger`, `verification`, and source `evidence`. `containments` describe parent/child hosting.

A launcher `activity-alias` marks its target Activity as an entry screen and is recorded in `entry_aliases` with `entry_evidence`. The alias is not an extra screen or a navigable edge. Literally disabled aliases are excluded from entry inference; runtime component enablement can still differ from the manifest.

`trigger.status` has three values: `resolved`, `event_only`, `unknown`. `trigger_id`, when present, can be matched to an element ID on the source screen. `verification=source_rule` or `decompiled_rule` indicates how Fast inferred a relationship; it is not runtime confirmation.

The standalone `map.html` stores human review locally in the browser, keyed by a fingerprint of the exact map. Exported review JSON has `schema_version: 1`, project name, optional source commit, `map_fingerprint`, export time, and a `reviews` object keyed by transition ID. Each entry may contain `status` (`unreviewed`, `confirmed`, `questionable`, `incorrect`), a free-text `note`, and `updated_at`. Keep this export beside the source map; do not merge subjective review status into the static evidence without an explicit reconciliation step.
