# PDF Retrieval V3 V1: source gold review candidate

**Status: pending NhiBuaa review.** This is a candidate corpus and gold packet, not frozen
gold or a claim about baseline quality. Exposure for all questions and synthetic content:
`agent-authored; no model calls; owner review pending`.

Batch 1 (001-012) was approved by NhiBuaa on 2026-10-14 after adding after-receipt
timing to both deadlines in case 010 and reconfirming cases 001/009 against the
original clean-02.pdf page 1. Batches 2-5 remain pending. This partial review does
not freeze the full dataset or approve chunk bindings or baseline B; the final
corpus/dataset hashes will be approved after all five batches.

## Fixed scope

| Category | Files | PDF pages | Visible characteristics |
| --- | --- | --- | --- |
| Clean (2) | clean-01, clean-02 | 2, 1 | Registry and prose; duplicate fee sentence supplies reviewed OR alternatives |
| Hierarchy (3) | hierarchy-01 through hierarchy-03 | 1, 1, 2 | Nested numbered headings, exceptions, negation, cross-page sections |
| Multi-column (2) | columns-01, columns-02 | 1, 1 | Physically separate text columns; Vietnamese/English glossary |
| Difficult tables (3) | table-01 through table-03 | 1, 1, 1 | Drawn grid, two-tier merged column headers and row-spanning headers; identifiers, counts and decimal comma units |
| Scan/mixed (3) | scan-01 through scan-03 | 1, 1, 1 | Raster-only evidence; scan-02 adds searchable title/footer; scan-03 is grayscale with 0.6-degree skew |
| Real academic (3) | academic-phobert, academic-phonlp, academic-vit5 | 6, 7, 7 | Original ACL PDFs; two columns, equations, figures and benchmark tables |

There are **16 PDFs, 35 PDF pages, 86 visible source anchors and 60 authored cases**.
Cases retain the approved distribution: 8 simple, 10 comparison, 10 table/hierarchy,
8 follow-up, 10 typo/no-accent/identifier, 6 multi-hop, 8 no-answer. Questions include
Vietnamese, English and mixed language, diacritics, negation, counts and exact identifiers.

The six multi-hop cases provide only a registry route code. The registry resolves that
code to an opaque identifier in a different document, where the requested value is found.
The target documents do not repeat registry route codes. Both source steps are required;
the two table lookups also require the target row identifier. The eight follow-ups name
their real preceding cases 001-008 and use their established subject through references
such as “thiết bị đó” and “nơi đó”. A follow-up must be asked in its parent conversation.
Multi-hop validation rejects any source that is an OR option in every AND group, so every
legal selection requires at least two distinct sources.

## Review packets

- [Batch 1: cases 001-012](review-batch-01.md)
- [Batch 2: cases 013-024](review-batch-02.md)
- [Batch 3: cases 025-036](review-batch-03.md)
- [Batch 4: cases 037-048](review-batch-04.md)
- [Batch 5: cases 049-060](review-batch-05.md)

Each packet includes the reference, required facts, evidence groups, source hash, license,
visible locator, parent and absence scope. PDF pages are 1-based physical pages, not printed
proceedings page numbers. Text coordinates are PDF points measured from the bottom; raster
coordinates are image pixels measured from the top. Table locators state the row, column
and unit. In packets, `/` separates authored line breaks in academic transcriptions;
the manifest stores actual newline characters. Typographic subscripts are transcribed
as attached text and explained in the visible locator.

The outer evidence groups mean AND; alternatives inside one group mean OR. The repeated
fee statement is an intentional ambiguity for derivation review. Gold anchors originate
from the authoring literals or visual inspection of the original papers, never from chunks,
parser output, embeddings, generated answers or a model judge. Reading PDF text for page
counts and checking absent terms does not create gold from extraction.

## Source provenance and redistribution

Academic downloads were acquired unchanged on 2026-10-14. SHA-256, URLs, title, authors,
printed page range and physical page count are recorded in the manifest. These copies
contain no edits. The attribution to retain on redistribution is:

