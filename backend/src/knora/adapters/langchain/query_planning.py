"""LangChain adapter and structured output integration for Query Planning.

Supports LLM-assisted query rewriting, multi-intent decomposition, and follow-up
resolution with Knora strict schema validation, protected span guards, and fail-safe fallbacks.
Refs #153 (Retrieval V3 Stage 7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from knora.answering.query_planning import (
    MAX_SUBQUESTIONS,
    MAX_VARIANTS_PER_QUERY,
    ProtectedSpan,
    QueryPlan,
    QueryVariant,
    Subquestion,
    build_fast_path_plan,
    extract_protected_spans,
    validate_protected_spans_preserved,
)
from knora.domain.errors import KnoraError

QUERY_PLANNER_PROMPT_VERSION = "knora-query-planner-v1"

QUERY_PLAN_SYSTEM_PROMPT = (
    "You are a query analysis and planning engine for enterprise documents. "
    "Given a user query and untrusted dialogue history, generate a structured query plan. "
    "Rules:\n"
    "1. Preserve exact entity names, identifiers (e.g. AUTH_403), numbers (e.g. 14, 3.1), "
    "dates, and negation (e.g. không quá, chưa, without) strictly unchanged.\n"
    "2. For follow-up queries with pronouns or references, rewrite into a clear standalone query.\n"
    "3. For comparison or multi-topic questions, decompose into atomic subquestions.\n"
    "4. Return only valid JSON conforming strictly to the requested schema."
)

QUERY_PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "subquestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "required": {"type": "boolean"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "text", "required"],
                "additionalProperties": False,
            },
        },
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "reason": {"type": "string"},
                    "variant_kind": {
                        "type": "string",
                        "enum": ["original", "rewrite", "subquestion", "typo_corrected"],
                    },
                },
                "required": ["query", "reason", "variant_kind"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["subquestions", "variants"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class KnoraLangChainQueryPlanner:
    """Wraps a LangChain Chat Model with Knora verification guards and fallbacks."""

    model: Any
    provider_name: str = "cloudflare-workers-ai"
    model_name: str = "@cf/openai/gpt-oss-20b"
    max_subquestions: int = MAX_SUBQUESTIONS
    max_variants: int = MAX_VARIANTS_PER_QUERY

    async def aplan(
        self,
        question: str,
        *,
        conversation_transcript: str | None = None,
        query_id: str = "plan-1",
    ) -> QueryPlan:
        if not isinstance(question, str) or not question.strip():
            raise KnoraError("QUERY_INPUT_INVALID")

        original_protected = extract_protected_spans(question)

        prompt_input = f"User Query: {question}\n"
        if conversation_transcript:
            prompt_input += (
                f"\nConversation Context (reference resolution only):\n{conversation_transcript}\n"
            )

        messages = [
            {"role": "system", "content": QUERY_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_input},
        ]

        try:
            if hasattr(self.model, "ainvoke"):
                raw = await self.model.ainvoke(messages)
            elif hasattr(self.model, "invoke"):
                raw = self.model.invoke(messages)
            else:
                return build_fast_path_plan(question, query_id=query_id)

            data = self._extract_data(raw)
            return self._validate_and_build_plan(
                data=data,
                original_query=question,
                original_protected=original_protected,
                query_id=query_id,
            )
        except Exception:
            # Fall back safely to fast-path original plan
            return build_fast_path_plan(question, query_id=query_id)

    def _extract_data(self, raw_output: Any) -> dict[str, Any]:
        if isinstance(raw_output, dict):
            return raw_output
        if hasattr(raw_output, "model_dump"):
            return raw_output.model_dump()
        if hasattr(raw_output, "dict"):
            return raw_output.dict()

        content = getattr(raw_output, "content", None)
        if isinstance(content, str):
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        elif isinstance(content, dict):
            return content

        raise ValueError("Invalid query plan output structure")

    def _validate_and_build_plan(
        self,
        *,
        data: dict[str, Any],
        original_query: str,
        original_protected: tuple[ProtectedSpan, ...],
        query_id: str,
    ) -> QueryPlan:
        raw_subs = data.get("subquestions", [])
        raw_variants = data.get("variants", [])

        subquestions: list[Subquestion] = []
        seen_sub_ids: set[str] = set()

        for item in raw_subs:
            sid = str(item.get("id", f"sub_{len(subquestions) + 1}"))
            if sid in seen_sub_ids:
                continue
            seen_sub_ids.add(sid)
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            req = bool(item.get("required", True))
            deps = tuple(str(d) for d in item.get("depends_on", ()))
            spans = extract_protected_spans(text)
            subquestions.append(
                Subquestion(
                    id=sid,
                    text=text,
                    required=req,
                    depends_on=deps,
                    protected_spans=spans,
                )
            )
            if len(subquestions) >= self.max_subquestions:
                break

        # Fallback subquestion if none provided
        if not subquestions:
            subquestions.append(
                Subquestion(
                    id="sub_1",
                    text=original_query,
                    required=True,
                    protected_spans=original_protected,
                )
            )

        # Check for circular dependencies in subquestions
        self._check_dependency_cycles(subquestions)

        variants: list[QueryVariant] = [
            QueryVariant(query=original_query, reason="original_query", variant_kind="original")
        ]
        seen_queries = {original_query.strip().casefold()}

        for item in raw_variants:
            q_text = str(item.get("query", "")).strip()
            if not q_text:
                continue
            norm_q = q_text.casefold()
            if norm_q in seen_queries:
                continue

            # Verify that protected spans are preserved in this variant
            try:
                validate_protected_spans_preserved(original_protected, q_text)
            except KnoraError:
                # Reject invalid variant that mutated protected entity/number
                continue

            seen_queries.add(norm_q)
            variants.append(
                QueryVariant(
                    query=q_text,
                    reason=str(item.get("reason", "llm_variant")),
                    variant_kind=str(item.get("variant_kind", "rewrite")),
                )
            )
            if len(variants) >= self.max_variants:
                break

        return QueryPlan(
            query_id=query_id,
            original_query=original_query,
            is_fast_path=False,
            subquestions=tuple(subquestions),
            variants=tuple(variants),
            protected_spans=original_protected,
            max_subquestions=self.max_subquestions,
            max_variants=self.max_variants,
        )

    def _check_dependency_cycles(self, subquestions: list[Subquestion]) -> None:
        adj: dict[str, list[str]] = {sq.id: list(sq.depends_on) for sq in subquestions}
        visited: dict[str, int] = {}  # 0: visiting, 1: visited

        def dfs(node: str) -> None:
            if visited.get(node) == 0:
                raise KnoraError("QUERY_PLAN_CYCLE_DETECTED")
            if visited.get(node) == 1:
                return
            visited[node] = 0
            for neighbor in adj.get(node, []):
                dfs(neighbor)
            visited[node] = 1

        for sq in subquestions:
            if sq.id not in visited:
                dfs(sq.id)
