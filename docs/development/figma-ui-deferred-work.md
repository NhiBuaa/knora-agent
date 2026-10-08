# Figma-to-code: approved deferred work

Date: 2026-10-08. The owner confirmed the proposed deferrals after requesting an
existing Issue/PR audit. Open Issues #146–#148 are unrelated; no open PR was found.
The following four Issues were created and read back. Keep their existing code and
tests. A deferral does not count as implementation or evidence of successful operation.

| Work | GitHub record | Implemented | Remaining and reason | Resume condition |
| --- | --- | --- | --- | --- |
| Live Documents navigation evidence | [#149](https://github.com/NhiBuaa/knora-agent/issues/149) | Locally qualified at `f9f6721`: the named live journey passed, 52 focused checks passed, five captures and source/lifecycle JSON were independently reviewed | The former runtime evidence gap is resolved locally; remote integration remains pending. Physical deletion, PDF processing and menu direct-detail parity are outside this proof | Integrate the reviewed local commit through the approved Git workflow; retain the existing Issue until remote disposition is recorded |
| Physical document deletion | [#150](https://github.com/NhiBuaa/knora-agent/issues/150) | Confirmation UI, cancellation/focus behavior and truthful backend policy projections | Processor, retention/purge policy and lifecycle completion require a separate domain decision | Approved retention/API/storage/audit contracts and authoritative end-to-end results |
| Mobile/dark source parity | [#151](https://github.com/NhiBuaa/knora-agent/issues/151) | Responsive layouts, semantic tokens and bounded interaction checks | Exact comparison lacks supplied source frames | Authoritative source frames or explicit owner-approved layout/token rules |
| OTP deployment hardening | [#152](https://github.com/NhiBuaa/knora-agent/issues/152) | Provider/service/storage source, templates, offline tests and bounded two-node proofs | Deployment rotation/restart, CSP, outages, upgrade proof and production runbook | Functional native recovery and essential safety accepted; appropriate isolated topology available |

## Requirements retained on the critical path

Desktop Figma screens and core interactions remain required. Native email → six-digit
OTP → Keycloak password update remains required, together with one-time consume,
expiry, cooldown, account/IP budgets, concurrency, unknown-account/delivery-failure
safety, MFA preservation and sensitive-data protection. Source tests alone do not
prove the native flow.

OTP stays unbound in ordinary and production configuration until its safety
prerequisites are proved. The rejected physical database outage operation must not
be retried through an equivalent workaround. The owner's deferral permits work on
functional isolated recovery without treating deployment-only outage proof as its
completion gate; it does not waive fail-closed behavior or authorize unsafe rollout.

The full Figma goal remains active. Deferred records do not accept unresolved desktop
parity or replace evidence for applicable product transitions.
