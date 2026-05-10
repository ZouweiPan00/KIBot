import sys
import tempfile
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

        from fastapi.testclient import TestClient
        from app import app

        response = TestClient(app).get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "KIBot"})

    def test_settings_runtime_defaults(self) -> None:
        self.assertTrue(
            (ROOT / "backend/core/config.py").exists(),
            "backend/core/config.py should define Settings",
        )

        from backend.core.config import Settings
        settings = Settings(_env_file=None)

        self.assertEqual(settings.openai_base_url, "https://example.com/v1")
        self.assertEqual(settings.openai_api_key, "")
        self.assertEqual(settings.openai_model, "gpt-5.4-mini")
        self.assertEqual(settings.session_storage_dir, "data/sessions")
        self.assertEqual(settings.app_host, "0.0.0.0")
        self.assertEqual(settings.app_port, 7860)

    def test_settings_ignore_unrelated_env_keys(self) -> None:
        from backend.core.config import Settings

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as env_file:
            env_file.write("UNRELATED_SETTING=ignored\n")
            env_file.flush()

            settings = Settings(_env_file=env_file.name)

        self.assertEqual(settings.openai_api_key, "")


if __name__ == "__main__":
    unittest.main()
