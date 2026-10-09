# Figma UI Q1 visual and interaction coverage — PARTIAL

Oct 7, 2026. Review base `eed8f9660a626c6dc181aea01fea4ced6e791a1e`. This ledger records observed evidence and remaining deviations; it does not accept a screenshot baseline or declare full Q1 complete.

## Evidence contract

- `V:<id>` is the individually named `source fixture <id> <name>` case in `frontend/tests/e2e/figma-ui-visual.spec.ts`; all 51 rows captured at 1440×960.
- Durable captures and side-by-side comparisons live under ignored `.superpowers/figma/q1/evidence/`. The original51 screen comparisons crop only the34px annotation strip from their1440×994 Figma PNGs. Original full MCP structures and source-index manifest remain unchanged in the foundations worktree cache. The separate Oct7 Operator prototype sources have1440×960 frames and1024×683 MCP PNGs with no annotation strip; their whole frames are compared proportionally without cropping.
- Cached structure is the geometry authority; PNG comparison checks the actual composition, assets, text hierarchy, borders, colors and selected/disabled/error state. RGB differences in `source-comparisons.json` are descriptive only, never an acceptance threshold.
- Fixture host composes actual modules, production CSS, local Inter/Roboto Slab and actual Next hooks/providers. Browser clock fixed to2026-10-05T12:00Z. API interception rejects unexpected paths/methods; it proves no backend authorization. Native fixtures render maintained FTL with pinned FreeMarker2.3.32/Keycloak26.3.3 parent assets and block submissions.
- The ten panel/response references are compact schematics. Their captures demonstrate actual module state, not full-screen pixel parity. Responsive/dark references are absent: tested adaptations cannot be described as Figma geometry acceptance.
- Owner abbreviations: U2 Conversation; U3 Workspace/Documents; O Operator; I1 sign-in/registration; I2 reset/OTP; I3 completion; Q1 verification. Every row below belongs to Q1 plus its implementation owner.

## Screen and state comparison ledger

| ID / kind / name | Owner | Test | Capture / comparison | Observed deviation or gap |
| --- | --- | --- | --- | --- |
| 128:107 / screen / A2 · Expanded · Evidence selected | Q1/U2 | V:128:107 | `128-107-1440x960.png`; `128-107-comparison.png` | Header/252px rail/376px inspector structure agrees. Actual answer has no fabricated chapter-count heading; citation selected styling retained; divider/focus controls add chrome. |
| 128:108 / screen / A2 · Collapsed · Thinking | Q1/U2 | V:128:108 | `128-108-1440x960.png`; `128-108-comparison.png` | Collapsed rail present; production processing stages and progress copy replace prototype thinking illustration; no timeout fabricates completion. |
| 128:109 / screen / A3 · New conversation · Empty | Q1/U2 | V:128:109 | `128-109-1440x960.png`; `128-109-comparison.png` | Original leaf/orbit assets and empty-state hierarchy present. Real suggested prompts differ from the prototype domain examples; search/archive controls add rail content. |
| 128:110 / screen / A4 · Grounded answer · Default | Q1/U2 | V:128:110 | `128-110-1440x960.png`; `128-110-comparison.png` | 64px header, 252px rail, 376px inspector and anchored composer agree. Answer body preserves authoritative text; no generated '7 chapters' heading; second citation uses returned page range. Extra panel controls and desktop Menu remain visible. |
| 128:111 / screen / A5 · Insufficient evidence | Q1/U2 | V:128:111 | `128-111-1440x960.png`; `128-111-comparison.png` | Refusal heading/error tone present. Production refusal reason and follow-up prompts are backend projections rather than forced prototype policy text. |
| 128:112 / screen / A6 · Retrieving evidence | Q1/U2 | V:128:112 | `128-112-1440x960.png`; `128-112-comparison.png` | Retrieving state present. Production stage indicator uses actual pending status; clicking it does not advance to an answer. |
| 128:115 / screen / A7 · Citation selected | Q1/U2 | V:128:115; parity toggle interaction | `128-115-1440x960.png`; `128-115-comparison.png`; `parity-citation-deselected.png` | Selected evidence and metadata shown. Oct 7 parity follow-up now clears the same Turn/index on repeated mouse or keyboard selection; another Turn/index keeps its own historical evidence. Remaining answer/citation copy and extra controls differ as documented. |
| 128:118 / screen / A8 · Answer interrupted | Q1/U2 | V:128:118 | `128-118-1440x960.png`; `128-118-comparison.png` | Interrupted presentation and retry affordance present. Retry checks history and restores draft; it does not promise immediate answer/restart. |
| 128:119 / screen / A9 · Archived · Read-only | Q1/U2 | V:128:119; Oct8 archived Conversation interaction | `128-119-1440x960.png`; `128-119-comparison.png`; `archived-conversation-bar-2026-10-08/implemented-128-119-{1440,390}.png` | Original captures remain historical. Oct8 authoritative archived copy and local bar/restore geometry corrected; generic rejection keeps read-only copy. History, evidence and source assets retained. Whole-frame parity remains open. |
| 128:120 / screen / D1 · Documents · State matrix | Q1/U3 | V:128:120 | `128-120-1440x960.png`; `128-120-comparison.png` | Five reference document names/state projections and Ready menu captured. Actual Reprocess/answer-availability copy is derived from API fields; menu includes supported reprocess action; contrast colors differ. |
| 128:121 / screen / D2 · Upload document · Selected file | Q1/U3 | V:128:121 | `128-121-1440x960.png`; `128-121-comparison.png` | Selected Reporting policy.pdf and actual dialog captured. Backend accepted kinds shown; deterministic fixture file is not submitted or parsed. |
| 128:122 / screen / D7 · Document detail · Ready | Q1/U3 | V:128:122; Document detail action height and cancellation {1440,390} | `128-122-1440x960.png`; `128-122-comparison.png`; `document-detail-action-height-2026-10-08/implemented-128-122-{1440,390}.png` | Historical captures retained. Oct8 deletion now measures40px; Reprocess/Archive remain42px. Actual source/serving fields and last-processed timestamp preserve API meanings; natural row growth and whole-frame differences remain. |
| 128:125 / screen / D8 · Document detail · Archived | Q1/U3 | V:128:125; Document detail action height and cancellation {1440,390} | `128-125-1440x960.png`; `128-125-comparison.png`; `document-detail-action-height-2026-10-08/implemented-128-125-{1440,390}.png` | Historical captures retained. Oct8 deletion now measures40px; Restore remains42px. Archived status and unavailable new-answer projection retained. Actual detail-dialog Cancel/Escape return focus; whole-frame parity remains open. |
| 128:128 / screen / D9 · Request deletion · Confirm | Q1/U3 | V:128:128 | `128-128-1440x960.png`; `128-128-comparison.png` | Actual deletion confirmation modal and destructive hierarchy present. Copy describes conditional availability and asynchronous request rather than guaranteeing removal. |
| 128:131 / screen / D9 · Document detail · Deletion requested | Q1/U3 | V:128:131 | `128-131-1440x960.png`; `128-131-comparison.png` | Requested deletion projection captured only as fixture. Status/availability displayed from independent returned fields; no claim of physical deletion. |
| 140:104 / screen / W1 · Workspace selector · Open | Q1/U3 | V:140:104 | `140-104-1440x960.png`; `140-104-comparison.png` | Empty underlying conversation and exact Research/Policy/Reporting options captured. Actual selector includes search and archived-navigation controls absent from target. |
| 148:116 / screen / W2 · Create workspace · Ready | Q1/U3 | V:148:116 | `148-116-1440x960.png`; `148-116-comparison.png` | Actual modal dimensions/focus/error capability captured over empty conversation. Mobile uses actual WorkspaceManagement Create trigger; no mobile Figma geometry reference. |
| 152:128 / screen / W3 · No active workspace | Q1/U3 | V:152:128 | `152-128-1440x960.png`; `152-128-comparison.png` | No-active heading and actions present; actual canonical resolver wording and active-navigation layout differ. Fresh registration resolves My Workspace ACTIVE, not this prototype landing. |
| 154:134 / screen / W4A · Workspace actions · Archive | Q1/U3 | V:154:134 | `154-134-1440x960.png`; `154-134-comparison.png` | Archive menu captured over empty conversation; actual ellipsis/Menu primitives and focus styling are preserved. |
| 154:290 / screen / W4B · Archive workspace · Confirm | Q1/U3 | V:154:290 | `154-290-1440x960.png`; `154-290-comparison.png` | Actual archive confirmation and conditional next-workspace explanation captured. Prototype cannot guarantee no-active outcome if another active workspace exists. |
| 154:431 / screen / W4C · Archived workspaces · Default | Q1/U3 | V:154:431 | `154-431-1440x960.png`; `154-431-comparison.png` | Three reference archived workspace names captured. Production restore/read-only semantics and search preserved; actual details reflect deterministic fixture projections. |
| 166:211 / screen / W4D · Archived workspaces · No results | Q1/U3 | V:166:211 | `166-211-1440x960.png`; `166-211-comparison.png` | No-results hierarchy/search state captured. Input uses deterministic unmatched query rather than reference literal; actual clear/search styles differ. |
| 166:290 / screen / W4E · Archived workspaces · Empty | Q1/U3 | V:166:290 | `166-290-1440x960.png`; `166-290-comparison.png` | Empty archived-list state captured; no restore row exists. Actual list heading/search spacing retained. |
| 183:176 / screen / W5A · Workspace archived · Read-only | Q1/U3 | V:183:176; parity bottom restore fixture/live; archived evidence notice fixture | `183-176-1440x960.png`; `183-176-comparison.png`; `parity-workspace-390.png`; `parity-live-workspace-archived.png`; `archived-evidence-notice-1440.png`; `archived-evidence-notice-390.png`; `archived-inspector-context-1440.png`; `archived-inspector-context-390.png` | Oct 7 follow-ups add source 72px bar, exact archived Workspace/helper copy and 184×40 desktop Restore workspace CTA, plus the separate READ-ONLY WORKSPACE inspector notice with exact copy, 340×82 desktop geometry and source padding/radius/gap. The retained unselected ANSWER context now measures 340×96 desktop, padding 14/13, gap/radius 8 and 14px notice separation; mobile naturally grows to 298×111.5 with all text visible. Selected historical excerpts and other outcome contexts retain 146px minimum. Server projection supplies revision/archive state; public restore/resolver selects destination, retaining any separately archived Conversation. Notice preserves historical source/version/provenance, appears in detail/Hub only for archived Workspace, and adapts to mobile/enlarged text without clipping. Remaining illustrated answer heading, citation labels, extra controls and small existing inspector origin offsets remain differences; full screen parity is not claimed. |
| 183:334 / screen / W5B · Limited permissions · Documents | Q1/U3 | V:183:334 | `183-334-1440x960.png`; `183-334-comparison.png` | Limited capability projection disables management and exposes read-only access. Actual descriptive copy/accessible actions differ from prototype abbreviated labels. |
| 183:490 / screen / W5C · Workspace unavailable · Access denied | Q1/U3 | V:183:490 | `183-490-1440x960.png`; `183-490-comparison.png` | Unavailable heading and Choose another workspace retained. No synthetic authorization grant or invented unavailable cause. |
| 194:194 / screen / O1 · Operator · Operations | Q1/O | V:194:194 | `194-194-1440x960.png`; `194-194-comparison.png` | 1200px Operator surface at x120/y64 matches structure. Original fixture metrics remain deterministic zero observations. The separate Oct7 216:345 comparison now supplies source-like nonzero/zero/missing observations; its recorded parity deviations remain open. |
| 198:200 / screen / O2 · Operator · Traces · Detail | Q1/O | V:198:200 | `198-200-1440x960.png`; `198-200-comparison.png` | Actual trace schema rendered with lookup/context/timing. Fixture trace has zero candidates; target two candidates and184ms are example data. No backend observation fabricated. |
| 206:206 / screen / O3 · Operator · Evaluations · Unavailable | Q1/O | V:206:206 | `206-206-1440x960.png`; `206-206-comparison.png` | Original unavailable evaluation and context remain unchanged. Lookup ID and timestamp are fixtures, never a fabricated report/download. The separate Oct7 216:755 comparison records remaining geometry, badge and context differences. |
| 228:212 / screen / AU1 · Sign in · Default | Q1/I1 | V:228:212; live account logout and forced sign-in {1440,390} | `228-212-1440x960.png`; `228-212-comparison.png`; `live-logout-prompt-2026-10-08/fresh-sign-in-{1440,390}.png` | Historical fixture submission blocked. Oct8 real normal login and post-logout password-empty native sign-in verified; native username/copy differ. Mobile adapts the brand panel; source geometry acceptance remains open. |
| 228:251 / screen / AU2 · Sign in · Invalid credentials | Q1/I1 | V:228:251 | `228-251-1440x960.png`; `228-251-comparison.png` | Actual invalid-credential FTL/error roles. Deterministic generic field errors differ from reference credential message; native validation authority unproved. |
| 228:293 / screen / AU3 · Sign in · Unavailable | Q1/I1 | V:228:293 | `228-293-1440x960.png`; `228-293-comparison.png` | Production AuthOutcome unavailable view; brand/copy hierarchy present. Real outage was not retried; fixture is presentation only. |
| 228:326 / screen / AU4 · Authentication · Failed | Q1/I1 | V:228:326 | `228-326-1440x960.png`; `228-326-comparison.png` | Production failed callback view; error styling/action present. Runtime callback failure behavior is not exercised by this state projection. |
| 228:424 / screen / AU5 · Account menu · Open | Q1/I1 | V:228:424; live account logout and forced sign-in {1440,390} | `228-424-1440x960.png`; `228-424-comparison.png`; `live-logout-prompt-2026-10-08/account-menu-{1440,390}.png` | Historical fixture retained. Oct8 actual subject menu over the real Workspace landing shows Signed in/Log out; Enter submits native logout and provider confirmation. Safe subject wraps; mobile menu overlays the landing. Whole-frame parity remains open. |
| 237:251 / screen / AU8 · Create account · Default | Q1/I1 | V:237:251 | `237-251-1440x960.png`; `237-251-comparison.png` | Actual registration FTL/user-profile attributes. Native fields, secure disclaimers and labels preserved; no fake registration/password authority. |
| 237:313 / screen / AU9 · Create account · Validation error | Q1/I1 | V:237:313 | `237-313-1440x960.png`; `237-313-comparison.png` | Actual registration error roles/fields; generic model errors differ from target specific validation text. No native successful validation claim. |
| 242:272 / screen / AU10 · Forgot password · Request | Q1/I2 | V:242:272 | `242-272-1440x960.png`; `242-272-comparison.png` | Actual maintained reset-email FTL: 'Reset your password'/'Send reset code' differ from target 'Forgot your password?'/'Send verification code'; anti-enumeration copy preserved. |
| 242:333 / screen / AU11 · Forgot password · Verify code | Q1/I2 | V:242:333 | `242-333-1440x960.png`; `242-333-comparison.png` | Actual OTP FTL/six cells, leading-zero paste and accessible input. Fixed40px specificity defect to56px; title/copy/30s countdown differ from target, focus outline intentionally visible. Native CSP/countdown/service proof still held. |
| 242:389 / screen / AU12 · Reset password · New password | Q1/I2 | V:242:389 | `242-389-1440x960.png`; `242-389-comparison.png` | Actual login-update-password FTL; native logout-other-sessions checkbox and Submit remain, versus target Reset password label. No password update performed. |
| 246:311 / screen / AU11B · Forgot password · Verify code · Error | Q1/I2 | V:246:311; OTP resend fallback interaction; native runtime states | `246-311-1440x960.png`; `246-311-comparison.png`; `otp-resend-no-js-enabled.png`; `native-otp-runtime-2026-10-08/` | Actual OTP error FTL and six cells;56px fix and transparent enhanced text proved. Generic anti-enumeration error/copy differ. Native runtime additionally proved server cooldown, resend and generation fencing; CSP/deployment hardening remains held in Issue #152. |
| 246:404 / screen / AU1B · Sign in · Password reset success | Q1/I3 | V:246:404; native detached completion | `246-404-1440x960.png`; `246-404-comparison.png`; `native-otp-runtime-2026-10-08/detached-completion-{desktop1440x960,mobile390x844}.png` | Actual maintained info FTL completion title/body differs from target branded Sign in success. Only trusted prompt=login CTA exists; no Forgot password/Create account actions. Native fresh login and password/TOTP authority passed; completion notice + native login composition remains visually different from Figma and provider browser SSO cookie reuse is unverified. |
| 4:10 / panel / open rail / inspector closed | Q1/U2 | V:4:10 | `4-10-1440x960.png`; `4-10-comparison.png` | Actual panel state rendered and manipulated through actual controls; original compact schematic retained. Full-screen geometry/reference missing; semantic layout only, no pixel acceptance. |
| 4:35 / panel / open rail / inspector open | Q1/U2 | V:4:35 | `4-35-1440x960.png`; `4-35-comparison.png` | Actual panel state rendered and manipulated through actual controls; original compact schematic retained. Full-screen geometry/reference missing; semantic layout only, no pixel acceptance. |
| 4:67 / panel / collapsed rail / inspector open | Q1/U2 | V:4:67 | `4-67-1440x960.png`; `4-67-comparison.png` | Actual panel state rendered and manipulated through actual controls; original compact schematic retained. Full-screen geometry/reference missing; semantic layout only, no pixel acceptance. |
| 4:99 / panel / hidden rail / inspector open | Q1/U2 | V:4:99 | `4-99-1440x960.png`; `4-99-comparison.png` | Actual panel state rendered and manipulated through actual controls; original compact schematic retained. Full-screen geometry/reference missing; semantic layout only, no pixel acceptance. |
| 4:126 / panel / collapsed rail / inspector closed | Q1/U2 | V:4:126 | `4-126-1440x960.png`; `4-126-comparison.png` | Actual panel state rendered and manipulated through actual controls; original compact schematic retained. Full-screen geometry/reference missing; semantic layout only, no pixel acceptance. |
| 4:165 / response / answered | Q1/U2 | V:4:165 | `4-165-1440x960.png`; `4-165-comparison.png` | Actual response projection rendered inside ConversationView. Compact response schematic is not a full-screen geometry reference; actual body/result/retry copy is authoritative. |
| 4:179 / response / processing | Q1/U2 | V:4:179 | `4-179-1440x960.png`; `4-179-comparison.png` | Actual response projection rendered inside ConversationView. Compact response schematic is not a full-screen geometry reference; actual body/result/retry copy is authoritative. |
| 4:190 / response / insufficient evidence | Q1/U2 | V:4:190 | `4-190-1440x960.png`; `4-190-comparison.png` | Actual response projection rendered inside ConversationView. Compact response schematic is not a full-screen geometry reference; actual body/result/retry copy is authoritative. |
| 4:201 / response / interrupted | Q1/U2 | V:4:201 | `4-201-1440x960.png`; `4-201-comparison.png` | Actual response projection rendered inside ConversationView. Compact response schematic is not a full-screen geometry reference; actual body/result/retry copy is authoritative. |
| 4:212 / response / system error | Q1/U2 | V:4:212 | `4-212-1440x960.png`; `4-212-comparison.png` | Actual response projection rendered inside ConversationView. Compact response schematic is not a full-screen geometry reference; actual body/result/retry copy is authoritative. |

