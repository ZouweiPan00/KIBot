from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Callable

from backend.schemas.session import KIBotSession


IntentType = str
IntentParser = Callable[[str], dict[str, Any] | None]

VALID_INTENTS = {
    "explain_decision",
    "keep_concept",
    "remove_concept",
    "merge_concepts",
    "split_concept",
    "unknown",
}

ACTION_BY_INTENT = {
    "keep_concept": "keep",
    "remove_concept": "remove",
    "merge_concepts": "merge",
    "split_concept": "split",
}

STATUS_BY_ACTION = {
    "keep": "active",
    "remove": "removed",
    "merge": "merged",
    "split": "split",
}

MAX_FULL_MESSAGES = 10
MAX_TURN_MESSAGES = 20


@dataclass(frozen=True)
class ParsedIntent:
    type: IntentType
    concept: str = ""
    concepts: list[str] = field(default_factory=list)
    decision_id: str = ""
    source: str = "rule"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "concept": self.concept,
            "concepts": list(self.concepts),
            "decision_id": self.decision_id,
            "source": self.source,
        }


@dataclass(frozen=True)
class DialogueResult:
    assistant_message: str
    parsed_intent: dict[str, Any]
    state_summary: dict[str, Any]


class DialogueService:
    def __init__(
        self,
        llm_intent_parser: IntentParser | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.llm_intent_parser = llm_intent_parser
        self.llm_client = llm_client

    def parse_intent(self, message: str) -> ParsedIntent:
        llm_intent = self._parse_with_llm(message)
        if llm_intent is not None:
            return llm_intent
        return self._parse_with_rules(message)

    def handle_message(self, session: KIBotSession, message: str) -> DialogueResult:
        clean_message = message.strip()
        intent = self.parse_intent(clean_message)
        session.messages.append({"role": "user", "content": clean_message})

        rule_message = self._apply_intent(session, intent, clean_message)
        assistant_message = self._llm_assistant_message(session, clean_message, rule_message) or rule_message
        session.messages.append({"role": "assistant", "content": assistant_message})
        self._compact_messages(session)

        return DialogueResult(
            assistant_message=assistant_message,
            parsed_intent=intent.to_dict(),
            state_summary=self._state_summary(session),
        )

    def _llm_assistant_message(
        self,
        session: KIBotSession,
        teacher_message: str,
        rule_message: str,
    ) -> str | None:
        if self.llm_client is None:
            return None
        try:
            response = self.llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are KIBot, a textbook knowledge integration agent. "
                            "Answer the teacher in Chinese. Be concise, grounded in the "
                            "current integration decisions, and mention what state changed "
                            "when relevant."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._llm_dialogue_context(session, teacher_message, rule_message),
                    },
                ]
            )
        except Exception as exc:
            return f"{rule_message}\n\nLLM 调用失败，已使用规则结果继续：{_safe_error_message(exc)}"

        self._record_token_usage(session, response)
        answer_text = getattr(response, "answer_text", None)
        if isinstance(answer_text, str) and answer_text.strip():
            return answer_text.strip()
        return None

    def _llm_dialogue_context(
        self,
        session: KIBotSession,
        teacher_message: str,
        rule_message: str,
    ) -> str:
        decision_lines = []
        for decision in session.integration_decisions[:12]:
            if not isinstance(decision, dict):
                continue
            decision_lines.append(
                " | ".join(
                    [
                        f"id={decision.get('decision_id', '')}",
                        f"concept={decision.get('concept_name', '')}",
                        f"action={decision.get('action', '')}",
                        f"reason={decision.get('reason', '')}",
                        f"note={decision.get('compact_note', '')}",
                    ]
                )
            )
        return (
            f"教师输入：{teacher_message}\n"
            f"规则层处理结果：{rule_message}\n"
            f"当前整合决策：\n" + "\n".join(decision_lines)
        )

    def _record_token_usage(self, session: KIBotSession, response: Any) -> None:
        usage = getattr(response, "token_usage", None)
        if usage is None:
            return
        session.token_usage.calls += _usage_int(usage, "calls")
        session.token_usage.input_tokens += _usage_int(usage, "input_tokens")
        session.token_usage.output_tokens += _usage_int(usage, "output_tokens")
        session.token_usage.total_tokens += _usage_int(usage, "total_tokens")

    def _parse_with_llm(self, message: str) -> ParsedIntent | None:
        if self.llm_intent_parser is None:
            return None
        payload = self.llm_intent_parser(message)
        if not isinstance(payload, dict):
            return None
        intent_type = str(payload.get("type") or "").strip()
        if intent_type not in VALID_INTENTS:
            return None
        concepts = [
            str(concept).strip()
            for concept in payload.get("concepts", [])
            if str(concept).strip()
        ]
        concept = str(payload.get("concept") or "").strip()
        if not concept and concepts:
            concept = concepts[0]
        return ParsedIntent(
            type=intent_type,
            concept=concept,
            concepts=concepts,
            decision_id=str(payload.get("decision_id") or "").strip(),
            source="llm",
        )

    def _parse_with_rules(self, message: str) -> ParsedIntent:
        text = " ".join(message.strip().split())
        lowered = text.lower()

        merge_match = re.search(r"\bmerge\s+(.+?)\s+(?:and|with|,)\s+(.+)$", text, re.I)
        if merge_match:
            concepts = [_clean_target(merge_match.group(1)), _clean_target(merge_match.group(2))]
            return ParsedIntent(
                type="merge_concepts",
                concept=concepts[0],
                concepts=[concept for concept in concepts if concept],
            )

        split_match = re.search(r"\bsplit\s+(.+?)(?:\s+into\b.*)?$", text, re.I)
        if split_match:
            concept = _clean_target(split_match.group(1))
            return ParsedIntent(type="split_concept", concept=concept, concepts=[concept])

        remove_match = re.search(r"\b(?:remove|delete|drop)\s+(.+)$", text, re.I)
        if remove_match:
            concept = _clean_target(remove_match.group(1))
            return ParsedIntent(type="remove_concept", concept=concept, concepts=[concept])

        keep_match = re.search(r"\b(?:keep|retain|preserve)\s+(.+)$", text, re.I)
        if keep_match:
            concept = _clean_target(keep_match.group(1))
            return ParsedIntent(type="keep_concept", concept=concept, concepts=[concept])

        if re.search(r"\b(?:explain|why|reason)\b", lowered):
            target = re.sub(
                r"(?i)\b(?:please|can you|could you|explain|why|the|decision|for|about|reason)\b",
                " ",
                text,
            )
            concept = _clean_target(target)
            return ParsedIntent(
                type="explain_decision",
                concept=concept,
                concepts=[concept] if concept else [],
                decision_id=concept if concept.startswith("dec-") else "",
            )

        return ParsedIntent(type="unknown")

    def _apply_intent(
        self,
        session: KIBotSession,
        intent: ParsedIntent,
        teacher_message: str,
    ) -> str:
        if intent.type == "unknown":
            return (
                "I can help explain, keep, remove, merge, or split concepts. "
                "Please name the concept or decision."
            )

        decision = self._find_decision(session, intent)
        if decision is None:
            target = intent.decision_id or intent.concept or ", ".join(intent.concepts)
            return f"I could not find a saved decision or concept matching '{target}'."

        if intent.type == "explain_decision":
            return self._explain_decision(decision)

        action = ACTION_BY_INTENT[intent.type]
        decision["action"] = action
        decision["teacher_note"] = f"Teacher requested {action}: {teacher_message}"
        self._update_graph_status(session, decision, action)
        self._mark_report_stale(session, decision, action)
        return (
            f"Updated '{decision.get('concept_name')}' to {action}. "
            "I also updated the related graph status."
        )

    def _find_decision(
        self,
        session: KIBotSession,
        intent: ParsedIntent,
    ) -> dict[str, Any] | None:
        targets = [intent.decision_id, intent.concept, *intent.concepts]
        normalized_targets = {_normalize(target) for target in targets if target}
        if not normalized_targets:
            return None

        for decision in session.integration_decisions:
            if not isinstance(decision, dict):
                continue
            if str(decision.get("decision_id") or "") in targets:
                return decision
            decision_terms = self._decision_terms(decision)
            if normalized_targets & decision_terms:
                return decision
        return None

    def _decision_terms(self, decision: dict[str, Any]) -> set[str]:
        terms = {
            _normalize(str(decision.get("decision_id") or "")),
            _normalize(str(decision.get("concept_name") or "")),
        }
        for source in decision.get("sources", []):
            if not isinstance(source, dict):
                continue
            for field_name in ("name", "concept_name", "node_id", "id"):
                terms.add(_normalize(str(source.get(field_name) or "")))
        return {term for term in terms if term}

    def _explain_decision(self, decision: dict[str, Any]) -> str:
        concept = decision.get("concept_name") or decision.get("decision_id") or "this concept"
        action = decision.get("action") or "review"
        reason = decision.get("reason") or "no reason was recorded"
        confidence = decision.get("confidence")
        confidence_text = "" if confidence is None else f" Confidence: {confidence}."
        return f"The saved decision for '{concept}' is {action}: {reason}.{confidence_text}"

    def _update_graph_status(
        self,
        session: KIBotSession,
        decision: dict[str, Any],
        action: str,
    ) -> None:
        status = STATUS_BY_ACTION[action]
        node_ids: set[str] = set()
        names: set[str] = {_normalize(str(decision.get("concept_name") or ""))}
        for source in decision.get("sources", []):
            if not isinstance(source, dict):
                continue
            for field_name in ("node_id", "id"):
                value = str(source.get(field_name) or "").strip()
                if value:
                    node_ids.add(value)
            for field_name in ("name", "concept_name"):
                value = _normalize(str(source.get(field_name) or ""))
                if value:
                    names.add(value)

        for node in session.graph_nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "")
            node_name = _normalize(str(node.get("name") or ""))
            if node_id in node_ids or node_name in names:
                node["status"] = status

    def _mark_report_stale(
        self,
        session: KIBotSession,
        decision: dict[str, Any],
        action: str,
    ) -> None:
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        session.report.updated_at = timestamp.replace("+00:00", "Z")
        concept = decision.get("concept_name") or decision.get("decision_id") or "concept"
        note = f"Teacher dialogue update: {concept} -> {action}."
        if session.report.markdown:
            session.report.markdown = f"{session.report.markdown.rstrip()}\n\n{note}"
        else:
            session.report.markdown = note

    def _compact_messages(self, session: KIBotSession) -> None:
        if len(session.messages) <= MAX_TURN_MESSAGES:
            return

        older = session.messages[:-MAX_FULL_MESSAGES]
        recent = session.messages[-MAX_FULL_MESSAGES:]
        older_summary = " ".join(
            f"{message.get('role', 'unknown')}: {message.get('content', '')}"
            for message in older
            if isinstance(message, dict)
        )
        if session.memory_summary:
            session.memory_summary = f"{session.memory_summary}\n{older_summary}".strip()
        else:
            session.memory_summary = older_summary.strip()
        session.messages = recent

    def _state_summary(self, session: KIBotSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "message_count": len(session.messages),
            "memory_summary": session.memory_summary,
            "decision_count": len(session.integration_decisions),
            "decisions": {
                str(decision.get("decision_id")): decision.get("action")
                for decision in session.integration_decisions
                if isinstance(decision, dict) and decision.get("decision_id")
            },
            "graph_nodes": {
                str(node.get("id")): node.get("status")
                for node in session.graph_nodes
                if isinstance(node, dict) and node.get("id")
            },
            "report_updated_at": session.report.updated_at,
        }


def _clean_target(value: str) -> str:
    cleaned = re.sub(r"(?i)\b(?:in the lesson|from the lesson|please|concepts?)\b", " ", value)
    return " ".join(cleaned.strip(" .?!'\"").split())


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


def _usage_int(usage: Any, field_name: str) -> int:
    value = getattr(usage, field_name, None)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    secret_prefix = "s" + "k-"
    secret_pattern = rf"{re.escape(secret_prefix)}[A-Za-z0-9_-]+"
    return re.sub(secret_pattern, f"{secret_prefix}REDACTED", message)
