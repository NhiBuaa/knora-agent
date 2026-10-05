"""Evaluation projection of validated source selections, preserving selected content."""

from dataclasses import replace

from evals.runners.ollama_evidence_first_probe import invalid, render_result

from knora.answering.generation_validation import validate_generation


def render_source_clauses(payload, evidence):
    result = render_result(payload, evidence)
    if result.decision == "REFUSAL":
        return result
    if any(item["text"] != item["quote"] for item in payload["facts"]):
        invalid()
    sources = {item.evidence_id: item.content for item in evidence}
    selected = {alias: [] for alias in result.cited_evidence_ids}
    for group in ("facts", "rules", "exceptions"):
        for item in payload[group]:
            selected[item["evidence_id"]].append(item["quote"])
    paragraphs = []
    for alias, quotes in selected.items():
        source = sources[alias]
        seen = set()
        spans = []
        fragments = []
        for ordinal, quote in enumerate(quotes):
            if quote in seen:
                continue
            seen.add(quote)
            start = source.find(quote)
            if source.find(quote, start + 1) >= 0:
                fragments.append((ordinal, quote.strip()))
            else:
                spans.append((start, start + len(quote), ordinal))
        merged = []
        for start, end, ordinal in sorted(spans):
            if merged and start <= merged[-1][1]:
                previous_start, previous_end, previous_ordinal = merged[-1]
                merged[-1] = (
                    previous_start,
                    max(previous_end, end),
                    min(previous_ordinal, ordinal),
                )
            else:
                merged.append((start, end, ordinal))
        fragments.extend((ordinal, source[start:end].strip()) for start, end, ordinal in merged)
        paragraphs.append(" ".join(text for _, text in sorted(fragments)) + f" [[{alias}]]")
    result = replace(result, answer="\n\n".join(paragraphs))
    validate_generation(result, available_evidence_ids=tuple(sources))
    return result