## Oct8 Documents local controls and mobile menu placement

The two named `Documents local interactions {1440,390} verifies filters, menus and cancelled dialogs without mutations` cases exercise actual DocumentList/Menu/Dialog controls at1440×960 and390×844. Exact Reporting policy.pdf search shows one row/count1; an unmatched query shows the empty state/count0; clearing restores five/count5. The state-driven fixture host stays on its original URL: Ready row and View details href agree with `/workspaces/fixture-workspace/documents/fixture-document`, but destination edges7/10/15 remain unexercised. Archived detail-button edge23 also remains unexercised; menu edge26 is separate.

Durable evidence is confined to `.superpowers/figma/q1/evidence/documents-local-interactions-2026-10-08/`: four final states at each width (`ready-menu`, `archived-menu`, `archived-deletion-confirm`, `upload-selected`), two journey JSON records, and retained mobile Archived menu RED geometry/PNG. Saved browser RED reports bottom924.421875 against844; the approved single `max-md:[&_.kn-menu\_\_panel]:bottom-full` rule in DocumentActionsMenu changes mobile placement only. Saved GREEN reruns both original journeys (2 passed); existing scoped document component regressions report45 passed across2 files. Mobile menu bottom is475px Ready and779.28125px Archived. Desktop menus remain downward, at200×155 Ready and200×121 Archived. Dialogs measure560×327/560×423 desktop and352×379/352×443 mobile (deletion/upload). All measured surfaces and menuitems fit the viewport with no horizontal overflow; captures were viewed for readable text and controls. No mobile Figma reference exists, so this is responsive usability evidence only.

Both journey records contain only the two intercepted Workspace/Documents GETs, no unexpected API paths/methods and no writes. The test-only selected file is never submitted or parsed; archive/restore/reprocess/deletion confirmation and native identity actions remain uninvoked. No backend authorization or lifecycle acceptance is added. Assets remain the loaded18×18 local Knora leaf in the header and8×5 local Workspace caret in its selector slot; normal page scrolling moves header assets above the mobile viewport without resizing them. All340 prior Q1 hashes are unchanged; the12 additions belong solely to this evidence directory, excluding the existing root regression-preflight from inventory.

At this prior checkpoint, the header Upload trigger measured158.234375×38 against source154×38. The later bounded Upload correction below resolves that allocation. Ready menu x1107 still differs from source x1115. Focus outlines remain visible. Status/helper text follows API fields (including Not indexed rather than manufacturing Needs re-index), and actual dialog copy describes asynchronous policy-dependent deletion. Original captures, unexercised edges and all live limitations are retained. Full Q1/design acceptance remains PARTIAL.

### Oct8 Documents Upload trigger allocation

Complete direct MCP128:120 nodes54:193–195 allocate154×38 to the Upload trigger, with8px gap,8px radius,15px plus and13px label. The maintained trigger now has that exact allocation at1440×960 and390×844. Loaded Inter requires10.078125px for the plus and111.484375px for “Upload document”; with8px gap, the129.5625px content fits the132px inner width left by local10px horizontal padding and1px borders. The label renders on one line. The local `!px-2.5` overrides shared Button padding; its first non-important form retained14px, caused a two-line wrap, and was rejected by the strengthened browser assertion. No shared primitive or asset changed.

Dedicated source fixture cases at both widths capture the current header and empty Upload dialog, verify disabled submission, Cancel and reopened Escape, and check focus returns to the trigger. Loaded header assets remain18×18 leaf and8×5 caret. Page width and button content fit; unexpected API requests and writes are empty. Existing Documents local interaction cases were rerun unchanged except for their output path, preserving all filter, menu, selected-file, cancellation and focus assertions. New evidence is `.superpowers/figma/q1/evidence/document-upload-trigger-2026-10-08/`: header/dialog PNGs, geometry JSONs, retained RED captures, and `local-interactions/` journey/capture outputs. Historical `documents-local-interactions-2026-10-08/` files remain in place.

The source-white foreground differs from the maintained accessible action-foreground token; menu origin, status/copy, whole-frame and native differences remain open. Mobile has no Figma geometry reference and proves responsive fit only. This local correction does not accept complete design parity or a live upload lifecycle.

## Prototype transitions (89 individually classified edges)

Classification describes the product relationship, not automatic test acceptance. `visual only` means the source/destination presentation was captured; the edge itself remains unexercised. Required native authentication/recovery results stay explicit gaps. Screenshots below are relative to the durable evidence directory.

