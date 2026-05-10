import json
from typing import Any

from backend.tools import session_value
from backend.tools.decision_tool import get_integration_decisions
from backend.tools.report_tool import get_report
from backend.tools.stats_tool import (
    get_compression_stats,
    get_graph_summary,
    get_token_usage,
)
from backend.tools.textbook_tool import get_selected_textbooks


class KIBotOrchestrator:
    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def build_context(self, session: Any) -> dict[str, Any]:
        return {
            "session_id": session_value(session, "session_id", ""),
            "selected_textbooks": get_selected_textbooks(session),
            "compression_stats": get_compression_stats(session),
            "token_usage": get_token_usage(session),
            "graph_summary": get_graph_summary(session),
            "integration_decisions": get_integration_decisions(session),
            "report": get_report(session),
            "memory_summary": session_value(session, "memory_summary", "") or "",
        }

    def answer(self, session: Any, teacher_message: str) -> dict[str, Any]:
        context = self.build_context(session)
        if not self._should_call_llm(teacher_message):
            return {
                "answer": self._deterministic_summary(context),
                "context": context,
                "used_llm": False,
            }

        if self.llm_client is None:
            return {
                "answer": (
                    "No LLM client is configured. "
                    f"{self._deterministic_summary(context)}"
                ),
                "context": context,
                "used_llm": False,
            }

        response = self.llm_client.chat(self._build_messages(context, teacher_message))
        return {
            "answer": getattr(response, "answer_text", str(response)),
            "context": context,
            "used_llm": True,
        }

    def _should_call_llm(self, teacher_message: str) -> bool:
        normalized = teacher_message.strip().lower()
        if not normalized:
            return False

        deterministic_terms = (
            "status",
            "stats",
            "summary",
            "current",
            "show",
            "token",
            "compression",
            "graph",
        )
        explanatory_terms = ("why", "explain", "reason", "怎么", "为什么", "解释")

        if any(term in normalized for term in explanatory_terms):
            return True
        return not any(term in normalized for term in deterministic_terms)

    def _build_messages(
        self,
        context: dict[str, Any],
        teacher_message: str,
    ) -> list[dict[str, str]]:
        context_json = json.dumps(context, ensure_ascii=False, sort_keys=True)
        return [
            {
                "role": "system",
                "content": (
                    "You are KIBot, a session-grounded textbook integration assistant. "
                    "Use only the provided session context. Do not invent API keys, files, "
                    "or persisted changes."
                ),
            },
            {
                "role": "user",
                "content": f"Session context:\n{context_json}\n\nTeacher message:\n{teacher_message}",
            },
        ]

    def _deterministic_summary(self, context: dict[str, Any]) -> str:
        selected_count = len(context["selected_textbooks"])
        decision_count = len(context["integration_decisions"])
        graph_summary = context["graph_summary"]
        compression_stats = context["compression_stats"]
        return (
            f"{selected_count} {_plural('selected textbook', selected_count)}, "
            f"{decision_count} {_plural('integration decision', decision_count)}, "
            f"{graph_summary['node_count']} graph {_plural('node', graph_summary['node_count'])}, "
            f"{graph_summary['edge_count']} graph {_plural('edge', graph_summary['edge_count'])}, "
            f"compression ratio {compression_stats['compression_ratio']:.2f}."
        )


def _plural(label: str, count: int) -> str:
    return label if count == 1 else f"{label}s"
