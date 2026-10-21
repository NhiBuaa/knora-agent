"""Source gold stays independent of chunks; exact matches require an owner review."""

import hashlib
import json


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def chunk_record(chunk) -> dict:
    fields = (
        "workspace_id",
        "chunk_id",
        "document_version_id",
        "chunk_set_id",
        "source_key",
        "raw_sha256",
        "parser_configuration_id",
        "normalizer_configuration_id",
        "chunking_configuration_id",
        "page_start",
        "page_end",
        "start_offset",
        "end_offset",
        "content_checksum",
        "content",
    )
    return {field: getattr(chunk, field) for field in fields}


def propose_bindings(dataset, chunks) -> dict:
    chunks = tuple(sorted((chunk_record(c) for c in chunks), key=lambda c: c["chunk_id"]))
    sources = {source.id: source for source in dataset.sources}
    if len({c["workspace_id"] for c in chunks}) > 1:
        raise ValueError("derivation workspace mismatch")
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("duplicate derivation chunks")
    for chunk in chunks:
        source = sources.get(chunk["source_key"])
        if (
            source is None
            or chunk["raw_sha256"] != source.sha256
            or not all(
                chunk[field]
                for field in (
                    "workspace_id",
                    "chunk_id",
                    "document_version_id",
                    "chunk_set_id",
                    "parser_configuration_id",
                    "normalizer_configuration_id",
                    "chunking_configuration_id",
                )
            )
            or type(chunk["page_start"]) is not int
            or chunk["page_start"] < 1
            or chunk["page_start"] != chunk["page_end"]
            or type(chunk["start_offset"]) is not int
            or chunk["start_offset"] < 0
            or type(chunk["end_offset"]) is not int
            or chunk["end_offset"] - chunk["start_offset"] != len(chunk["content"])
            or hashlib.sha256(chunk["content"].encode()).hexdigest() != chunk["content_checksum"]
        ):
            raise ValueError("invalid source derivation")
    anchors = {}
    for anchor in dataset.anchors:
        occurrences = {}
        for chunk in chunks:
            if chunk["source_key"] != anchor.source_id or chunk["page_start"] != anchor.page:
                continue
            cursor = 0
            while (position := chunk["content"].find(anchor.text, cursor)) >= 0:
                start = chunk["start_offset"] + position
                identity = (
                    chunk["document_version_id"],
                    chunk["chunk_set_id"],
                    start,
                    start + len(anchor.text),
                )
                match = occurrences.setdefault(
                    identity,
                    {
                        "document_version_id": identity[0],
                        "chunk_set_id": identity[1],
                        "page": anchor.page,
                        "start_offset": identity[2],
                        "end_offset": identity[3],
                        "chunk_ids": [],
                    },
                )
                match["chunk_ids"].append(chunk["chunk_id"])
                cursor = position + 1
        matches = list(occurrences.values())
        anchors[anchor.id] = {
            "source_id": anchor.source_id,
            "status": "missing"
            if not matches
            else "proposed"
            if len(matches) == 1
            else "ambiguous",
            "matches": matches,
        }
    result = {
        "schema_version": 1,
        "corpus_sha256": dataset.corpus_sha256,
        "dataset_sha256": dataset.dataset_sha256,
        "derivation_sha256": digest(chunks),
        "anchors": anchors,
    }
    result["proposal_sha256"] = digest(result)
    return result


def validate_binding_review(proposals: dict, review: dict) -> dict[str, tuple[str, ...]]:
    if (
        review.get("status") != "approved"
        or review.get("reviewer") != "NhiBuaa"
        or not review.get("decision_url")
    ):
        raise ValueError("owner binding review required")
    calculated = digest({k: v for k, v in proposals.items() if k != "proposal_sha256"})
    if (
        calculated != proposals.get("proposal_sha256")
        or review.get("proposal_sha256") != calculated
    ):
        raise ValueError("binding review digest mismatch")
    choices = review.get("choices")
    if not isinstance(choices, dict) or set(choices) != set(proposals["anchors"]):
        raise ValueError("binding review must cover every anchor, including missing ones")
    bindings = {}
    for anchor_id, proposal in proposals["anchors"].items():
        indexes = choices[anchor_id]
        if not isinstance(indexes, list) or any(type(i) is not int for i in indexes):
            raise ValueError("invalid binding review choices")
        matches = proposal["matches"]
        if len(indexes) != (1 if matches else 0):
            raise ValueError("ambiguous binding requires one explicitly reviewed occurrence")
        if indexes and not 0 <= indexes[0] < len(matches):
            raise ValueError("invalid binding review occurrence")
        bindings[anchor_id] = tuple(matches[indexes[0]]["chunk_ids"]) if indexes else ()
    return bindings


def group_coverage(groups, bindings, selected_chunk_ids) -> tuple[bool, ...]:
    selected = set(selected_chunk_ids)
    return tuple(
        any(selected.intersection(bindings[a]) for a in alternatives) for alternatives in groups
    )
