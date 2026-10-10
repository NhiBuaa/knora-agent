# Knora visual tokens

`frontend/styles/tokens.css` is the source of truth for both themes. The root values are light;
`[data-theme="dark"]` applies explicit dark preference. When no explicit preference is stored,
system mode follows `prefers-color-scheme` before hydration.

| CSS token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--page` | #EFFCFA | #0B1412 | App background |
| `--surface` | #FFFFFF | #12201C | Raised content background |
| `--surface-subtle` | #F3F8F5 | #1B2B25 | Quiet grouping |
| `--text-primary` | #1F3B36 | #D7EFE6 | Main text |
| `--text-secondary` | #385A51 | #B8D1C6 | Supporting text |
| `--text-muted` | #60756F | #94B3A5 | Low emphasis text |
| `--action` | #33A15B | #4DBB73 | Primary control background |
| `--action-hover` | #2F9555 | #69CF8B | Pointer hover |
| `--action-active` | #2D9052 | #3DA965 | Pressed action |
| `--action-foreground` | #FFFFFF | #FFFFFF | Figma white text on solid action controls |
| `--action-soft` | #E6F5EB | #163E27 | Tinted page-range/auth cue surface |
| `--signature` | #784131 | #C68F79 | Restrained brand accent |
| `--signature-soft` | #F4EAE6 | #34251F | Tinted source/auth-status cue surface |
| `--signature-foreground` | #FFFFFF | #0B1412 | Text on signature |
| `--border` | #D9E2DE | #2A3D36 | Subtle dividers and surfaces |
| `--control-border` | #788A82 | #60776C | Input and control boundaries |
| `--focus` | #176B43 | #9CE3B5 | Visible focus indicator |
| `--status-success` | #1E6A41 | #83DCA4 | Success foreground |
| `--status-warning` | #805500 | #E5BE73 | Warning foreground |
| `--status-error` | #A33030 | #F49B98 | Error foreground |
| `--status-info` | #245F88 | #8EC8F0 | Information foreground |

The owner explicitly corrected solid green controls to Figma's white foreground on Oct10.
`--action-foreground` therefore stays white in light, explicit dark and system dark; native
Keycloak primary controls also use white. The original green background and its hover/pressed
tones remain. This source-color exception does not meet 4.5:1 for small text, so primary action
pairs are excluded from that claim. Body, muted, notice and status contrast checks remain enforced.
Signature foreground pairs exceed 4.5:1 in both themes. Status colors are foreground values on page or surface; state text and icons must
also identify the state. Do not use status color alone to communicate meaning.
The control border contrasts at least 3:1 against both surface backgrounds in each theme.
The subtler border is for decoration and must not be the only visible boundary of a control.

Light muted text deliberately uses `#60756F` instead of the Figma sample `#657A74`.
The sample passes on white (4.576:1), but fails on page (4.352:1) and subtle surface
(4.261:1), where small table headings, evidence labels and trust cues appear.
The shared accessible value provides 4.916:1 on white, 4.676:1 on page and 4.578:1 on
subtle surface. Both themes are checked on all three backgrounds. This is a documented
accessibility adaptation, not an exact source-color parity claim.

Evaluation unavailable uses local status roles: light `--evaluation-status-surface` is
`#F2E4DF` and `--evaluation-status-foreground` is `#784131`, matching Figma216:810.
Explicit/system dark preserve the existing warning foreground and its10% surface mix;
there is no dark Figma reference. These roles do not change other warning badges.

Authentication outcome cue surfaces reuse the Figma light and existing native-theme dark palette.
Both explicit and system dark define these tokens. Source/status and page-range foregrounds retain
the accessible semantic signature/action-text colors; their actual rendered pairs are checked at
4.5:1 or better. Dark is an adaptation without a supplied dark source.

`frontend/styles/typography.css` assigns local Roboto Slab to headings and local Inter to body
and controls. The scale is 32 px heading, 18 px lead, 16 px body, 14 px controls, 13 px small,
12 px caption, and 48 px display for rare editorial use. Content max width is 1200 px with
responsive gutters. Existing section/article surfaces remain global until their pages can opt in
to a shared presentation style without losing current readability.

## Bundled font provenance

- Inter variable WOFF2: [rsms/inter at `353b61b9`](https://github.com/rsms/inter/blob/353b61b9f4430d5f420d56605a6e7993e0941470/docs/font-files/InterVariable.woff2); license in `frontend/public/fonts/OFL-Inter.txt` (SIL Open Font License 1.1).
- Roboto Slab variable WOFF2: [googlefonts/robotoslab at `67af3ce9`](https://github.com/googlefonts/robotoslab/blob/67af3ce9c4ca574419e1295b6165a2eeee112e6e/fonts/webfonts/RobotoSlab%5Bwght%5D.woff2); license in `frontend/public/fonts/LICENSE-RobotoSlab.txt` (Apache License 2.0).

Both upstream WOFF2 character maps include sampled Vietnamese vowels and tone marks. Fonts are
loaded through `next/font/local` and do not require build-time network access.
