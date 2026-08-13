from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorpusMember:
    source_key: str
    before_chunk_set_digest: str
    after_chunk_set_digest: str
    v2_embedding_complete: bool
    v2_vectors_are_new: bool
    v1_immutable: bool


@dataclass(frozen=True, slots=True)
class CutoverDecision:
    production_enablement_allowed: bool
    pending_source_keys: tuple[str, ...]
    invariant_violations: tuple[str, ...]


def evaluate_cutover(members: tuple[CorpusMember, ...]) -> CutoverDecision:
    if not members or len({member.source_key for member in members}) != len(members):
        raise ValueError("authority-bound corpus population must be non-empty and unique")
    violations: list[str] = []
    pending: list[str] = []
    for member in sorted(members, key=lambda item: item.source_key):
        if member.before_chunk_set_digest != member.after_chunk_set_digest:
            violations.append(f"{member.source_key}:CHUNK_SET_CHANGED")
        if not member.v2_embedding_complete:
            pending.append(member.source_key)
        if not member.v2_vectors_are_new:
            violations.append(f"{member.source_key}:V2_VECTOR_NOT_NEW")
        if not member.v1_immutable:
            violations.append(f"{member.source_key}:V1_MUTATED")
    return CutoverDecision(
        production_enablement_allowed=not pending and not violations,
        pending_source_keys=tuple(pending),
        invariant_violations=tuple(violations),
    )
