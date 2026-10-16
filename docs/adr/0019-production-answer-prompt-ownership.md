# Keep production answer prompt definitions separate from provider transport

Status: owner-approved design through Issue #191; implementation acceptance pending.

The internal `knora.providers.prompts` module owns production answer policy,
the two existing serializers, pure message building and static definition identity.
It preserves generic, Ollama Qwen/GPT-OSS and both Cloudflare stage profiles rather
than applying a single policy to providers with different contracts. Existing
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

Issue #183 owns Cloudflare behavior/schema and its separate acceptance. Its approved
changes are synchronized as an explicitly recorded upstream baseline, then checked
for extraction parity. Passing #191 tests does not accept #183, establish semantic
support or fix provider HTTP400/token-limit failures. Until #183 is accepted into
main, #191 must not carry its unaccepted behavior there through a main-targeted PR.
