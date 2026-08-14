# Semantic diff: issue-51-v10 → issue-51-v11

## Changed

- Adds exclusive sealed run ownership after corpus-closure PASS and before startup auth injection.
- While sealed, prohibits corpus/retrieval-provenance mutation while allowing Q&A and trace
  persistence. Failure to establish exclusive ownership blocks Q&A.
- Requires post-run closure, Binding V3 and resolved configuration verification. Drift invalidates
  the full run as quality evidence and prevents quality-score publication.
- States seal and post-run checking are outside the per-request end-to-end latency interval.

## Unchanged

- Pre-start credential lifecycle, Binding V3, canonical identity, metric/denominator, citation,
  semantic scorer, independent latency semantics and manual-acceptance status.
