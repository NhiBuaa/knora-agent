# Versioned PDF extraction behind a Knora adapter

Status: accepted

Milestone 2 wraps the pinned `pypdf` baseline in a `PdfTextExtractor` adapter because library
behavior alone cannot provide the deterministic contract required by Knora. Extraction options,
parser, normalizer and chunking versions are explicit immutable identities; changing them creates
new derivations rather than mutating historical results. The baseline intentionally rejects OCR and
does not promise perfect reading order or table reconstruction. Distinct terminal errors and
resource limits prevent malformed, encrypted, unsupported or empty PDFs from becoming successful
knowledge.
