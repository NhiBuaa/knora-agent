# Keep lexical derivation and serving authority in PostgreSQL

Status: accepted S2 design through Issue #153 and owner decisions Q1–Q19;
implementation and acceptance remain incomplete.

PDF extraction and lexical indexing are separate durable ingestion jobs. Extraction commits
the real Chunk Set/Chunks, desired generation and one index job in one transaction. Indexing
uses existing leases, retry/history and finalization fencing, and succeeds only after an exact
projection receipt and PostgreSQL CAS activation. Extraction success alone does not permit
serving. This preserves crash/replay handling without inventing an Embedding Set or coordinating
an atomic transaction across PostgreSQL and Qdrant.

Both new job kinds capture Document and Workspace revisions at enqueue. A changed snapshot,
including archive followed by unarchive, supersedes old work with `stale_derivation_snapshot`.
Reprocess `same_as_job` preserves the selected extraction kind/profile; BM25 `current` uses
the valid desired generation, including indexing B while A is active, and fails unavailable
if that desired configuration is invalid. It never falls back to A or implicitly switches
to dense. Internal index jobs are not external extraction commands.

Upload job identity/status, lexical indexing status and retrieval readiness are distinct.
Serving is computed for the selected retrieval strategy after valid activation. A lexical-only
document has no embedding readiness, and BM25 operator provenance has nullable dense fields.
Dense defaults and existing dense reader semantics remain compatible.

Owner Q15 exposes read-only derivation kind for document/job status. Failed lexical extraction
before a desired generation retries `same_as_job` with the exact extraction job/profile; with
a desired generation it uses `current` under Q7. A new failed extraction without a child does
not imply that an older desired generation is absent. Public projection must distinguish these
states explicitly. Dense list/detail retry behavior remains compatible.

Before generation, revalidate the lexical generation/version/profile/revisions. Revalidate
again in the trace persistence transaction before returning citations. Invalidated authority
raises `LEXICAL_RETRIEVAL_UNAVAILABLE`; it is never an empty-evidence observation. No database
transaction or lock spans generation. Classified Qdrant transport/timeout/408/429/5xx failures
reuse `STORAGE_TRANSIENT`; malformed receipt/profile/configuration failures are terminal
configuration failures. PostgreSQL indeterminate coordination semantics remain unchanged.

One native query returns at most 200 hits. Below 200, the response is complete and ties
use score descending then canonical chunk ID ascending. At exactly 200, preserve native
order and record the tie boundary as unknown. Primary Top8 comes from that same ranked
window; revalidation never refills it or issues another query. Smaller adapter windows,
when used outside this primary path, must use their actual requested limit for completeness.

An index job has an explicit `parent_ingestion_job_id` linking its extraction job; extraction
creates it atomically. Public indexing projection follows that link rather than guessing
from generation identity or creation time. The additive migration needs its own finite ACK.

S2 population support is finite and opt-in: one verified manifest for the frozen 47 chunks
and another separately measured upload fixture. The selected profile must match exact source
hashes and ordered content checksums/native token counts. An unknown or changed population
is unavailable until an explicitly verified profile/rebuild; S2 does not automatically build
profiles for arbitrary PDFs. Equal text at two chunk positions is valid repeated content.
Owner Q12 preserves `retrieval-bm25-diagnostic-v1` at candidate limit200 and adds
`retrieval-bm25-top8-v1` at candidate limit8 for the primary opt-in path. Both use one native
Top200 window; changing a candidate limit does not reuse an existing configuration identity.
Owner Q14 binds primary Top8 to the frozen47 profile and gives the separately measured upload
fixture its own `retrieval-bm25-upload-fixture-top8-v1` configuration/profile binding. A single
immutable configuration identity does not vary its lexical profile across these populations.
Owner Q13 approves a new profile/statistics digest using stable source SHA and ordered chunk
checksum/native-count identities. Counts must match retained native evidence and be verified
again in the S2 batch. Historical profiles, runtime chunk identities and evidence are preserved.

Owner Q16 freezes each all60 retrieval query to the selected Baseline B observation, including
saved conversation context for the eight follow-ups. Each case uses one native Top200 window,
primary Top8 and the existing evidence selector, with no generator call. Reports distinguish
this retrieval comparison with frozen B context from fresh application/context verification.

The implementation checkpoint records exact shared-hunk ACKs and separate offline/runtime
evidence. This decision does not authorize provider calls, production activation or migration
outside the owner-approved isolated S2 runtime.

Owner Q19 makes physical generation cleanup an explicit CLI operation rather than a third
ingestion job. PostgreSQL lifecycle locks protect the check that neither active nor desired
head references the generation, including archived documents. The projection delete is
idempotent and errors remain retryable by a later explicit invocation; it never grants serving
eligibility. Accepted experiment collections/points are retained through owner review. Native
cleanup verification uses a separate structural fixture only.

Owner Q20 defines rollback as a fresh `same_as_job` extraction using eligible historical A,
followed by exactly one new index child and a new generation C. Eligibility means the source,
profile and Document/Workspace revision snapshots still match; A need not remain the current
head pointer and its old projection may already have been cleaned. Revoked A is ineligible.
An enqueue revision CAS reserves the new request and fences B's old activation immediately.
The extraction must still own that reserved revision when it completes, then stage/readback
and activate C through the normal receipt/CAS path. Historical identities and the unique
parent-child linkage remain immutable. Reusing A's old parent for another index child is the
withdrawn proposal. This behavior is implemented under finite #192 ACKs6247908659/6248015911/6248144459.
The isolated rollback fixture proved two real extractions, a new parent/child C, enqueue CAS,
stale B rejection and native restaging/readback before revision5 activation. Full integration
and exact-head CI remain separate gates.
