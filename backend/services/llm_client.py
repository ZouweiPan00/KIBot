import json
from typing import Any

import httpx
from pydantic import BaseModel

from backend.core.config import Settings, settings
from backend.schemas.session import TokenUsage


class LLMResponse(BaseModel):
    answer_text: str
    token_usage: TokenUsage
    usage_estimated: bool = False


class LLMClient:
    def __init__(
        self,
        settings: Settings = settings,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._client = client or httpx.Client(transport=transport, timeout=30.0)

    def chat(self, messages: list[dict[str, Any]]) -> LLMResponse:
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required to call the LLM provider")

        payload = {
            "model": self.settings.openai_model,
            "messages": messages,
        }
        url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"

        try:
            response = self._client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM provider request failed: {exc.__class__.__name__}") from exc

        body = self._parse_response_body(response)
        if response.status_code < 200 or response.status_code >= 300:
            message = self._provider_error_message(body) or response.reason_phrase
            raise RuntimeError(f"LLM provider returned {response.status_code}: {message}")

        provider_error = self._provider_error_message(body)
        if provider_error:
            raise RuntimeError(f"LLM provider returned an error: {provider_error}")

        answer_text = self._extract_answer_text(body)
        usage = body.get("usage")
        if isinstance(usage, dict):
            token_usage = self._usage_from_provider(usage)
            usage_estimated = False
        else:
            token_usage = self._estimate_usage(messages, answer_text)
            usage_estimated = True

        return LLMResponse(
            answer_text=answer_text,
            token_usage=token_usage,
            usage_estimated=usage_estimated,
        )

    def close(self) -> None:
        self._client.close()

    def _parse_response_body(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"LLM provider returned {response.status_code} with invalid JSON"
            ) from exc
        if not isinstance(body, dict):
            raise RuntimeError("LLM provider returned an invalid response payload")
        return body

    def _provider_error_message(self, body: dict[str, Any]) -> str | None:
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        if isinstance(error, str):
            return error
        return None

    def _extract_answer_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM provider returned no chat completion choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("LLM provider returned an invalid chat completion choice")

        message = first_choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content

        text = first_choice.get("text")
        if isinstance(text, str):
            return text

        raise RuntimeError("LLM provider returned no answer text")

    def _usage_from_provider(self, usage: dict[str, Any]) -> TokenUsage:
        input_tokens = self._int_token_value(usage.get("prompt_tokens"))
        output_tokens = self._int_token_value(usage.get("completion_tokens"))
        total_tokens = self._int_token_value(usage.get("total_tokens"))
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens

        return TokenUsage(
            calls=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    def _estimate_usage(
        self,
        messages: list[dict[str, Any]],
        answer_text: str,
    ) -> TokenUsage:
        serialized_messages = json.dumps(
            messages,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        input_tokens = self._estimate_tokens(serialized_messages)
        output_tokens = self._estimate_tokens(answer_text)
        return TokenUsage(
            calls=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text) * 0.6)

    def _int_token_value(self, value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value
        return 0
