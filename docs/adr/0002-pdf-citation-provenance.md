# Version-pinned PDF citation provenance

Status: accepted

PDF citations use a version-pinned source locator rather than page numbers alone: the projection
must retain `document_version_id`, a persisted Chunk identity, a 1-based physical page range, and
stable offsets in normalized page text. `page_label` is display-only, while existing line fields
remain derived compatibility metadata. This preserves traceability when parser or normalization
versions change and leaves an extensible place for future bounding boxes; page-only provenance was
rejected because it cannot identify the exact extracted text or survive page-level ambiguity.
