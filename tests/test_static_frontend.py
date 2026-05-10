import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class StaticFrontendTest(unittest.TestCase):
    def test_react_routes_fall_back_without_swallowing_api_routes(self) -> None:
        from fastapi.testclient import TestClient

        from app import create_app

        with tempfile.TemporaryDirectory() as temp_dir:
            dist_dir = Path(temp_dir)
            (dist_dir / "assets").mkdir()
            (dist_dir / "index.html").write_text(
                "<!doctype html><div id=\"root\">KIBot</div>",
                encoding="utf-8",
            )
            (dist_dir / "assets" / "app.js").write_text(
                "console.log('kibot')",
                encoding="utf-8",
            )

            client = TestClient(create_app(frontend_dist_dir=dist_dir))

            api_response = client.get("/api/health")
            self.assertEqual(api_response.status_code, 200)
            self.assertEqual(api_response.json()["status"], "ok")

            frontend_response = client.get("/sessions/demo/graph")
            self.assertEqual(frontend_response.status_code, 200)
            self.assertIn("text/html", frontend_response.headers["content-type"])
            self.assertIn("KIBot", frontend_response.text)

            asset_response = client.get("/assets/app.js")
            self.assertEqual(asset_response.status_code, 200)
            self.assertIn("kibot", asset_response.text)


if __name__ == "__main__":
    unittest.main()
