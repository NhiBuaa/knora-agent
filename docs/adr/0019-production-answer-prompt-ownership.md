# Keep production answer prompt definitions separate from provider transport

Status: owner-approved design through Issue #191; accepted-main integration proposed in PR #200.

The internal `knora.providers.prompts` module owns production answer policy,
the two existing serializers, pure message building and static definition identity.
It preserves generic, Ollama Qwen/GPT-OSS and the accepted single-call Cloudflare
answer profile, including their different contracts. Existing
constant imports remain compatible exports. This centralizes reviewable model input
without adding a provider interface, registry, template engine or dependency.

Adapters keep HTTP/authentication, model controls, digest checks, error handling,
decoding, metadata and Cloudflare composition. Existing schema models/helpers stay
with their contract owners; the builder selects their actual definitions. Application
code keeps Evidence Aliases, Conversation Context selection/bounds and question
wrapping, public validation, citation mapping and access. Experimental and scorer
prompts retain their own evaluation ownership.

Readable prompt versions and runtime metadata schemas are unchanged. Each definition
fingerprints its static system text, schema, version and explicit serializer identity.
Independent baseline wire fixtures and drift tests bind serializers/messages to those
identities; evaluation's existing committed-source guard includes the extracted
dependencies. Question/evidence, secrets and model/token configuration are not part
of this static fingerprint. No new runtime refusal gate, metadata field or history
rewrite follows from the fingerprint.

Issue #183 owns Cloudflare behavior/schema and its separate acceptance. PR #184
was accepted and merged into main as `0f76233b7ebbdf49cedba0b3affe96e132b069e4`;
[the owner released #191's integration gate](https://github.com/NhiBuaa/knora-agent/issues/191#issuecomment-6336021245).
The extraction follows that accepted v21 policy/schema/serializer and production
cap 2048. The removed selector and its stage aggregation have no current prompt
profile; application SSE progress remains independent. Historical v17 fixtures
remain evidence of their own baseline, alongside a separate accepted-main oracle.
Passing extraction tests does not establish model compliance, semantic support or
new runtime acceptance. This integration grants no provider, merge or deployment
authority.
