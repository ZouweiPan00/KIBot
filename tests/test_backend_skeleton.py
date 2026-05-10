import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class BackendSkeletonTest(unittest.TestCase):
    def test_health_endpoint_returns_ok_service(self) -> None:
        self.assertTrue(
            (ROOT / "app.py").exists(),
            "app.py should define the FastAPI application",
        )

        try:
            from fastapi.testclient import TestClient
        except ModuleNotFoundError as exc:
            if exc.name == "fastapi":
                self.skipTest("fastapi is not installed")
            raise

        from app import app

        response = TestClient(app).get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "KIBot"})

    def test_settings_defaults_match_env_example(self) -> None:
        self.assertTrue(
            (ROOT / "backend/core/config.py").exists(),
            "backend/core/config.py should define Settings",
        )

        try:
            from backend.core.config import Settings
        except ModuleNotFoundError as exc:
            if exc.name in {"pydantic", "pydantic_settings"}:
                self.skipTest(f"{exc.name} is not installed")
            raise

        settings = Settings(_env_file=None)

        self.assertEqual(settings.openai_base_url, "https://example.com/v1")
        self.assertEqual(settings.openai_api_key, "replace_me")
        self.assertEqual(settings.openai_model, "gpt-4o-mini")
        self.assertEqual(settings.session_storage_dir, "data/sessions")
        self.assertEqual(settings.app_host, "0.0.0.0")
        self.assertEqual(settings.app_port, 7860)


if __name__ == "__main__":
    unittest.main()
