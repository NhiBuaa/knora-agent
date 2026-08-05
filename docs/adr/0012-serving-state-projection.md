# Separate ingestion lifecycle from retrieval serving state

Status: accepted

Milestone 2 job status exposes target, current and nullable served Document Version IDs plus a
server-computed `serving_state` of `unavailable`, `current` or `previous`. All pointers are
resolved from one database snapshot so concurrent upload/activation cannot produce a contradictory
response. `job.status` remains the ingestion lifecycle; serving state describes retrieval only and
will later be reusable in a Document detail/status projection.
