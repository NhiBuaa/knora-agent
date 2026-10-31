# Issue #162: password reset authorization investigation

Investigation date: 13 October 2026, Asia/Saigon. Initial verification base: [PR #160](https://github.com/NhiBuaa/knora-agent/pull/160),
`89ffc296a61cda25a02300c40fc4f78bae698d4c`. PR #160 subsequently merged into `main` as
`f138e81`; the #162 branch has been synchronized with that base. Auth implementation files did
not change between the initial verification base and the merged base. This record accompanies regression coverage;
it does not claim that the reported historical reset loss has been reproduced or repaired.

## Verified observations

- Initial read-only inspection of the reported account found zero Keycloak capability attributes.
  Its issuer/subject still matches the persisted owner of the reported Workspace.
  The account was created on 11 October at 14:17:15, before automatic baseline provisioning
  was introduced at 15:45:54 in commit `bd83b82`. Managed capability profile configuration
  followed in `7f992e2` at 16:32:23. These dates support a legacy provisioning explanation;
  they do not establish the account's capability set before its password reset.
- No historical user event audit was available to prove a before/after capability difference.
  Denial at that inspection was explained by missing Keycloak capabilities. Ownership was not lost.
- The registration listener handles successful registration only. Recovery resolves the existing
  user; native password update changes the credential. The notification listener changes only
  a presentation flag. Neither recovery listener assigns or removes capabilities.
- Fresh OIDC login projects validated ID-token claims into the BFF session. The backend verifies
  access-token capabilities and checks persisted Workspace ownership independently.
- Native browser recovery on the current base preserves the exact capability set for baseline,
  additional grants, restricted read-only access and no capabilities. No reset-loss defect was
  reproduced in those cases. Therefore this change adds regression coverage and diagnosis,
  without speculative restoration of permissions during reset.

Keycloak's native credential update can be inspected in the pinned
[26.3.3 UpdatePassword implementation](https://github.com/keycloak/keycloak/blob/26.3.3/services/src/main/java/org/keycloak/authentication/requiredactions/UpdatePassword.java).

## Regression scope

Each case creates a synthetic account through native registration, captures baseline provisioning,
applies any administrative grant/revocation before recovery, signs in afresh, and records current
authorization. It then runs native Forgot Password, actual mailbox OTP verification, password update,
and another fresh OIDC login. Assertions compare Keycloak authorization attributes after OTP,
password update and login, plus BFF subject, capabilities and Workspace hints.

The real BFF/backend must retain the same owned Workspace, allow or deny Documents read/write and
Chat question admission according to the preserved permissions, and deny foreign Workspace access
in both directions. Empty/restricted capabilities must remain empty/restricted. The baseline case
does not receive an administrative capability repair.

The tests use fixed project `knora-issue162`, Keycloak on `127.0.0.1:8480`, API on `127.0.0.1:8900`,
mailbox on `127.0.0.1:8125`, and frontend on `127.0.0.1:3400`. Preparation and browser checks validate
checkout ownership; preparation rejects ambient `DOCKER_*` and `COMPOSE_*` selectors and ports owned by
other projects. Daily development and Figma services are not targets.

> [!IMPORTANT] > **Consolidated Compose topology update**: The standalone fixture `test/fixtures/password-reset/compose.yml`
> has been deleted as part of the [Compose consolidation plan](../plans/docker-compose-consolidation.md).
> The password reset topology is now integrated into `docker-compose.dev.yml` under capability profile
> `password-reset-test`, explicitly targeting five scoped services: `reset-api`, `reset-keycloak`,
> `reset-keycloak-db`, `reset-mail`, and `reset-postgres` on isolated network `knora-issue162_reset-isolated`.
> Realm configuration and Vault material (`./infra/keycloak` / `$EvidenceRoot/vault`) remain runtime fixture
> data mounted into `reset-keycloak`, NOT a third Compose entry point.

### Guard self-checks vs. automated runtime execution

The setup and guard scripts require PowerShell 7 (`pwsh`) on Windows:

1. **Mocked guard self-checks (NOT real runtime)**:
   The scripts `scripts/test-password-reset-runtime.ps1` and `scripts/test-password-reset-preparation.ps1`
   are mocked guard unit checks that verify parameter parsing, path traversal, ancestor reparse points,
   Vault keys, and error-handling with Docker/HTTP mocked. Running them does NOT execute real runtime containers
   or Playwright browser tests.

2. **Automated runtime invocation (owned `-Run` lifecycle)**:
   Run only after approval of the candidate, owned data, image pulls/builds, ports, time limits and cleanup; the example is not runtime authorization.
   The current launcher is `scripts/prepare-password-reset-regression.ps1`. When executing automated browser
   verification, provide mandatory `-RunId <GUID>`, mandatory `-EvidenceRoot <absolute>`, and `-Run <scriptblock>`:

```powershell
$runId = [guid]::NewGuid().ToString()
$repoRoot = (git rev-parse --show-toplevel).Trim()
$evidenceRoot = Join-Path $repoRoot ".verification/password-reset-$runId"
./scripts/prepare-password-reset-regression.ps1 -RunId $runId -EvidenceRoot $evidenceRoot -Run {
    param($project, $composeArgs)
    Push-Location frontend
    try {
        npm exec -- playwright test --config=playwright.password-reset.config.ts
        if ($LASTEXITCODE -ne 0) { throw "Password reset regression failed ($LASTEXITCODE); preserve evidence" }
    } finally {
        Pop-Location
    }
}
```

- **Project and RunId semantics**: The project name remains fixed as `knora-issue162`. Passing `-RunId`
  identifies the attempt and claim ledger, but does NOT change the project name.
- **Reservation and receipt semantics**: The launcher acquires an exclusive lock file
  `[IO.Path]::GetTempPath()/knora-reset-reservation-knora-issue162.lock`. Inside `finally`, it performs
  cleanup of proved-owned containers, volumes, and network, and writes a durable, sanitized
  `cleanup-receipt.json` into `$EvidenceRoot`. The lock is released only if cleanup succeeds. If cleanup
  fails or receipt persistence fails, the reservation is retained; never automatically steal or delete a stale claim.
- **Checkout ownership refusal**: If existing `knora-issue162` resources exist from another checkout
  (`RESET_TEST_PROJECT_NOT_FRESH` for `-Run`, or `RESET_TEST_CHECKOUT_OWNERSHIP_REQUIRED` during legacy inspection), startup is immediately refused. Do not adopt, delete, or
  rename resources owned by another checkout.
- **Owned lifecycle vs. manual teardown**: The default legacy invocation (`./scripts/prepare-password-reset-regression.ps1`
  without `-Run`) is preserved for retained manual preparation. It can build/start/configure that stack and requires corresponding authorization. The owned `-Run` block is strongly
  recommended because manual, unguarded `docker compose down` is prohibited.
- **Prerequisites**: Next.js, Playwright, and Chromium must already be installed in the owned checkout
  (`frontend/node_modules`). Missing dependencies are blockers requiring explicit authorization; auto-installation
  is prohibited.

New passwords, OTP and bearer tokens exist only in process memory. Browser traces, screenshots and
videos are disabled; failures report only a stage code and a safe error category after clearing page content. Generated realm
and private Vault material are ignored by Git. The fixture uses test-only bootstrap credentials.

## Verification and remaining acceptance

Results are recorded in the linked Issue/PR after execution. Backend CI partition, frontend unit
tests, formatting/type checks and the native recovery matrix are separate from the complete release
runtime gates. This standalone browser test is invoked explicitly, not by the existing Figma profile.

> [!NOTE] > **Historical baseline records**: The local verification observations and test pass counts below are
> historical baseline records from the original Issue #162 investigation (13 October 2026). They confirm
> native auth recovery under the legacy fixture, but do NOT validate the consolidated Docker Compose
> migration. Validating the consolidated Compose migration requires fresh runtime execution under Stage E;
> no new runtime pass claim is made here.

Verified locally: four native recovery cases passed in 39.7 seconds, including real Documents
upload (201), read (200), Conversation creation (201), question admission (202), retained denials
(403) and Workspace isolation. The backend partition passed 1,256 tests (573 other cases deselected);
49 frontend test files passed all 447 cases. The three setup ownership guards, frontend formatting,
TypeScript check, Ruff checks and both applicable Compose configuration checks passed.
The Windows CI partition also passed all 222 selected cases (1,607 others deselected).

Review follow-up makes setup reject reparse points at writable ancestors/targets before writes,
complete valid partially installed recovery flows, replace invalid HMAC keys atomically while retaining
valid keys, and wait for bounded API health before reporting readiness. Sixteen executable setup
self-checks exercise the real script in disposable fixture copies with Docker/HTTP mocked; three use
real directory junctions and two simulate file-link metadata because creating file symlinks requires
elevation on this machine. Five frontend tests check safe failure categories without retaining secret
messages or causes. The separate three runtime ownership guards still apply.
After these repairs, real runtime preparation succeeded and all four native recovery cases passed
again in 40.6 seconds without retries. Frontend category/JUnit tests passed six cases; frontend
formatting/type checks, Ruff checks and production/fixture Compose configuration checks passed.

## User-reported manual check

On 13 October the user reported deleting the existing users, creating/testing user `gohuynh`,
completing Forgot Password and changing the password, then successfully uploading Documents and
sending a Chat question. This confirms current functional access for that new user. It is
user-reported manual evidence, separate from the agent's isolated automated matrix and its exact
subject/capability/Workspace comparisons. It does not establish what happened to the previous
account's permissions before deletion. No password, OTP or token is requested or recorded.

This agent did not modify the reported account. Determining whether its permissions were previously granted
requires approved provisioning history or a reproducible before/after observation on the current
auth base. Recovery must never infer those grants from missing attributes or reapply a baseline.
Keep #162 In Progress pending review and integration/acceptance; do not close it from this evidence.
#160 is now merged, so its integration dependency is resolved. Gmail SMTP/rollback #157 and Documents
UI/navigation/shared Figma harness work are outside this change.

PR #165 was merged by the repository owner on 13 October into the former #160 branch,
`fix/restore-figma-merge-regressions`. At follow-up inspection GitHub `main` still pointed to `f138e81`,
so that merge did not integrate #162 into `main`. A follow-up PR targets `main` with the #162 changes
and the five review repairs. This agent did not merge either PR or close the Issue.
