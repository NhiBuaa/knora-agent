# Task 3 report

Status: implemented

Added the typed `QuestionEvent` contract and `AnswerQuestion.execute_stream` async iterator with
deterministic progress stages, one terminal validated/refusal/failure event, and no token or
provisional answer deltas. Added `format_sse_event` and the additive `POST /v1/questions/stream`
transport with workspace/authentication validation, no-store buffering headers, and an explicit
OpenAPI `text/event-stream` response. The existing synchronous `/v1/questions` route remains
unchanged.

Verification:

- `pytest test/api/test_question_stream.py -q`: 2 passed
- `pytest test/answering/test_question_stream.py -q`: 2 passed
- `pytest test/adapters/http/test_questions.py test/api/test_http_api.py -q`: 8 passed, 1
  PostgreSQL integration failure because the local database has no migrated `workspaces` table
- Ruff passed on all touched source and test paths
- OpenAPI inspection confirmed `/v1/questions/stream` and `text/event-stream` content

Disconnect safety is provided by the request-scoped async generator: no background task is
created, and cancellation/iterator close can terminate the stream without detached work.