| # | Source → destination | Trigger | Classification / owner | Owning test / scope | Screenshot | Observed result / deviation / gap |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 117:104 Prototype · Documents · 01 List before upload → 117:224 Prototype · Documents · 02 Upload selected | Button · Upload document | real action / Q1+U3 | owned document lifecycle (live) | `live-document-ready.png` | Actual owned document navigation/archive/restore observed through UI and backend responses. |
| 2 | 117:104 Prototype · Documents · 01 List before upload → 124:141 Prototype · Documents · 07 Ready detail | Document row · Teacher Manh – Guidelines 2024.pdf | real action / Q1+U3 | owned document lifecycle (live) | `live-document-ready.png` | Actual owned document navigation/archive/restore observed through UI and backend responses. |
| 3 | 117:224 Prototype · Documents · 02 Upload selected → 117:104 Prototype · Documents · 01 List before upload | Button · Cancel | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local controls) | `documents-local-interactions-2026-10-08/upload-selected-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Selected-file Cancel closes the actual dialog and returns focus to Upload; reopening clears the draft and file input, disables Upload, and Escape returns focus. Underlying five-row state matrix is retained; prototype before-upload population and backend upload are not proved. |
| 4 | 117:224 Prototype · Documents · 02 Upload selected → 117:344 Prototype · Documents · 03 List processing | Button · Upload document · Confirm | real action / Q1+U3 | owned document lifecycle (live) | `live-pdf-job.png` | Actual Markdown upload and PDF queued submission observed; controller isolated extractor later produced actual PDF Ready. No forced timeout. |
| 5 | 117:344 Prototype · Documents · 03 List processing → 117:224 Prototype · Documents · 02 Upload selected | Button · Upload document | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local controls) | `documents-local-interactions-2026-10-08/upload-selected-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Upload trigger opens the actual dialog from the state matrix containing a processing row; test-only in-memory Reporting policy.pdf enables Upload. No submission, parsing, ingestion or READY transition is invoked. |
| 6 | 117:344 Prototype · Documents · 03 List processing → 117:464 Prototype · Documents · 04 Show archived | Show archived | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local controls) | `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Checking Show archived restores Legacy handbook.pdf and changes visible count from4 to5. Filtering is local; ingestion/status meanings are unchanged. |
| 7 | 117:344 Prototype · Documents · 03 List processing → 124:141 Prototype · Documents · 07 Ready detail | Document row · Teacher Manh – Guidelines 2024.pdf | real action / Q1+U3 | V:128:122 (fixture visual only) | `128-122-1440x960.png` | Actual Documents components/source state captured; exact edge unexercised. Upload submission, processing and READY must remain separate backend observations. |
| 8 | 117:344 Prototype · Documents · 03 List processing → 117:611 Prototype · Documents · 05 Ready menu | More | real action / Q1+U3 | Documents local interactions {1440,390} (fixture keyboard controls) | `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | With archived rows excluded, ArrowDown on the actual Ready trigger opens its menu; Escape closes it and returns trigger focus. No row navigation or lifecycle action is invoked. |
| 9 | 117:464 Prototype · Documents · 04 Show archived → 117:344 Prototype · Documents · 03 List processing | Show archived | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local controls) | `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Unchecking Show archived removes Legacy handbook.pdf and changes visible count from5 to4. Processing remains an independent backend projection. |
| 10 | 117:464 Prototype · Documents · 04 Show archived → 124:141 Prototype · Documents · 07 Ready detail | Document row · Teacher Manh – Guidelines 2024.pdf | real action / Q1+U3 | Documents live navigation (f9f6721) | `document-navigation-2026-10-08/ready-detail.png`; `document-navigation-2026-10-08/journey.json` | Checked Show archived list opens the exact owned Ready document; actual URL, heading and scoped GET confirm its identity. Unique synthetic source name replaces prototype example data. Markdown is synchronous with null job/status and independently observed ready/current versions; no asynchronous processing claim. |
| 11 | 117:464 Prototype · Documents · 04 Show archived → 117:611 Prototype · Documents · 05 Ready menu | More | real action / Q1+U3 | Documents local interactions {1440,390} (fixture keyboard controls) | `documents-local-interactions-2026-10-08/ready-menu-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | ArrowDown opens Ready actions with archived rows included. Exact View details/Reprocess/Archive/Request deletion entries and ArrowDown/ArrowUp focus verified. Desktop downward composition retained; mobile upward placement is a disclosed adaptation. |
| 12 | 117:464 Prototype · Documents · 04 Show archived → 124:231 Prototype · Documents · 08 Archived detail | Document row · Legacy handbook.pdf · Archived | real action / Q1+U3 | Documents live navigation (f9f6721) | `document-navigation-2026-10-08/archived-detail.png`; `document-navigation-2026-10-08/journey.json` | Checked archived list opens the exact owned Archived document after real Archive200/If-Match1. GET200 observes revision2, unchanged source/served versions and unavailable new-answer eligibility; no fabricated filename or physical deletion. |
| 13 | 117:464 Prototype · Documents · 04 Show archived → 117:758 Prototype · Documents · 06 Archived menu | More | real action / Q1+U3 | Documents local interactions {1440,390} (fixture keyboard controls) | `documents-local-interactions-2026-10-08/archived-menu-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Archived trigger opens View details/Restore document/Request deletion, with no Reprocess. All menuitems fit after the diagnosed mobile upward placement amendment; Restore and deletion confirmation are never submitted. |
| 14 | 117:611 Prototype · Documents · 05 Ready menu → 117:464 Prototype · Documents · 04 Show archived | More | real action / Q1+U3 | Documents local interactions {1440,390} (fixture keyboard equivalent) | `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Escape closes Ready menu and returns focus to its existing trigger with all five rows retained. Equivalent keyboard close is exercised; the exact prototype More toggle is not clicked. |
| 15 | 117:611 Prototype · Documents · 05 Ready menu → 124:141 Prototype · Documents · 07 Ready detail | Menu item · View details | real action / Q1+U3 | Documents live navigation (f9f6721) | `document-navigation-2026-10-08/ready-menu.png`; `document-navigation-2026-10-08/ready-detail.png` | Actual Ready Actions menu toggles open/closed/reopened, then View details arrives at the exact owned detail URL. Heading and authenticated GET confirm the same source identity. |
| 16 | 117:611 Prototype · Documents · 05 Ready menu → 124:231 Prototype · Documents · 08 Archived detail | Menu item · Archive document | real action / Q1+U3 | Documents menu destinations (live) | `document-menu-destinations-2026-10-09/archived-after-menu-archive.png`; `document-menu-destinations-2026-10-09/journey.json` | Archive200 with the loaded If-Match revision navigates directly to the authenticated canonical detail. The archived detail GET confirms the same owned source and its back link preserves `?archived=true`; source/version identity and answer availability are recorded in the journey. |
| 17 | 117:611 Prototype · Documents · 05 Ready menu → 124:316 Prototype · Documents · 09 Deletion confirm | Menu item · Request deletion · Destructive | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local dialog) | `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | ArrowUp/Enter invokes Ready Request deletion to open the actual confirmation with Teacher Manh filename and enabled Cancel/Request deletion controls. Cancel and reopened Escape return focus to the Ready trigger. Confirm is never invoked. |
| 18 | 124:141 Prototype · Documents · 07 Ready detail → 117:344 Prototype · Documents · 03 List processing | ← Documents | real action / Q1+U3 | Documents live navigation (f9f6721), destination-state proof bounded | `document-navigation-2026-10-08/restored-list.png`; `document-navigation-2026-10-08/journey.json` | Actual Ready detail back link returns to the bare canonical list, unchecked archived filter and same source row. This proves the trigger/route; the prototype's processing-list composition is separately unproved and is not forced by navigation. |
| 19 | 124:141 Prototype · Documents · 07 Ready detail → 124:231 Prototype · Documents · 08 Archived detail | Button · Archive document | real action / Q1+U3 | owned document lifecycle (live) | `live-document-archived.png` | Actual owned document navigation/archive/restore observed through UI and backend responses. |
| 20 | 124:141 Prototype · Documents · 07 Ready detail → 124:316 Prototype · Documents · 09 Deletion confirm | Button · Request deletion | real action / Q1+U3 | owned document lifecycle (live); Document detail action height and cancellation {1440,390} (fixture local dialog) | `live-deletion-confirm-only.png`; `document-detail-action-height-2026-10-08/dialog-128-122-{1440,390}.png`; `document-detail-action-height-2026-10-08/journey-{1440,390}.json` | Prior live evidence retained. Actual Ready detail Request deletion opens the named dialog with enabled Cancel/confirmation; Cancel and reopened Escape return focus to its trigger. No deletion submission. |
| 21 | 124:231 Prototype · Documents · 08 Archived detail → 117:464 Prototype · Documents · 04 Show archived | ← Documents | real action / Q1+U3 | Documents live navigation (f9f6721) | `document-navigation-2026-10-08/journey.json`; `document-navigation-2026-10-08/archived-detail.png` | Actual Archived detail back link arrives at the exact list URL with archived=true. Show archived remains checked and the same owned archived source row is visible; URL preference does not grant scope or capability. |
| 22 | 124:231 Prototype · Documents · 08 Archived detail → 124:141 Prototype · Documents · 07 Ready detail | Button · Restore document | real action / Q1+U3 | owned document lifecycle (live) | `live-document-ready.png` | Actual owned document navigation/archive/restore observed through UI and backend responses. |
| 23 | 124:231 Prototype · Documents · 08 Archived detail → 124:316 Prototype · Documents · 09 Deletion confirm | Button · Request deletion | real action / Q1+U3 | Document detail action height and cancellation {1440,390} (fixture local dialog) | `document-detail-action-height-2026-10-08/dialog-128-125-{1440,390}.png`; `document-detail-action-height-2026-10-08/journey-{1440,390}.json` | Actual Archived detail Request deletion opens the named dialog with archived source status. Cancel and reopened Escape close it and return trigger focus. Fixture retains Teacher Manh filename rather than replacing runtime source data with the prototype Legacy handbook example; no lifecycle action or confirmation submission. |
| 24 | 117:758 Prototype · Documents · 06 Archived menu → 117:464 Prototype · Documents · 04 Show archived | More | real action / Q1+U3 | Documents local interactions {1440,390} (fixture keyboard equivalent) | `documents-local-interactions-2026-10-08/archived-menu-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Escape closes Archived menu and returns focus to its existing trigger. Equivalent keyboard close is exercised; the exact prototype More toggle is not clicked. |
| 25 | 117:758 Prototype · Documents · 06 Archived menu → 124:231 Prototype · Documents · 08 Archived detail | Menu item · View details | real action / Q1+U3 | Documents live navigation (f9f6721) | `document-navigation-2026-10-08/archived-menu.png`; `document-navigation-2026-10-08/archived-detail.png` | Actual Archived Actions menu toggles open/closed/reopened; View details opens the exact owned Archived URL. Authenticated source checks agree and the actual back link restores the checked archived list. |
| 26 | 117:758 Prototype · Documents · 06 Archived menu → 124:316 Prototype · Documents · 09 Deletion confirm | Menu item · Request deletion · Destructive | real action / Q1+U3 | Documents local interactions {1440,390} (fixture local dialog) | `documents-local-interactions-2026-10-08/archived-deletion-confirm-{1440,390}.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json` | Archived menu Request deletion opens the actual confirmation with Legacy handbook.pdf and an enabled confirmation control, then Cancel returns trigger focus. No request or physical deletion is submitted. |
| 27 | 117:758 Prototype · Documents · 06 Archived menu → 124:141 Prototype · Documents · 07 Ready detail | Menu item · Restore document | real action / Q1+U3 | Documents menu destinations (live) | `document-menu-destinations-2026-10-09/ready-after-menu-restore.png`; `document-menu-destinations-2026-10-09/journey.json` | Restore200 with the loaded If-Match revision navigates directly to the authenticated canonical detail. The Ready detail GET confirms the same owned source and its back link returns to the bare list; source/version identity and restored availability are recorded in the journey. |
| 28 | 124:316 Prototype · Documents · 09 Deletion confirm → 124:141 Prototype · Documents · 07 Ready detail | Button · Cancel deletion request | real action / Q1+U3 | owned document lifecycle (live); Documents local interactions {1440,390}; Document detail action height and cancellation {1440,390} (fixture local dialog) | `live-deletion-confirm-only.png`; `documents-local-interactions-2026-10-08/journey-{1440,390}.json`; `document-detail-action-height-2026-10-08/journey-{1440,390}.json` | Prior live and list-dialog evidence retained. New Ready detail Cancel returns to its actual Ready trigger; reopened Escape does likewise. Archived detail Cancel/Escape returns to Archived detail, preserving its projection rather than manufacturing a Ready destination. No deletion submitted. |
| 29 | 124:316 Prototype · Documents · 09 Deletion confirm → 124:424 Prototype · Documents · 10 Deletion requested | Button · Request deletion · Confirm | state display / Q1+U3 | V:128:131 (fixture); initial live diagnostic202 | `128-131-1440x960.png` | Requested projection fixture. Initial policy assumption409 was wrong: owned synthetic submission returned202; request retained, no retry/cleanup. This does not prove physical deletion or all-user policy. |
| 30 | 124:424 Prototype · Documents · 10 Deletion requested → 117:344 Prototype · Documents · 03 List processing | ← Documents | real action / Q1+U3 | V:128:120 (fixture visual only) | `128-120-1440x960.png` | Actual Documents components/source state captured; exact edge unexercised. Upload submission, processing and READY must remain separate backend observations. |
| 31 | 136:166 Prototype · Conversations · 01 New conversation → 136:290 Prototype · Conversations · 02 Question ready | Prompt · Report chapter count | real action / Q1+U2 | empty suggestions interaction (fixture) | `128-109-1440x960.png` | Suggestions edit draft and focus composer without submission; exact prototype prompt text differs. |
| 32 | 136:166 Prototype · Conversations · 01 New conversation → 136:666 Prototype · Conversations · B1 Unsupported question ready | Prompt · Late-submission policy | real action / Q1+U2 | empty suggestions interaction (fixture) | `128-109-1440x960.png` | Suggestions edit draft and focus composer without submission; exact prototype prompt text differs. |
| 33 | 136:166 Prototype · Conversations · 01 New conversation → 136:290 Prototype · Conversations · 02 Question ready | Composer input | real action / Q1+U2 | V:128:109 (fixture visual only) | `128-109-1440x960.png` | Composer is actual labelled input. Clicking/focusing does not manufacture a question or answer. |
| 34 | 136:290 Prototype · Conversations · 02 Question ready → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | owned Workspace restore and Conversation creation journey (live) | `conversation-creation-2026-10-08/created-from-draft.png`; `conversation-creation-2026-10-08/journey.json` | Actual composer contains an unsubmitted draft. New Conversation sends POST201 with an idempotency key, navigates to a different Conversation URL, and shows an empty composer. Destination GET200 confirms the new ID, same Workspace and archived=false. No source-example question/answer is fabricated. |
| 35 | 136:290 Prototype · Conversations · 02 Question ready → 136:414 Prototype · Conversations · 03 Retrieving evidence | Send | real action / Q1+U2 | owned Turn submission/lost-response recovery (live) | `live-lost-response.png` | Real POST accepted queued Turn; response delivery deliberately aborted after route.fetch reached backend. No response body substituted. |
| 36 | 136:414 Prototype · Conversations · 03 Retrieving evidence → 136:491 Prototype · Conversations · 04 Grounded answer | Prototype · Conversations · 03 Retrieving evidence | state display / Q1+U2 | existing owned queued Turn terminal proof (live) | `live-answer-evidence.png` | Controller guarded real runner processed exact owned Turn; real history answered/citation inspected. AFTER_TIMEOUT is illustration, not fixed product completion. |
| 37 | 136:414 Prototype · Conversations · 03 Retrieving evidence → 136:491 Prototype · Conversations · 04 Grounded answer | Prototype · Conversations · 03 Retrieving evidence | prototype-only simulation / Q1+U2 | V:128:110 (fixture visual only) | `128-110-1440x960.png` | Retrieving-frame click cannot force grounded answer; no such product action. |
| 38 | 136:414 Prototype · Conversations · 03 Retrieving evidence → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | `frontend/tests/conversation-view.test.tsx` retrieving case; live retained-outcome journey | `conversation-navigation-2026-10-09/` | The production control remains available while a Turn is retrieving and creation uses the same idempotent POST path; the live journey intentionally does not fabricate a pending backend Turn. |
| 39 | 136:414 Prototype · Conversations · 03 Retrieving evidence → 136:880 Prototype · Conversations · B3 Answer interrupted | Knora thinking | prototype-only simulation / Q1+U2 | V:128:118 (fixture visual only) | `128-118-1440x960.png` | Thinking click cannot force interruption. Controlled backend interruption requires its own evidence. |
| 40 | 136:491 Prototype · Conversations · 04 Grounded answer → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | live retained-answer/citation/refusal/draft journey (application) | `.superpowers/figma/q1/evidence/conversation-navigation-2026-10-09/{answer,citation}-created.png` | From the retained answered Turn, the real button POSTs201 with an idempotency key, navigates to a distinct active Conversation, and leaves the source history hash unchanged. |
| 41 | 136:491 Prototype · Conversations · 04 Grounded answer → 136:576 Prototype · Conversations · 05 Citation selected | Chip · [01] p.12 | real action / Q1+U2 | citation selection/focus interaction (fixture), actual answer inspector (live) | `live-answer-evidence.png` | Keyboard citation opens evidence; close returns focus; real returned source inspected. |
| 42 | 136:491 Prototype · Conversations · 04 Grounded answer → 136:576 Prototype · Conversations · 05 Citation selected | Chip · [02] Report structure | real action / Q1+U2 | citation selection/focus interaction (fixture), actual answer inspector (live) | `128-110-1440x960.png` | Fixture second citation renders; second-chip exact backend path not separately exercised. |
| 43 | 136:576 Prototype · Conversations · 05 Citation selected → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | live retained-answer/citation/refusal/draft journey (application) | `.superpowers/figma/q1/evidence/conversation-navigation-2026-10-09/citation-{before,created}.png` | A selected citation remains visible before creation; New Conversation creates a distinct empty destination and the source answer/citation history remains unchanged. |
| 44 | 136:576 Prototype · Conversations · 05 Citation selected → 136:491 Prototype · Conversations · 04 Grounded answer | Chip · [01] p.12 | real action / Q1+U2 | parity citation toggle/focus interaction (fixture); Turn-bound unit regression | `parity-citation-deselected.png` | Same Turn/index now clears selected inspector and pressed state on repeat. Mouse, Enter/Space and another Turn/index retain correct historical binding; panel preferences and unrelated panels remain intact. Actual prior answer inspector evidence is retained separately. |
| 45 | 136:666 Prototype · Conversations · B1 Unsupported question ready → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | `frontend/tests/conversation-view.test.tsx` draft/refusal cases; live retained-outcome journey | `conversation-navigation-2026-10-09/unsupported-draft-created.png` | An unsubmitted unsupported-question draft remains intact until New Conversation; the real creation path is covered, while the live journey does not invent a backend answer state. |
| 46 | 136:666 Prototype · Conversations · B1 Unsupported question ready → 136:790 Prototype · Conversations · B2 Insufficient evidence | Send | real action / Q1+U2 | existing owned unsupported Turn terminal verification (live) | `live-refusal.png` | Unsupported question submitted through actual composer; controller processed the exact retained Turn. Native UI now shows the authoritative REFUSAL/INSUFFICIENT_EVIDENCE projection with no citations after the diagnosed enum correction. |
| 47 | 136:790 Prototype · Conversations · B2 Insufficient evidence → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | live retained-answer/citation/refusal/draft journey (application) | `.superpowers/figma/q1/evidence/conversation-navigation-2026-10-09/refusal-{before,created}.png` | The authoritative refusal remains visible before creation; New Conversation creates a distinct active destination and keeps the refusal history unchanged. |
| 48 | 136:790 Prototype · Conversations · B2 Insufficient evidence → 136:290 Prototype · Conversations · 02 Question ready | Follow-up · Order | real action / Q1+U2 | empty suggestions interaction (fixture) | `128-109-1440x960.png` | Actual follow-up fills draft, not automatic submission; prototype Order copy differs. |
| 49 | 136:880 Prototype · Conversations · B3 Answer interrupted → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | `frontend/tests/conversation-view.test.tsx` interrupted case | `conversation-navigation-2026-10-09/` | The production control remains available while a Turn is interrupted and uses the same creation path; no HTTP interrupt command exists to create a live interrupted Turn for this journey. |
| 50 | 136:880 Prototype · Conversations · B3 Answer interrupted → 136:414 Prototype · Conversations · 03 Retrieving evidence | Action · Try again | real action / Q1+U2 | interrupted state V:128:118 and ConversationView recovery regression | `128-118-1440x960.png` | Actual Retry checks persisted history and restores the same draft. Native interrupted recovery remains unexercised: no HTTP interrupt command exists. The thinking-frame click is prototype-only; retry does not promise immediate retrieving state. |
| 51 | 136:965 Prototype · Conversations · B4 Archived read-only → 136:166 Prototype · Conversations · 01 New conversation | Button · New conversation | real action / Q1+U2 | owned Workspace restore and Conversation creation journey (live) | `conversation-creation-2026-10-08/created-from-archived.png`; `conversation-creation-2026-10-08/journey.json` | In an active Workspace, the actual New Conversation button creates and opens a distinct active Conversation; destination GET200 confirms ID and Workspace. A second GET confirms the source Conversation remains archived. While the Workspace itself is archived, the creation button is absent. Other answer/interruption starting states remain separately unexercised. |
| 52 | 136:965 Prototype · Conversations · B4 Archived read-only → 136:491 Prototype · Conversations · 04 Grounded answer | Button · Restore conversation | real action / Q1+U2 | owned Conversation lifecycle (live) | `live-conversation-restored.png` | Actual archive/read-only/restore returns to retained history; it does not create a new grounded answer. |
| 53 | 216:345 Prototype · Operator · 01 Operations → 216:448 Prototype · Operator · 02 Traces lookup | Tab · Traces | real action / Q1+O | figma-operator.spec.ts authorized five-state journey (live) | `operator-tab-journeys-2026-10-08/O2-lookup-live.png` | Actual tab navigation reaches empty Trace lookup, retaining the selected Workspace. Source visual parity remains open. |
| 54 | 216:345 Prototype · Operator · 01 Operations → 216:698 Prototype · Operator · 04 Evaluations lookup | Tab · Evaluations | real action / Q1+O | figma-operator.spec.ts edge-54 live | `operator-tab-journeys-2026-10-08/edge-54.png` | Operations opens the empty Evaluation lookup with the same authorized Workspace; report field and Open report are empty/disabled. |
| 55 | 216:448 Prototype · Operator · 02 Traces lookup → 216:345 Prototype · Operator · 01 Operations | Tab · Operations | real action / Q1+O | figma-operator.spec.ts edge-55 live | `operator-tab-journeys-2026-10-08/edge-55.png` | Empty Trace lookup returns to Operations and retains the selected Workspace. |
| 56 | 216:448 Prototype · Operator · 02 Traces lookup → 216:698 Prototype · Operator · 04 Evaluations lookup | Tab · Evaluations | real action / Q1+O | figma-operator.spec.ts edge-56 live | `operator-tab-journeys-2026-10-08/edge-56.png` | Empty Trace lookup opens empty Evaluation lookup; report field and Open report are empty/disabled. |
| 57 | 216:448 Prototype · Operator · 02 Traces lookup → 216:573 Prototype · Operator · 03 Trace detail | Button · Open trace | real action / Q1+O | figma-operator.spec.ts authorized five-state journey (live) | `operator-tab-journeys-2026-10-08/O2-detail-live.png` | Real trace lookup shows the actual ID, decision and ingested filename provenance. Source visual parity remains open. |
| 58 | 216:573 Prototype · Operator · 03 Trace detail → 216:345 Prototype · Operator · 01 Operations | Tab · Operations | real action / Q1+O | figma-operator.spec.ts edge-58 live | `operator-tab-journeys-2026-10-08/edge-58.png` | Real trace detail returns to Operations; the selected Workspace remains visible and no trace content is fabricated. |
| 59 | 216:573 Prototype · Operator · 03 Trace detail → 216:698 Prototype · Operator · 04 Evaluations lookup | Tab · Evaluations | real action / Q1+O | figma-operator.spec.ts edge-59 live | `operator-tab-journeys-2026-10-08/edge-59.png` | Reopened real Trace detail navigates to empty Evaluation lookup and retains the selected Workspace. |
| 60 | 216:698 Prototype · Operator · 04 Evaluations lookup → 216:345 Prototype · Operator · 01 Operations | Tab · Operations | real action / Q1+O | figma-operator.spec.ts edge-60 live | `operator-tab-journeys-2026-10-08/edge-60.png` | Empty Evaluation lookup returns to Operations and retains the selected Workspace. |
| 61 | 216:698 Prototype · Operator · 04 Evaluations lookup → 216:448 Prototype · Operator · 02 Traces lookup | Tab · Traces | real action / Q1+O | figma-operator.spec.ts edge-61 live | `operator-tab-journeys-2026-10-08/edge-61.png` | Empty Evaluation lookup opens empty Trace lookup; trace field and Open trace are empty/disabled. |
| 62 | 216:698 Prototype · Operator · 04 Evaluations lookup → 216:755 Prototype · Operator · 05 Evaluation unavailable | Button · Open report | real action / Q1+O | figma-operator.spec.ts authorized five-state journey (live) | `operator-tab-journeys-2026-10-08/O3-unavailable-live.png` | Real report lookup shows EVALUATION_REPORT_UNAVAILABLE and no download link; no persisted report is invented. |
| 63 | 216:755 Prototype · Operator · 05 Evaluation unavailable → 216:345 Prototype · Operator · 01 Operations | Tab · Operations | real action / Q1+O | figma-operator.spec.ts edge-63 live | `operator-tab-journeys-2026-10-08/edge-63.png` | The unavailable evaluation state returns to Operations through the real tab and retains the selected Workspace. |
| 64 | 216:755 Prototype · Operator · 05 Evaluation unavailable → 216:448 Prototype · Operator · 02 Traces lookup | Tab · Traces | real action / Q1+O | figma-operator.spec.ts edge-64 live | `operator-tab-journeys-2026-10-08/edge-64.png` | The unavailable evaluation state returns to empty Trace lookup; no trace content is fabricated. |
| 65 | 250:549 Prototype · Auth · A1 Sign in → 250:694 Prototype · Auth · R1 Forgot password | Forgot password action | real action / Q1+I1 | dedicated native OTP desktop/mobile journey | `.superpowers/sdd/2026-10-08-figma-otp-native-runtime/evidence/native-otp-runtime-2026-10-08/` | Native Keycloak recovery opened from the real sign-in flow in both viewports. |
| 66 | 250:549 Prototype · Auth · A1 Sign in → 250:1108 Prototype · Auth · A4 Signed in · Active workspace | Button · Sign in | real action / Q1+I1 | guarded native login → actual application journeys (live) | `live-document-ready.png` | Versioned owned synthetic identity authenticated; real resolver/application route reached. No plaintext credentials/action URLs captured. |
| 67 | 250:549 Prototype · Auth · A1 Sign in → 250:589 Prototype · Auth · A2 Create account | Auth secondary action | real action / Q1+I1 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native sign-in Create account reaches the real four-field registration form in both viewports. |
| 68 | 250:589 Prototype · Auth · A2 Create account → 250:1235 Prototype · Auth · A3 New account · No active workspace | Button · Create account | real action / Q1+I1 | V:152:128 (fixture visual only) | `152-128-1440x960.png` | Real registration remains conditional native authority. Prototype fresh NO_ACTIVE landing differs from canonical My Workspace ACTIVE; no-active source is separate state. |
| 69 | 250:589 Prototype · Auth · A2 Create account → 250:549 Prototype · Auth · A1 Sign in | Auth secondary action | real action / Q1+I1 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native registration Sign in returns to the real username/password form without creating an account. |
| 70 | 250:640 Prototype · Auth · E4 Registration validation error → 250:1235 Prototype · Auth · A3 New account · No active workspace | Button · Create account | real action / Q1+I1 | V:152:128 (fixture visual only) | `152-128-1440x960.png` | Real registration remains conditional native authority. Prototype fresh NO_ACTIVE landing differs from canonical My Workspace ACTIVE; no-active source is separate state. |
| 71 | 250:640 Prototype · Auth · E4 Registration validation error → 250:549 Prototype · Auth · A1 Sign in | Auth secondary action | real action / Q1+I1 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native registration validation remains on the registration form, then Sign in returns to the real login form. |
| 72 | 250:694 Prototype · Auth · R1 Forgot password → 250:723 Prototype · Auth · R2 Verify OTP | Button · Send verification code | real action / Q1+I2 | real Mailpit six-digit delivery in desktop/mobile journey | `native-otp-runtime-2026-10-08/empty-otp-{desktop1440x960,mobile390x844}.png` | Real native request delivered a six-digit OTP and rendered the verify form. |
| 73 | 250:694 Prototype · Auth · R1 Forgot password → 250:549 Prototype · Auth · A1 Sign in | Auth secondary action | real action / Q1+I2 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native email request Back to sign in returns to the real login form. |
| 74 | 250:723 Prototype · Auth · R2 Verify OTP → 250:801 Prototype · Auth · R3 Choose new password | Button · Verify code | real action / Q1+I2 | native correct-code → `#kc-passwd-update-form` | `native-otp-runtime-2026-10-08/native-password-{desktop1440x960,mobile390x844}.png` | Correct generation reached the native password form after malformed, wrong and previous-generation rejection. |
| 75 | 250:723 Prototype · Auth · R2 Verify OTP → 250:694 Prototype · Auth · R1 Forgot password | Use different email | real action / Q1+I2 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native verify form Use a different email returns to a blank email request form. |
| 76 | 250:761 Prototype · Auth · E5 OTP incorrect / expired → 250:801 Prototype · Auth · R3 Choose new password | Button · Verify code | real action / Q1+I2 | native rejected-code state followed by correct-generation verification | `native-otp-runtime-2026-10-08/rejected-otp-{desktop1440x960,mobile390x844}.png` | Wrong and prior-generation codes stayed on the native error state; the valid generation then advanced to password update. |
| 77 | 250:761 Prototype · Auth · E5 OTP incorrect / expired → 250:694 Prototype · Auth · R1 Forgot password | Use different email | real action / Q1+I2 | native identity secondary navigation desktop/mobile | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/native-otp/secondary-{desktop1440x960,mobile390x844}/` | Native rejected-code state Use a different email returns to a blank email request form. |
| 78 | 250:761 Prototype · Auth · E5 OTP incorrect / expired → 250:723 Prototype · Auth · R2 Verify OTP | Resend code | real action / Q1+I2 | native server cooldown, allowed resend, previous-generation rejection, and consumed replay terminal rejection | `native-otp-runtime-2026-10-08/` | Real Mailpit delivery and bounded service/runtime checks proved cooldown, resend generation rotation and rejection of the previous generation. A post-consume native replay returns HTTP 400 HTML with `#kc-error-message`/page-expired and no OTP form or redirect. Production outage hardening remains deferred. |
| 79 | 250:801 Prototype · Auth · R3 Choose new password → 250:841 Prototype · Auth · R4 Password reset success | Button · Reset password | real action / Q1+I2 | native policy/confirmation errors → strong password → completion info | `native-otp-runtime-2026-10-08/password-updated-login-{desktop1440x960,mobile390x844}.png` | Real native password policy and confirmation rejection preceded successful update and automatic fresh native sign-in. The green success notice is shown above the native form; the completion frame still retains production-native controls and differs from the prototype's exact geometry. |
| 80 | 250:841 Prototype · Auth · R4 Password reset success → 250:694 Prototype · Auth · R1 Forgot password | Forgot password action | real action / Q1+I3 | native test-mail password completion then Forgot Password (desktop) | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/identity/reset-success-forgot-password.png` | After real native password update, the green notice and native sign-in form appear; Forgot Password reaches the real email-request form. Verified in the nine-case identity suite; no second recovery request was sent. |
| 81 | 250:841 Prototype · Auth · R4 Password reset success → 250:1108 Prototype · Auth · A4 Signed in · Active workspace | Button · Sign in | real action / Q1+I3 | native completion → automatic fresh native login → exact Workspace | `native-otp-runtime-2026-10-08/result-{desktop1440x960,mobile390x844}.json` | The trusted completion link stamps only a short-lived per-tab cosmetic marker, then starts a fresh BFF `prompt=login` transaction. Application cookies are transferred only as an existing application session; fresh state/nonce/PKCE, old-password rejection, new password, TOTP (desktop) and exact Workspace were verified. Provider browser SSO cookie reuse is explicitly unverified. |
| 82 | 250:841 Prototype · Auth · R4 Password reset success → 250:589 Prototype · Auth · A2 Create account | Auth secondary action | real action / Q1+I3 | native reset-success → fresh login → registration desktop | `.superpowers/sdd/2026-10-09-figma-reset-success-native-login/evidence/identity/reset-success-create-account.png` | After automatic fresh sign-in, the native login Create account action reaches the real registration form; the completion info screen itself remains intentionally detached from authentication actions. |
| 83 | 250:884 Prototype · Auth · E1 Invalid credentials → 250:694 Prototype · Auth · R1 Forgot password | Forgot password action | real action / Q1+I1 | V:242:272 (fixture visual only) | `242-272-1440x960.png` | Actual FTL/AuthOutcome source presentation only; native result/edge remains unproved. No password/recovery/MFA/outage changes performed. |
| 84 | 250:884 Prototype · Auth · E1 Invalid credentials → 250:1108 Prototype · Auth · A4 Signed in · Active workspace | Button · Sign in | real action / Q1+I1 | V:128:109 (fixture visual only) | `128-109-1440x960.png` | Invalid credentials cannot advance merely on click; corrected real credentials required. Fixture error presentation does not prove server validation. |
| 85 | 250:924 Prototype · Auth · E2 Sign-in unavailable → 250:549 Prototype · Auth · A1 Sign in | Button · Try again | real action / Q1+I1 | V:228:212 (fixture visual only) | `228-212-1440x960.png` | Unavailable presentation only. Real outage retry prohibited/held; no artificial outage recovery acceptance. |
| 86 | 250:948 Prototype · Auth · E3 Authentication failed → 250:549 Prototype · Auth · A1 Sign in | Button · Try signing in again | real action / Q1+I1 | V:228:212 (fixture visual only) | `228-212-1440x960.png` | Actual FTL/AuthOutcome source presentation only; native result/edge remains unproved. No password/recovery/MFA/outage changes performed. |
| 87 | 250:972 Prototype · Auth · A5 Account menu → 250:1108 Prototype · Auth · A4 Signed in · Active workspace | Account avatar | real action / Q1+I1 | AccountMenu source capture V:228:424 | `228-424-1440x960.png` | Actual account trigger opens menu; focus/menu primitives preserved. Exact close-to-ACTIVE prototype edge is navigation illustration. |
| 88 | 250:972 Prototype · Auth · A5 Account menu → 250:549 Prototype · Auth · A1 Sign in | Button · Log out | real action / Q1+I1 | live account logout and forced sign-in {1440,390} | `live-logout-prompt-2026-10-08/journey-{1440,390}.json`; `live-logout-prompt-2026-10-08/fresh-sign-in-{1440,390}.png` | Enter invokes actual BFF POST303 and native Keycloak logout confirmation, then Signed out. Session GET200/null and protected Workspace GET401 verified; scoped panel preference cleared and unrelated key retained. Sign in then opens native password-empty form without automatic SSO callback. Natural expiry remains unproved. |
| 89 | 250:1108 Prototype · Auth · A4 Signed in · Active workspace → 250:972 Prototype · Auth · A5 Account menu | Account avatar | real action / Q1+I1 | live account logout and forced sign-in {1440,390} | `228-424-1440x960.png`; `live-logout-prompt-2026-10-08/account-menu-{1440,390}.png` | Actual subject-labelled account trigger opens Signed in/Log out menu after real native login and Workspace landing. Source trigger artwork and whole-frame parity remain open. |

## Responsive, accessibility and theme observations

- Eight actual compositions checked at1024×768,768×1024,390×844: conversation/evidence, upload, detail, Create workspace, three Operator views and OTP. Dialog fit and page horizontal overflow asserted; composer bottom remains within viewport. Mobile rail/evidence each open a single modal; Escape restores triggering focus.
- Divider keyboard arrows and Enter reset produce actual252px rail/376px inspector geometry. Create dialog Tab remains trapped; menu arrows/Escape preserve focus. Focus-visible outline2px measured.
- Real clipboard paste `000042` into maintained FTL input preserves leading zeroes with and without JS, and mirrors six cells when enhanced. Enhanced height56px/transparent text and no-JS visible labelled input are verified. Oct 7 actual offline FTL rendering at30s and0s verifies enabled native resend markup with preserved POST intent/formnovalidate and visible cooldown information. JS adds disabled countdown behavior immediately and enables resend at zero; the controlled clock checks29s/30s. Server cooldown/budgets remain authoritative. Source fixture submissions stay blocked, so these checks do not prove deployed early-request rejection or OTP recovery.
- Four actual production token pairs in light/dark meet4.5:1 text contrast; source muted/action foreground are intentional accessibility color differences. Reduced-motion removes actual control transitions (`0s`). This is sampled token coverage, not a complete page-wide contrast audit.
- CSS `zoom:2` reflows Document actions without page overflow; actual browser200% zoom UI is not independently proved. Dark captures exercise existing app preference; native FTL dark acceptance and Figma dark/mobile geometry references are absent.

## Remaining acceptance gaps

### Oct7 Operator prototype source and lookup guidance follow-up

Figma was reconnected on Oct7. Complete, non-sparse MCP structures and screenshots for216:345,
216:448,216:573,216:698 and216:755 are cached in
`.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/`, with a five-entry source index.
These are separate from the original51-state inventory, captures and comparison artifacts.
The two lookup prototypes are registered in a separate fixtureStates union for the guarded host.

| Source | Actual route/composition checked | Fresh captures and geometry | Observation |
| --- | --- | --- | --- |
| 216:448, guidance221:212 | Async `/operator/traces` route and real OperatorFrame/OperatorLookup/OperatorLookupGuidance fixture | `implemented-216-448-1440.png`, `implemented-216-448-390.png`, matching `-geometry.json` files | Exact heading/introduction/three items rendered; empty lookup disabled; optional Workspace override and encoded scoped navigation preserved. |
| 216:698, guidance221:227 | Async `/operator/evaluations` route and equivalent real feature fixture | `implemented-216-698-1440.png`, `implemented-216-698-390.png`, matching `-geometry.json` files | Exact persisted-data guidance rendered; empty lookup disabled; optional scope and encoded navigation preserved; no synthetic scores or report action. |

Both desktop sections measure1200×230 atx120/y441.6875, with columns360×112 atx120/540/960,
y533.6875 (60px gaps,92px from section top). Source geometry isx119/y434 and columnsy526:
the current unchanged surrounding page/form causes+1px horizontally and+7.6875px vertically.
The section's natural59px gap follows the source lookup-container bottom-to-guidance interval.
Source Roboto Slab18/600 heading, Inter14/20 introduction/body and Inter12/600 labels are checked.
Source per-item label offsets and340px body measure are retained; narrow text can grow naturally.
At390px sections are358px wide atx16 and496px tall; all three columns stack with24px gaps,
without horizontal overflow or clipped copy. No mobile Figma reference exists, so this is usability
verification rather than mobile source geometry acceptance.

`lookup-comparisons.html` shows each whole desktop source and implementation at the same1024px
display width, without cropping or replacing existing51 screenshots. Source initial example IDs
are not prefilled in production. Existing optional Workspace disclosure, empty disabled buttons,
accessible Workspace actions, smaller existing selector caret and accessibility-adjusted tokens
remain visible differences. Guidance has no static asset; the unchanged local18×18 brand and
existing fractional selector caret remain their production assets and callsites. Those surrounding
differences remain open. The other three prototype comparisons are now recorded individually below;
retrieving five sources and measuring five compositions does not accept five exact comparisons.

Two focused browser cases each run desktop1440×960 and mobile390×844, check encoded GET navigation
and Workspace query, then independently open the existing guarded trace/report observation fixture.
This proves client navigation/presentation, not backend authorization or a result for the synthetic
lookup ID. API requests are intercepted; unexpected requests fail and no API writes occur.
Actual RED/GREEN, final commands and runtime limits are recorded in
`.superpowers/sdd/2026-10-07-figma-operator-lookup-guidance/task-1-report.md`.

### Oct7 remaining Operator prototype comparisons — historical diagnosis, parity unresolved

Three individually named `Operator prototype comparison <id> <name> records desktop deviations and mobile fit` cases now compose the actual OperationsView, TraceView and EvaluationView at1440×960 and390×844. Separate fixtureStates contains56 entries; original visualStates remains51 and every original fixture/projection stays unchanged. Only the three new prototype states were captured. Their source PNGs remain1024×683 whole frames from1440×960 designs, with zero cropping. `remaining-operator-comparisons.html` displays source/current at the same720px width and links desktop/mobile geometry JSON.

| Prototype / route / test identity | Matching production content and fixture limits | Durable comparison evidence | Unresolved source differences and owning next action |
| --- | --- | --- | --- |
| 216:345 · Operations · `/operator/operations` | Actual configuration, observation, accounting, latency and Alerts sections; synthetic queue/cleanup zero, retry2.4%,18s/124/18.4s/1/32/zero accounting and four cumulative buckets. Orphan discoveries deliberately missing → Unavailable, independently of valid zeros. | `implemented-216-345-{1440,390}.png`; matching `-geometry.json`; whole-frame HTML | Source/current band1200×108→1200×110; accounting list148→147px; buckets760×92→760×86; Alerts380×70→380×69.1875. Selector inflation and section origins accumulate vertical drift; exact typeface/size matches do not establish exact geometry. Separate O implementation task must reconcile borders/box sizing/spacing and Alerts tone; missing signal and decimal bucket bound strings are explicitly fixture/presentation differences. |
| 216:573 · Trace detail · `/operator/traces/fixture-trace` | Synthetic typed ANSWER/VALID/184ms, two selected candidates with exact supplied excerpts, lines84–102/31–47, ranks1/2, fusion0.86/0.72, alias mappings, version/Chunk Set/embedding identities and184/612/24ms phases. Missing costs/usage/reason/branch contribution/lifecycle relation stay unavailable. | `implemented-216-573-{1440,390}.png`; matching `-geometry.json`; whole-frame HTML | Trace field360×34→360×36 and13→14px; button104×36→104.71875×40. Left column780→760, gap40→60 with right column still380px. Answer630×40→760×20 changes wrapping; candidates760×102→760×131.375 each, with added Retrieval details. Context row38→40, citation/timing headings22→24, validation timing falls below the960px desktop frame. Source badge rectangles differ from production icon/pill badges. Separate O plan must reconcile source slots/flow while preserving disclosures and backend provenance; synthetic IDs/E1/E2/ASCII line separators are data/presentation differences, not replacement backend facts. |
| 216:755 · Evaluation unavailable · `/operator/evaluations/fixture-report` | Exact unavailable heading/explanation and four report-context meanings. Synthetic report/Workspace IDs; no metrics, score, pass/fail result, download or fabricated available report. | `implemented-216-755-{1440,390}.png`; matching `-geometry.json`; whole-frame HTML | Button124×36→111.421875×40; unavailable badge92×28→96.046875×24.375 with warning icon/pill shape; explanation680×70→680×60; context heading24→32; first row40→41px; long observation code wraps inside its constrained column while source grants300px past the380px context column. Separate O implementation plan must resolve lookup/badge/row geometry without copying source overflow or inventing a Workspace name/report. |

Shared observed differences: source root/navigation border model places navigation at(1,1), current at(0,0); source content is declared atx120 for Operations or119 for trace/evaluation andy44 inside the896px body following64px navigation. Geometry JSON reconstructs global coordinates with the1px outer border and retains that coordinate model; source `normal` text line heights do not specify exact ink bounds. Current content x120; Workspace selector rowy126,height29.6875 versus source reconstructed y127,height26; its extra28.109375×29.6875 Workspace actions control is retained. Source Workspace label11px differs from current10px. Current titley169.6875 versus source167; navigationy263.6875,height43 versus source260,height42. All four signals have300px columns. Supplied display/body families and named sizes agree where measured, but muted source#657a74/#5e736b remains accessible semantic#546b63; Alerts soft color and status palettes also differ. Optional exact Workspace disclosure, retrieval details, M4 lifecycle evidence, Additional provenance and Provider accounting remain supported production affordances; no source authorizes removing them.

The original local leaf asset (`ad252.svg` → `/brand/knora-leaf.svg`, SHA256`FDA63DFBB12011B92EB338979D40482A202F6486D07231D339D42DCE778B72B3`) loads at18×18, current slot(24,22.5). Source selector requires Operations`a4e11.svg`10×6 or trace/evaluation`bab86.svg`10×5 slot with11.4×6.4 wrapper. Current active selector uses`21b31.svg`6.984375×4.484375 at(267.25,138.859375), SHA256`9C8D9FCEEF740FD3EB8511F7D2C6223318DE2850A7B513A4288B499BD5F1C0E0`. This is an unresolved asset/slot mismatch; the source asset policy does not treat it as exact parity. Exact local source asset reuse belongs in the separate production plan.

All measured mismatches are explicit source/current/delta/classification records, without tolerances or an accepted-parity result. The report includes the exhaustive measured mismatch table and visual copy/control/shape observations. API doubles allow only the three states' exact Workspace hydration GET; every other path/method fails. No API writes occurred. Expanded provenance assertions run after closed-composition captures. Mobile section/body copy fits with no horizontal page/text overflow; no mobile Figma source exists, so mobile checks prove readable adaptation only. Visual QA records awkward within-word wrapping of the Operations Unavailable signal and first trace SELECTED badge at390px; all characters remain present, and this readability refinement belongs in the subsequent production plan. All225 pre-existing source, capture, geometry and comparison artifacts (including original51 and prior lookups) retain their hashes. Exact commands, source/output hashes and remaining action are recorded in `.superpowers/sdd/2026-10-07-figma-operator-prototype-comparisons/task-1-report.md`.

Native reset/provider/Vault/MFA/outage and native CSP/browser-flow proof remain held. Existing I1 native login/registration evidence is recorded in `.superpowers/sdd/2026-10-05-figma-ui-identity/task-1-report.md`; it is prior evidence for those unchanged behaviors, not a new Q1 registration or logout run. Oct8 bounded real account journeys now prove live logout and forced sign-in at1440/390; the native mobile restart-login tooltip was corrected to stay within390px and both viewport journeys now assert no horizontal overflow. Natural expiry and reset completion remain unproved. I3 completion configured-port/bracket-IPv6 defects are corrected in the actual offline template; configured-host trust, DNS/IDNA, deployed configuration and service reachability remain unverified. All five fresh Operator prototype contexts were retrieved and all five now have named composition comparisons; source parity acceptance remains open for the recorded deviations. Per-edge unexercised paths are retained above, and these three fixture cases do not close the Q2 full-regression gap. Exact geometry acceptance remains open for native copy/hierarchy differences, extra accessible navigation/panel controls and backend-derived content. The Oct 7 follow-ups resolve citation toggle, the bottom Workspace restore affordance, the W5A inspector notice and the no-JS resend defect; the W5A unselected retained-answer context now has its source 96px minimum, 340px desktop width and 14px following-notice gap; remaining answer/citation/extra-control differences and existing inspector origin offsets remain recorded. No production fixture routes or new baseline images were committed.

### Historical diagnosis resolved by the Oct 7 Conversation parity follow-up

Q1 originally diagnosed edge 44 through `TurnCard.tsx` → direct `setSelection` in ConversationView. The approved follow-up replaces that assignment with a functional comparison of Turn ID and citation index, clearing only the repeated selection. It also supplies the validated Workspace revision through both server routes and the shared bottom restore composer. Fresh proof and remaining limits are in `.superpowers/sdd/2026-10-07-figma-conversation-parity/task-1-report.md`; the earlier Q1 report remains a historical observation rather than current unresolved status for these two behaviors.

The subsequent archived evidence notice task passes the same authoritative Workspace archive flag to the actual inspector in detail and Hub. Its independent notice does not replace evidence or add a restore action. Current W5A-only comparison and desktop/mobile selected-source checks are recorded in `.superpowers/sdd/2026-10-07-figma-archived-evidence-notice/task-1-report.md`.

The retained context follow-up uses only that archive projection, an existing ANSWER result and
absence of citation selection to apply the 96px minimum. Actual desktop geometry is 340×96 at
x1083/y210.5; notice 340×82 at x1083/y320.5, gap 14. The cached source's border/content flow starts
about 1px farther right and 1.5px higher; this bounded task does not accept full-screen origin parity.
At 390×844, the context is 298×111.5 and notice 298×91, with 14px separation and all text inside
the cards without horizontal overflow. Selected historical excerpt retains 146px minimum with
its exact version, provenance and Open document link. The real link GET/URL is checked, followed
by the existing guarded detail fixture selected through its explicit state query; that second
observation does not prove production routing or backend authorization. Source requests remain
intercepted and the new cases observe no API writes. Only W5A was recaptured and its comparison
and workspace sheet rebuilt; other 50 captures/comparisons and all 51 source PNG/full MCP structures
have unchanged hashes. Evidence, initial navigation-harness failure and exact commands are in
`.superpowers/sdd/2026-10-07-figma-archived-inspector-context/task-1-report.md`.

The OTP resend fallback task removes permanent server-rendered disabled markup, preserving the existing native POST and server protocol. It re-exports actual FTL with the existing offline renderer and runs only the two affected OTP interactions. Only the changed no-JS rendering is captured; existing JS source comparisons and full MCP structures remain unchanged. RED/GREEN commands and runtime limits are recorded in `.superpowers/sdd/2026-10-07-figma-otp-resend-fallback/task-1-report.md`.

The completion origin correction validates ordinary expanded/compressed bracketed IPv6 and optional one-to-five-digit ports up to 65535, including syntactic port 0. Actual `info.ftl` RED/GREEN verifies fail-closed rejection of seven malformed port/IPv6 configurations, preserves valid configured origins at the fixed `/api/auth/login?prompt=login` route without configured path/query/fragment or native action parameters, and retains unfinished native links and `skipLink` suppression. The existing ASCII hostname branch is unchanged; IPv4-embedded IPv6 and zone identifiers are outside this grammar. Configured-host trust, DNS/IDNA, deployed configuration and service reachability are separate acceptance limits. No visual baseline was changed or capture rerun. Commands and source-only evidence are recorded in `.superpowers/sdd/2026-10-07-figma-completion-origin-validation/task-1-report.md`.

### Oct7 Operator geometry correction — current measured status

The approved geometry task supersedes the addressed measurements in the historical comparison
notes above. Five affected prototypes were recaptured at1440×960 and390×844 using actual
production components, with scoped API interception and no writes. Source structures and PNGs
remain unchanged. Full-frame parity, native acceptance and full-regression acceptance remain open.

| Owning component | Corrected source geometry | Preserved behavior and remaining differences |
| --- | --- | --- |
| OperatorFrame / WorkspaceSelector | Selector220×26; retained Workspace actions trigger26px high. Operations uses exact local a4e11 in10×6; trace/evaluation use exact local bab86 root11.4×6.4 in10×5 with declared−0.7px inset. | Optional presentation is consumed only by OperatorFrame. Default consumers retain21b31/23c31 and archived a4e11 behavior; open menu, archive/create/restore navigation and backend authority remain intact. Chromium intrinsic layout quantizes bab86 to11.375×6.390625 and inset−0.6875; no root size overrides. Source fixed caret position and current natural-name positioning still differ. |
| OperatorLookup | Trace field360×34/13px, report field360×36/14px; trace button104×36, report124×36. | Pending text may grow. Empty lookup, exact encoded IDs, optional Workspace scope and refresh/navigation behavior remain intact. Current trace input y340/button y339 versus source global y338; report field/button y339 versus338. |
| OperationsView | Runtime band1200×108 including borders; mobile358×214 with179px cells. | Actual Unavailable stays complete on one line at390px: text range148.140625px inside166px value box, with visible natural overflow and text inside the cell. Zero/missing distinction is retained. Accounting147 versus source148px, buckets86 versus92px, Alerts69.1875 versus70px, token tone and origins remain unresolved. |
| TraceView | Left780/right380/gap40; answer630×40. SELECTED remains one complete word at390px while the surrounding source-name row wraps. | Candidate excerpts, full source names, IDs, version/Chunk Set metadata, extra disclosures and timing remain. Candidate rows grow naturally to131.375px and780px width versus source102px/760px; context rows40 versus38px, heading heights24 versus22px, icon/pill badges and page coordinates remain unresolved. Validation timing y954.140625 extends below the960px viewport and is reachable by natural scroll. |
| EvaluationView | Unavailable badge92×28/radius8, warning tone and text preserved; decorative icon hidden locally. | Available/other observations retain existing semantics. Explanation680×60 versus source680×70, context heading32 versus24px, first row41 versus40px and origins remain unresolved. Full opaque observation code wraps at200px rather than copying source300px extending past the380px column. |

Current shared desktop selector is atx120/y126 versus reconstructed sourcey127; titley166 versus167;
navigationy260/height43 versus sourcey260/height42; Workspace label10px versus source11px.
Lookup guidance now starts atx120/y434, with360px columns atx120/540/960 andy526. The source's
local x119/y434 becomes global x120/y435 after its1px outer border. Accessible Workspace actions,
optional scope, provenance disclosures, data-derived IDs/E1/E2/ASCII separators and semantic
contrast tokens remain deliberate visible differences. No source comparison is accepted as complete.

Exact bab86 bytes are331bytes, SHA256
`864C1D2BB9B35ED4DD76DEE4346A2BF2BAE674A2B8E74EFBE6138A1651949911`.
The unchanged brand loads18×18. Fresh `correctedGeometry` records include root metadata,
callsite/slot/rendered geometry and actual text-range fit. The five affected captures/JSONs and two
comparison HTMLs are refreshed;239 other Q1 cached artifacts retain their recorded hashes,
including the original51-state captures/comparisons and source/hash manifests. Active root-owned
regression-preflight logs are excluded from this preservation inventory. Exact RED/GREEN commands,
remaining limits and preservation proof are in
`.superpowers/sdd/2026-10-07-figma-operator-geometry-corrections/task-1-report.md`.

### Oct7 Operator typography and Trace badges — current measured status

The owning selector presentation now renders the Workspace label at Inter11px/600 on all five
Operator prototypes. Default consumers and the open popup retain10px; actions and source caret
slots retain the preceding geometry correction. Trace lookup remains13px/34px high and report
lookup14px/36px high.

Trace detail reuses StatusBadge locally: ANSWER source216:637 is110×28/radius7, and SELECTED
source216:644/651 is150×28/radius7. Both render Inter12px/600 with10px left padding and a16px
text region centered6px from the top. Decorative icons are hidden only in those named states;
semantic success tone and the complete backend label remain. Other observed decisions and
candidate outcomes retain their existing warning/info meanings and can grow and wrap naturally.
At390px SELECTED stays a whole word, with the source-name row wrapping and no page overflow.

The five affected desktop/mobile captures, geometry JSONs and two comparison HTMLs are refreshed.
The existing `correctedGeometry.workspaceLabel` and `correctedGeometry.traceBadges` records contain
effective type, shape, text alignment, icon visibility and fit; descriptive `measurements` still
record exact source/current deviations without a parity waiver.239 unrelated cached Q1 artifacts,
including original51 source/capture/comparison evidence, retain their hashes; only active root-owned
regression-preflight logs are excluded from the preservation inventory.

Remaining differences include page origins/margins, candidate source-name measure and natural
row growth, additional supported controls/disclosures, source data versus runtime IDs/citations,
and accessible semantic contrast tokens. Validation timing remains reachable through natural
scroll. These focused fixture checks do not accept whole-page geometry, backend authorization,
native identity flows or full regression qualification. Exact RED/GREEN, preservation proof and
residuals are in `.superpowers/sdd/2026-10-07-figma-operator-type-and-badges/task-1-report.md`.

### Oct7 Trace internal content measures — current measured status

The bounded Trace follow-up supersedes the addressed summary, candidate-width and context measures
above. Complete source 216:573 remains authoritative. At 1440×960 the summary is 1200×84 including
both borders; its four 300×82 cells have 13px/17px labels at relative top 15 and 22px/26px values at 39.
The existing 780/380 columns and 40px gap remain. The result row and candidates now use 760px inner
measures, placing the 110px ANSWER badge 650px from the column origin. Candidate descriptions use
730px; complete source names have a 420px maximum. The answer remains 630×40.

All four desktop context rows measure 380×38 with 13px/17px text, 170px label/200px value/10px gap
and text top 7px. Citation mapping and Phase timing headings are 18px/22px; Trace context retains
20px/24px. These are minimums and responsive maximums: full IDs, configurations, excerpts,
aliases, mapped sources, unavailable observations and disclosures remain readable through natural
growth. Actual zero timing/contributions retain zero, independently of unavailable values.

Remaining global differences are recorded in the desktop JSON: summary source y425/current429;
detail columns 533/537; answer 567/573; candidate heading 659/667; first candidate 723/715 and second
833/850. Both candidate rows are 135px high versus source 102, retaining Retrieval details. Context
starts 567/571; citation heading 738/743; phase heading 851/869; validation row 927/943 and ends 969,
below the 960px frame. Columns naturally grow to 500px versus source 420. Summary text boxes are
263px versus source 264px under the retained cell border model. Added Workspace controls,
optional scope, provenance/accounting/lifecycle disclosures, runtime IDs/E1/E2/ASCII separators,
accessible semantic contrast and surrounding origins remain visible differences. No data is omitted
to fit the supplied frame, and whole-page parity remains open.

At 390px the 358×166 summary stacks two 179×82 cells per row; candidates are 358px wide with natural
170.25/153px heights, and context rows stack to 65px. SELECTED stays one whole word, all provenance
is inspectable, and both closed and expanded content have no horizontal overflow. No mobile Figma
source exists, so this proves readable adaptation only. Guarded actual-component fixtures allow
only Workspace hydration GETs, preserve prior lookup/navigation and selector/asset/badge geometry,
and observe no unexpected requests or API writes; they do not prove backend authorization.

Only the two Trace PNGs and two matching geometry JSONs changed. The combined Operator HTML was
regenerated and remains byte-identical while referencing the updated captures. All 257 other
inventoried Q1 artifacts retain hashes, including all 16 capture/JSON artifacts for the other four
Operator cases and all original 51 source/capture/comparison artifacts. Active root-owned
regression-preflight logs are excluded. Exhaustive source/current residuals remain in
`implemented-216-573-{1440,390}-geometry.json` under the Operator prototype evidence cache.
Preserved RED/GREEN logs, final formatting/type checks, retention manifests and self-review are in
`.superpowers/sdd/2026-10-07-figma-trace-content-measures/task-1-report.md`.
Native identity, full regression and full-goal acceptance remain open.

### Oct8 Evaluation relative content measures — current measured status

The bounded Evaluation follow-up uses complete source 216:755, specifically 216:794–811.
Report context now has a 22px/24px title, with the first context text starting 44px below the
title top. Desktop rows retain the 170px label/200px value/10px gap split. A 24px text region,
10px top padding, 5px bottom padding and 1px divider give a 40px minimum row: the divider begins
29px after the text starts, followed by its 1px thickness and 10px before the next text region.
The complete opaque observation code wraps inside the column and grows its row to 64px; the
source's 300px value region extending outside its 380px context column is not reproduced.

The explanation retains the complete contract copy and 16px/20px type at a 680px maximum,
with a 70px minimum allocation. Its desktop top is 44px below the existing 26px/32px main
heading; the local 12px gap accounts for the unchanged 28px badge centered within that heading
row. No fixed height clips longer content. At 390px the explanation is 358×100 and context rows
stack to 358×74; the title/badge flex row grows naturally. Full report and Workspace IDs,
available/unavailable/failure semantics and missing-observation defensive fallback remain
inspectable. Undefined observation fields in the defensive component case are explicitly
out of contract; the generated schema still requires strings.

Absolute origins remain unresolved: desktop heading/context source y409 versus current411,
explanation453/455, first context text453/455 and observation text573/575. The historical
`report context row` measurement compares source text start453 against CSS container top445;
the named `correctedGeometry.evaluationContent` regions record the actual text top455 and
the 40px flow interval. Badge source x503/y412 versus current486.21875/413 remains a natural
title-width/alignment difference. Semantic contrast, exact runtime IDs instead of illustrative
display values, extra Workspace controls and optional scope remain visible differences.
No mobile Figma source exists, so mobile evidence proves readable adaptation only.

Actual-browser RED failed on the intended measures before implementation; focused Evaluation
GREEN and all five existing Operator/guidance cases passed at both sizes with no writes or
unexpected API requests. All 36 component checks and final format, format:check and typecheck
passed. Only the two Evaluation PNGs and two geometry JSONs changed; all 257 other inventoried
Q1 artifacts, including the other four Operator cases' 16 outputs and original 51-state evidence,
retain their hashes. Combined Operator HTML was regenerated and remains byte-identical. Root
active regression-preflight logs are excluded. Details, initial test-only typecheck recovery,
visual QA and residual JSON links are in
`.superpowers/sdd/2026-10-08-figma-evaluation-content-measures/task-1-report.md`.
Whole-page parity, native identity and full-regression acceptance remain open (`parityAccepted:false`).

### Oct8 Operations relative content measures — current measured status

Complete cached source 216:345, especially 216:401–447, remains authoritative. Desktop accounting
now allocates 1200×148: six 580×49 rows at local x0/600 and y0/49/98, with 20px column gap,
20px right inset and one trailing pixel. The rows retain their divider and natural 14px top /
14px bottom padding around a 14px/20px text region; values start 420px into each row. The extra
container pixel does not stretch rows or create another divider.

Buckets now allocate 760×92: four 370×40 rows at local x0/390 and y0/46, with 20px column gap,
6px row gap and 6px trailing allocation. Each row has 10px top / 9px bottom padding and its 1px
divider. Labels and semibold values use 13px/20px regions; the value slot starts at310px and
has a natural60px minimum, growing for complete longer values. Every valid supplied bucket is
retained; source decimal spellings remain illustrative rather than replacing runtime formatting.
Accounting and bucket rows use minimum heights and naturally grow when text wraps.

Alerts now has a70px minimum and8px radius, with14px left padding,11px/15px semibold label
at local y12 and13px/20px body at y35, following an8px gap. The exact unavailable statement
and role=status remain. The theme-aware semantic color mix is unchanged: source light#f4eae6
versus current `color(srgb 0.947059 0.92549 0.919216)` remains a shared-token residual; geometry
correction does not accept that tone. Accessible semantic text colors also remain distinct.

Desktop accounting source x121/y619 versus current120/622, buckets121/857 versus120/858 and
Alerts941/857 versus940/858 remain absolute-origin differences. Runtime band remains1200×108
and mobile Unavailable is a complete readable word. At390px accounting is358×294 with six
single-column49px rows; buckets358×178 with four40px rows and6px gaps; Alerts358×70. Full
observations remain readable with no horizontal overflow. Mobile has no supplied Figma source
and records responsive adaptation only. Exhaustive residuals and text-region measurements are
in [desktop JSON](../../.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/implemented-216-345-1440-geometry.json)
and [mobile JSON](../../.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/implemented-216-345-390-geometry.json);
[whole-frame comparison](../../.superpowers/figma/q1/evidence/operator-prototypes-2026-10-07/remaining-operator-comparisons.html)
retains uncropped source/current frames.

Actual-browser RED caught allocation, bucket text-slot and Alerts region mismatches. Focused
Operations GREEN passed both sizes. The five-case run passed the other four Operator/guidance
cases and exposed a pre-existing header lazy-image readiness race in Operations; a bounded
test-only readiness wait preserves the loaded-asset assertion and focused Operations recovery
passed. Those four passing cases were not repeated. All46 relevant component checks and final
format, format:check and typecheck passed. Only Operations' two PNGs/two JSONs changed; all257
other Q1 artifacts retain hashes, including the other four Operator cases'16 outputs and all
original51 source/capture/reference artifacts. The full261-entry audit excludes only root active
regression-preflight logs; its42 files outside the initial evidence-directory snapshot explicitly
use the prior verified Evaluation baseline. Combined Operator HTML regenerated byte-identically.
Commands, race diagnosis, hashes and limits are recorded in
`.superpowers/sdd/2026-10-08-figma-operations-content-measures/task-1-report.md`.
Whole-page, native identity and full-goal acceptance remain open.

### Oct8 shared Operator frame flow — current measured status

Fresh complete MCP 216:467 and the five retained prototype structures supply the frame coordinates.
The local main now starts at global y109 under the unchanged 64px header. Relative to the Workspace
label origin, all five desktop compositions allocate selector top18/height26, title top58/height42,
description top105, navigation top151/height42, and a separate decorative divider top193/height1.
Trace/Operations descriptions use natural 19px lines; Evaluation uses 24px. The Trace description
retains its source 870px maximum. Chromium text ink is 20px in the 19px region (mobile58px ink in
57px allocation); visible overflow and measured parent/navigation clearance preserve the full copy.

Tabs retain source minimum widths76/50/82 and offsets0/104/182 with28px gaps,27px allocation,
and the2px underline at local25. Operations labels use17px at top0 with8px trailing gap;
Trace labels use17px at top5 with3px gap. Evaluation preserves20px at top5, no gap,400 inactive /
500 active weights; Operations/Trace preserve500 inactive /600 active. These minimum slots grow
for text, and navigation can wrap without clipping links.

Lookup starts at relative211 after the divider's17px gap. Its natural13px label and5px control gap
put both field and button at relative229/global338, including the34px Trace input beside its36px
button. The56px minimum keeps the source's trailing2px allocation and moves guidance to global435,
with unchanged360px columns at global527 (92px internal offset). Report labels preserve source500
weight. Evaluation source24px label allocation overlaps its controls by6px; the retained13px natural
region is an explicit overlap-avoidance adaptation, not exact label-allocation parity.

At390×844, full descriptions grow to57px (Trace/Operations) or48px (Evaluation); lookup grows to124px
or126px as controls wrap and optional Workspace disclosure enters normal flow. Existing scope,
same-ID refresh, menu/keyboard, default-selector and complete evidence behaviors remain covered.
The five browser cases prove readable adaptation and exact selected desktop measures only.

The shared header/artboard border model remains distinct: source header x1/y1 versus production0/0,
and Operations content x121 versus production120. Workspace label source13px versus retained12px,
semantic contrast colors, runtime formatting, natural backend-derived wrapping, extra Workspace
actions/scope/provenance controls and previously recorded per-view origins remain residuals.
Whole-page parity, backend authority, native identity/outage and full-goal acceptance remain open.

All five affected desktop/mobile PNGs and matching JSONs were refreshed; both comparison HTMLs were
regenerated byte-identically. Of263 inventoried Q1 artifacts,243 retain hashes, including original51
evidence, native files, all five old source structures/renders and fresh216:467 structure/render.
Only root active regression-preflight logs are excluded. Browser RED failed all five; GREEN passed
both Evaluation cases, then a test-only ink/allocation correction passed the remaining three.
Thirteen focused component checks passed. Final format→format:check→typecheck evidence and the
source position map are in `.superpowers/sdd/2026-10-08-figma-operator-frame-flow/task-1-report.md`.

### Oct8 Trace result and candidate flow — current measured status

Complete fresh direct MCP216:635 and its returned uncropped render supply the result/candidate
slots; complete216:573 remains the whole-frame comparison source. Relative to the desktop detail
column, Observed result allocates top0/height24 beside a28px decision badge. The two-line answer
starts34 with40px height/630px maximum, citations start82 with24px minimum and16px text lines,
and provenance starts126 with24px heading. Its description starts156 with18px lines/730px maximum;
the candidate list starts190 after16px. The result heading's26px glyph ink is recorded separately
from its24px line allocation; visible overflow retains the complete glyphs.

Both desktop candidate rows allocate760×128. Their name starts7 with20px lines/420px maximum;
selected badge starts4 with150×28; metadata starts33 with17px minimum/16px lines;
excerpt starts60 with20px minimum/18px lines/610px maximum. Retrieval details starts88 with18px
natural lines and8px margin after the excerpt. Retaining this existing disclosure adds26px to the
source's clipped102px row;21px trailing space plus the divider remain. The second candidate starts
326, following actual prior height+8 rather than source300. All IDs, versions, sets, fusion, reasons
and vector/full-text contributions remain inspectable. No dynamic content is replaced with source
sample text, and no outer420px or page960px height clamp is introduced.

Citations retain actual E1/E2 aliases, all supplied markers and unavailable semantics; their pills
have38×22 minimums and medium labels, grow for longer values, and wrap naturally. The source's
[01]/[02] spellings and200px clipped region do not replace the typed observation. Existing semantic
theme tokens and contrast colors remain; source color parity is not accepted by this geometry work.
The detail column remains global538 versus source533; the answer now572 versus source567. Whole-page
absolute parity and added lifecycle/provider/provenance controls remain open.

At390×844, the answer grows to60px and the description to54px. Candidate list starts relative246;
rows grow naturally to163/144px, with second top417. Keyboard-expanded candidate rows grow to618/599px
(desktop394px each), show full persisted values, and close/reopen correctly. Both collapsed and
expanded states have no horizontal overflow; collapsed PNGs are captured before expanding details.
Mobile has no supplied Figma source and proves readable adaptation only.

Actual-browser geometry RED failed on the intended measures; the focused Trace comparison GREEN
passed both sizes with previous summary/context/badge/frame checks intact. Twenty-four focused
component preservation checks passed; three affected checks also passed after a test-only numeric
fixture correction. Final format→format:check→typecheck passed after documented test-only recovery.
Only Trace's two PNGs/two JSONs changed across266 Q1 artifacts;262 retain hashes, including original51,
native evidence, all source structures/renders and fresh216:635 MD/PNG/render-base64. Combined Operator
HTML regenerated byte-identically; lookup HTML remains byte-identical. Only root active
regression-preflight logs are excluded. Full source map, RED/GREEN logs, artifact proof and recovery
details are in `.superpowers/sdd/2026-10-08-figma-trace-result-candidate-flow/task-1-report.md`.
Fixture measurements make no backend/native identity or whole-design acceptance claim; parity remains
unaccepted. Independent review is owned by the controller.

### Oct8 reset presentation — current measured status

Fresh complete direct MCP 242:272, 242:333, 242:389 and 246:311 supplies the reset request,
verification, ordinary new-password and generic-error labels. Request copy now says “Forgot your
password?”, “Send verification code” and “Remembered it?”. Ordinary password actions say “Choose
a new password”, “Confirm new password” and “Reset password”, followed by the source instruction
to sign in with the new password. Native app-initiated Submit/Cancel and logout-other-sessions
remain. The return instruction describes the next step and is not native completion evidence.

OTP copy keeps “If an account exists” and an escaped runtime masked address. Actual five-minute
expiry and generic error copy remain because provider failures can also represent budgets or
storage. The source sample address, unconditional sent assertion and incorrect/expired-only
failure statement are not substituted for runtime outcomes.

Server retry seconds render zero-padded minutes:seconds (30 → 00:30, 61 → 01:01); zero renders
only “Resend code”. The enhancement reads numeric data-seconds, uses the existing Date-based
250ms timer and restores the localized ready label/removes the countdown at zero. Server markup
keeps an enabled native resend POST for the existing no-JavaScript fallback; admission remains
server-owned. Accessible single-code input, leading-zero paste, six mirror cells, native intent
values, action URLs and formnovalidate remain.

Focused actual-parent FreeMarker and browser evidence is recorded in
`.superpowers/sdd/2026-10-08-figma-reset-presentation/task-1-report.md`. New current captures use
the separate `reset-presentation-2026-10-08` Q1 evidence directory; historical captures remain.
Labels/countdown verification does not accept shared CSS, content origin, field/notice geometry,
whole-page parity or responsive source parity. Native recovery binding and live reset remain held.

The bounded offline renderer now extracts only the referenced pinned 698-byte base password
visibility module, after exact hash verification, and uses the native password page ID for the
ordinary password fixture. Both empty password fields toggle password → text → password and
retain the exact 18px source eye asset. The exporter also regenerates the success HTML from
current accepted `info.ftl`: its prior cached copy predated the earlier completion-origin
validation and differs only in CTA whitespace (4491 → 4494 bytes). Exact historical bytes/hash
are reproduced separately in the SDD report evidence; historical PNGs stay unchanged. This
additional export difference makes no new completion or native recovery claim.

### Oct8 OTP input presentation — local allocation and empty marks

Cached complete direct MCP242:333/246:311 structures and renders map the OTP wrapper to
246:292/363:420×56, with six54×56 cells,10px gaps and a centered374px inner row. Existing
native CSS now uses the420px wrapper and centered bounded grid. Empty decorative cells show
the source22px semibold em dash using the existing semantic muted token. The true labelled
text/numeric input stays authoritative; the aria-hidden mirrors contain no placeholder text.

Focused browser RED failed on374px allocation, missing23px inset and absent muted marks.
GREEN proves normal/error at1440×960 and390×844, one56px input, unchanged required/pattern/
length/autocomplete/ARIA, real clipboard000042 and focus, no pseudo marks on populated cells,
and six marks after clearing. Desktop wrapper origins are830/287 and830/370 with cells at853;
at390px the available342px wrapper holds approximately48.67px cells and no horizontal overflow.
Mobile proves readable adaptation only; the source supplies no mobile geometry.

The wrapper correction does not accept the whole content origin or shared notice/type geometry.
Privacy adds a description line; the error remains generic, expiry stays the actual five minutes,
and native input focus/error outlines remain visible. The source error sample234567 is never
hardcoded; marks and digits reflect the empty/entered input. Existing semantic muted color is
#546B63, while the source fallback is#657A74; semantic color policy remains unchanged.

The existing JS cooldown and no-JavaScript cases pass, including visible native56px input,
hidden mirrors, enabled native resend with00:30 and blocked fixture actions. Existing four-state
source-copy checks also pass for request/password copy, toggles,18px exact assets and native forms.
Their capture paths and the no-JS capture now use the separate task evidence namespace to preserve
all historical files. Current evidence is `.superpowers/figma/q1/evidence/otp-input-presentation-2026-10-08/`:
four dedicated OTP empty PNG/JSON pairs, eight source-copy PNG/JSON pairs and one no-JS PNG.
Only copied native CSS changes among315 prior Q1 files; nine native HTMLs and all assets/modules/
historical captures retain hashes. Detailed source map, transition geometry, commands and inventory
are in `.superpowers/sdd/2026-10-08-figma-otp-input-presentation/task-1-report.md`.
Local OTP presentation verification leaves native recovery/CSP and whole-design acceptance open;
the controller owns independent Spec/Quality review.

### Oct8 archived Conversation bar — current measured status

Complete fresh direct MCP128:119 and its uncropped returned PNG define the local bottom container
46:130, bar46:131, caption46:132 and restore46:180/182. The authoritative Conversation archive
now shows “Archived conversation · Read-only” as a status. The existing caller supplies onRestore
only for projection.archived; generic WORKSPACE_ARCHIVED or CONVERSATION_ARCHIVED submission
rejection keeps “This Conversation is read-only.” with no archive claim or restore button.
Workspace archive still uses its separate composer and blocks Conversation restore.

At1440×960, the retained outer container measures72px and its available-width inner bar748×48px
inside the current796px panel. This is responsive geometry, with no748px width clamp. The bar
has10px radius and14/8px inner horizontal padding. Caption is13px regular; restore is151×34px,
8px radius and13px semibold with16px lines. Source12px restore padding adapts to7px: loaded
production Inter measures133.29px text, exceeding the source125px content allocation;135px
content preserves full text and the source button allocation without fixed-height clipping.
The existing semantic action tint remains, so source-color parity is not accepted.

At390×844, the inner bar grows naturally to358×76.14px and the outer container to99.14px;
caption and151×34px button occupy separate rows. Complete text fits, history remains readable,
and there is no horizontal overflow. Mobile has no source geometry and proves readable adaptation.
Keyboard Tab returns focus to the enabled restore control; the browser does not invoke its blocked
fixture endpoint. Real component tests activate the existing revision3 restore with Enter and
recover the question composer; both generic409 variants and Workspace separation remain checked.

The new A9 evidence folder contains current desktop/mobile full captures and geometry, retained
RED captures and the loaded-font diagnostic. All285 pre-existing Q1 artifacts retain their hashes,
including native exports, source/original51 and Operator outputs. Only root active
`evidence/regression-preflight/**` is excluded. No asset was added or edited; existing18×18px
brand and desktop caret slots remain. The retained answer has no invented “7 chapters” heading,
second citation stays backend page-derived, and extra suggestion/panel/rail/menu controls remain.
These checks accept only the local archived bar; whole-design, native identity and live acceptance
remain open. Full RED/GREEN, source mapping, commands and artifact proof are in
`.superpowers/sdd/2026-10-08-figma-archived-conversation-bar/task-1-report.md`.

#### Round1 review fix — collapsed panel coverage

Review finding I1 required a genuine collapsed desktop composition in addition to the retained
expanded source comparison. New tests use the actual “Collapse rail” and “Close evidence”
controls at1440×960: the rail becomes72px, the inspector closes, the Conversation panel widens
to1360px and its bar to1312×48px. Outer72px and restore151×34px remain; available width follows
the panel. At390×844, the rail is naturally hidden; the test opens and closes the evidence
sheet through actual controls before capturing the collapsed composition. Bar358×76.14px
and outer99.14px retain natural growth and full text. Keyboard Tab focus, enabled restore,
absent question submission, retained history/citations and default evidence copy are checked.
These responsive compositions establish no new global source parity.

Separate `collapsed-128-119-{1440,390}.png` and matching geometry JSON use the existing A9 folder;
the earlier expanded desktop/mobile, RED and diagnostic evidence is untouched. All295 prior
Q1 artifacts retain hashes, including all285 historical artifacts and10 initial A9 additions.
Only4 new collapsed artifacts were added. Two focused browser cases passed with NO_COLOR and
FORCE_COLOR removed from this owned invocation; no color warnings were emitted. Original
warning-bearing logs remain historical. Report append records I1 disposition and hash proof.

### Oct8 Document detail action height — current measured status

Complete fresh direct MCP128:122/125 structures and their returned uncropped renders define
Ready94:254 and Archived101:174 deletion slots298×40. Reprocess94:239, Archive94:244 and
Restore101:159 allocate298×42. The existing local common class combined42px dimensions with
callsite40px dimensions on deletion; actual-browser RED measured42px at both viewport sizes.
The common class now contains no height dimensions, ordinary callsites explicitly allocate42px and
deletion explicitly allocates40px. Shared Button, tokens, CSS, handlers and capabilities stay intact.

At1440×960, all actions remain298px wide; deletion measures40px height/min-height in Ready and
Archived, with42px ordinary actions. At390×844, all action widths grow to358px within16px margins,
and the same42/40px heights remain. Full composition captures include natural content below the
mobile viewport; horizontal fit passes. Mobile has no supplied Figma geometry and proves readable
adaptation only. Native Current/Served version strings keep their53px desktop/73px mobile overview
row; the source sample's48px row is not forced through clipping. Actual availability labels,
source filename/key, revision7, succeeded ingestion and localized processed time remain intact.

Both cases prepare Ready then Archived and invoke the real detail deletion control. The named
confirmation retains the filename/status, enabled Cancel and confirmation action. Actual Cancel
and reopened keyboard Escape close it and restore the invoking control's focus in both states.
Dialog bounds fit at560×327 desktop and352×389.28125 mobile. Each state permits exactly the existing
Document GET; unexpected requests and API writes stay empty. Confirm, reprocess, archive and
restore are never invoked. These checks add local detail transitions20/23 and Cancel coverage28;
backend authorization, deletion policy, native identity and live lifecycle acceptance remain open.

Existing exact assets remain in their original callsites: header leaf18×18 and Ready-only status
dot7×7, with nonempty956/240-byte local files and loaded browser dimensions. No asset changed.
Fonts/assets load before the four composition and four dialog captures, which were visually checked.
The source's shared border origin, colors, extra Menu/provenance disclosure, API-derived text and
whole-page geometry remain differences; this action correction does not accept whole-design parity.

Current evidence uses only `document-detail-action-height-2026-10-08/`: eight final PNGs, two journey
JSONs and two RED PNG/JSON pairs. All352 pre-existing Q1 files retain exact hashes, including native
exports/cache and original51 evidence; only root active regression-preflight is excluded. Scoped
browser GREEN passed2 cases;45 relevant component checks passed once. Final format→format:check→
typecheck and post-format scoped browser verification are recorded in
`.superpowers/sdd/2026-10-08-figma-document-detail-action-height/task-1-report.md`.
Independent Spec/Quality review belongs to the controller; full-goal acceptance remains open.

## Oct8 Document navigation

The bounded Documents navigation journey covers owned Ready and Archived rows, Actions menus,
detail links, archive/restore lifecycle and source identity. Archived detail now returns to
`/workspaces/{workspaceId}/documents?archived=true`; Ready detail retains the bare list URL.
`DocumentList` initializes its local checkbox from that query preference. Live status, revisions,
source version identities and limitations are recorded in
`.superpowers/sdd/2026-10-08-figma-document-navigation/task-1-report.md` and the scoped journey
folder. Processing-source proof, deletion, native OTP and full-frame parity remain open.

### Live navigation qualification

The named isolated1440×960 journey now passes (1 case,19.9s after the restored-list capture wait).
It proves Ready row/back with the unchecked local filter, checked Ready row/back, Ready Actions
View details, Ready and Archived trigger toggles, Archived row/detail/back retaining
`?archived=true`, Archived Actions View details/back, and list-destination Archive/Restore.
The latter two differ from the prototype's illustrated direct-detail destination. The scoped
`document-navigation-2026-10-08/` folder contains five inspected desktop captures and
`journey.json`. The restored-list capture shows a loaded Ready row and unchecked filter.

The live Markdown upload is synchronous: persisted `ingestion_job_id` and `ingestion_status` are
both null while `embedding_readiness=ready`, `serving_state=current`, and current/served version
IDs match. This does not prove a processing-row source. Source identity and current/served version
IDs remained fixed across revisions1→2→3; archive changed answer availability from available to
unavailable, restore returned it to available. Deletion projection stayed null. Scoped POSTs returned
200 with If-Match1 and2. No deletion request was submitted. Native OTP, full-frame parity and
processing-source proof remain open.
