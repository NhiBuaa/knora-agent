# Knora visual tokens

`frontend/styles/tokens.css` is the source of truth for both themes. The root values are light;
`[data-theme="dark"]` applies explicit dark preference. Until the theme control lands, a system
dark preference uses the same dark values when no explicit `data-theme` is set.

| CSS token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--page` | #EFFCFA | #0B1412 | App background |
| `--surface` | #FFFFFF | #12201C | Raised content background |
| `--surface-subtle` | #F3F8F5 | #1B2B25 | Quiet grouping |
| `--text-primary` | #1F3B36 | #D7EFE6 | Main text |
| `--text-secondary` | #385A51 | #B8D1C6 | Supporting text |
| `--text-muted` | #546B63 | #94B3A5 | Low emphasis text |
| `--action` | #33A15B | #4DBB73 | Primary control background |
| `--action-hover` | #2F9555 | #69CF8B | Pointer hover |
| `--action-active` | #2D9052 | #3DA965 | Pressed action |
| `--action-foreground` | #0B1412 | #0B1412 | Text on action |
| `--signature` | #784131 | #C68F79 | Restrained brand accent |
| `--signature-foreground` | #FFFFFF | #0B1412 | Text on signature |
| `--border` | #D9E2DE | #2A3D36 | Dividers and controls |
| `--focus` | #176B43 | #9CE3B5 | Visible focus indicator |
| `--status-success` | #1E6A41 | #83DCA4 | Success foreground |
| `--status-warning` | #805500 | #E5BE73 | Warning foreground |
| `--status-error` | #A33030 | #F49B98 | Error foreground |
| `--status-info` | #245F88 | #8EC8F0 | Information foreground |

Action and signature foreground pairs exceed 4.5:1 in both themes. The dark text on green is
intentional. Status colors are foreground values on page or surface; state text and icons must
also identify the state. Do not use status color alone to communicate meaning.

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
