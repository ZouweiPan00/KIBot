import json
import sys
import unittest
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class LLMClientTest(unittest.TestCase):
    def settings(self, base_url: str = "https://llm.example/v1", api_key: str = "test-key"):
        from backend.core.config import Settings

        return Settings(
            _env_file=None,
            openai_base_url=base_url,
            openai_api_key=api_key,
            openai_model="kibot-test-model",
        )

    def client_with_handler(self, handler, base_url: str = "https://llm.example/v1/"):
        from backend.services.llm_client import LLMClient

        transport = httpx.MockTransport(handler)
        return LLMClient(settings=self.settings(base_url=base_url), transport=transport)

    def test_chat_completion_posts_openai_compatible_payload_and_tracks_provider_usage(self) -> None:
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Cells divide in stages."}}],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 5,
                        "total_tokens": 17,
                    },
                },
            )

        client = self.client_with_handler(handler)

        response = client.chat(
            [
                {"role": "system", "content": "Answer briefly."},
                {"role": "user", "content": "What is mitosis?"},
            ]
        )

        self.assertEqual(captured["url"], "https://llm.example/v1/chat/completions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(
            captured["body"],
            {
                "model": "kibot-test-model",
                "messages": [
                    {"role": "system", "content": "Answer briefly."},
                    {"role": "user", "content": "What is mitosis?"},
                ],
            },
        )
        self.assertEqual(response.answer_text, "Cells divide in stages.")
        self.assertFalse(response.usage_estimated)
        self.assertEqual(response.token_usage.calls, 1)
        self.assertEqual(response.token_usage.input_tokens, 12)
        self.assertEqual(response.token_usage.output_tokens, 5)
        self.assertEqual(response.token_usage.total_tokens, 17)

    def test_chat_completion_estimates_usage_when_provider_omits_usage(self) -> None:
        messages = [{"role": "user", "content": "Summarize ATP."}]
        answer = "ATP stores energy."

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": answer}}]},
            )

        client = self.client_with_handler(handler, base_url="https://llm.example/v1")

        response = client.chat(messages)

        serialized_messages = json.dumps(
            messages,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        expected_input_tokens = int(len(serialized_messages) * 0.6)
        expected_output_tokens = int(len(answer) * 0.6)
        self.assertTrue(response.usage_estimated)
        self.assertEqual(response.token_usage.calls, 1)
        self.assertEqual(response.token_usage.input_tokens, expected_input_tokens)
        self.assertEqual(response.token_usage.output_tokens, expected_output_tokens)
        self.assertEqual(
            response.token_usage.total_tokens,
            expected_input_tokens + expected_output_tokens,
        )

    def test_missing_api_key_raises_value_error_without_sending_request(self) -> None:
        from backend.services.llm_client import LLMClient

        requests = []
        transport = httpx.MockTransport(lambda request: requests.append(request))
        client = LLMClient(settings=self.settings(api_key=""), transport=transport)

        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            client.chat([{"role": "user", "content": "Hello"}])

        self.assertEqual(requests, [])

    def test_provider_http_error_raises_runtime_error_without_api_key(self) -> None:
        secret_key = "sk-test-secret"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        client = self.client_with_handler(handler)
        client.settings.openai_api_key = secret_key

        with self.assertRaises(RuntimeError) as raised:
            client.chat([{"role": "user", "content": "Hello"}])

        self.assertIn("LLM provider returned 401", str(raised.exception))
        self.assertNotIn(secret_key, str(raised.exception))

    def test_provider_error_payload_raises_runtime_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"error": {"message": "Model unavailable"}})

        client = self.client_with_handler(handler)

        with self.assertRaisesRegex(RuntimeError, "Model unavailable"):
            client.chat([{"role": "user", "content": "Hello"}])


if __name__ == "__main__":
    unittest.main()