- Dat Quoc Nguyen and Anh Tuan Nguyen. *PhoBERT: Pre-trained language models for Vietnamese*.
  Findings of EMNLP 2020, pp. 1037-1042. [Original](https://aclanthology.org/2020.findings-emnlp.92.pdf).
- Linh The Nguyen and Dat Quoc Nguyen. *PhoNLP: A joint multi-task learning model for
  Vietnamese part-of-speech tagging, named entity recognition and dependency parsing*.
  NAACL-HLT 2021 Demonstrations, pp. 1-7. [Original](https://aclanthology.org/2021.naacl-demos.1.pdf).
- Long Phan, Hieu Tran, Hieu Nguyen and Trieu H. Trinh. *ViT5: Pretrained Text-to-Text
  Transformer for Vietnamese Language Generation*. NAACL 2022 Student Research Workshop,
  pp. 136-142. [Original](https://aclanthology.org/2022.naacl-srw.18.pdf).

The [ACL copyright policy](https://aclanthology.org/faq/copyright/) identifies the applicable
license for these post-2015 ACL publications as CC BY 4.0. The PDF license is distinct from
the Apache License 2.0 mentioned for the PhoNLP toolkit. Preserve the paper attribution,
copyright notice and [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/).
No author endorsement is implied.

The original synthetic fixture text, source gold and drawn layouts are supplied as Knora
evaluation fixtures under CC BY 4.0; attribution: “Knora evaluation fixture; agent-authored,
2026”. They are fictional examples, not operational policy. Arial fonts come from the
authoring machine and are embedded as subsets for PDF display; original font files are
not redistributed or included in this content license.

License evidence fetched on 2026-10-14:

| Snapshot | SHA-256 |
| --- | --- |
| [ACL copyright HTML](licenses/acl-copyright-2026-10-14.html) | `b6f99045085741dfb18d02a8ed839f371da43c39eb2284b87cbb90991a65334c` |
| [CC BY 4.0 legal code HTML](licenses/cc-by-4.0-legalcode-2026-10-14.html) | `58230517b7895aa219ff46a6ed63e67057a1582fb9ea054b16728a8c13525650` |

## Reproduction and validation

[author_fixtures.py](author_fixtures.py) contains all synthetic text, layout recipes and
authored cases. It creates exactly 13 synthetic PDFs and regenerates the manifest, JSONL
and five packets; it never modifies the three academic originals. It needs the bundled
authoring Python with reportlab 4.4.9 and Pillow, plus local `C:/Windows/Fonts/arial.ttf`
and `arialbd.ttf`. Those tools are authoring dependencies only; no backend dependency
was added. Regeneration on a different font/tool version can change hashes and requires
a new owner review. Run from the repository root:

```powershell
& 'C:/Users/NhiBuaa/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 evals/corpora/pdf_retrieval_v3_v1/author_fixtures.py
./.venv/Scripts/python -m pytest evals/test/test_pdf_retrieval_v3_dataset.py -q
```

The strict loader validates safe paths, file hashes, actual page counts, licenses, IDs,
case distribution, source closure, parent order, AND/OR groups, positive/refusal gold
and digests. Corpus SHA-256 binds canonical UTF-8 JSON of `{sources, anchors}` using sorted
keys and compact separators. Dataset SHA-256 binds JSONL bytes after CRLF/CR normalization
to LF. Thus visible gold/locator edits invalidate corpus approval; question/fact/parent
edits invalidate dataset approval. Owner approval must explicitly match both hashes and
owner `NhiBuaa` through `validate_approval`; packet status never grants approval.

All 15 synthetic pages were rendered with Poppler and visually inspected for legible
diacritics, columns, table geometry, scan text and clipping. Academic positive facts were
checked on rendered physical page 1 of each paper. The entire seven-page PhoNLP paper
was read to check the absent training cost claim. The three scan PDFs deliberately contain
no searchable positive evidence; pypdf page counts do not establish OCR or extraction
fidelity. Exact matching may fail on line breaks, subscripts, table cells or images, and
will be reported by the derivation step. Keep all 16/60 even if the unchanged baseline fails.
