import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TextbooksApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        from backend.services.session_store import SessionStore

        self.store = SessionStore(storage_dir=Path(self.temp_dir.name))
        self.app = None
        self.session_dependency = None
        self.textbooks_dependency = None

    def tearDown(self) -> None:
        if self.app is not None:
            if self.session_dependency is not None:
                self.app.dependency_overrides.pop(self.session_dependency, None)
            if self.textbooks_dependency is not None:
                self.app.dependency_overrides.pop(self.textbooks_dependency, None)
        self.temp_dir.cleanup()

    def client(self, *, raise_server_exceptions: bool = True):
        import backend.api.session as session_api
        import backend.api.textbooks as textbooks_api

        from app import app
        from fastapi.testclient import TestClient

        app.dependency_overrides[session_api.get_session_store] = lambda: self.store
        app.dependency_overrides[textbooks_api.get_session_store] = lambda: self.store
        self.app = app
        self.session_dependency = session_api.get_session_store
        self.textbooks_dependency = textbooks_api.get_session_store
        return TestClient(app, raise_server_exceptions=raise_server_exceptions)

    def test_upload_textbook_parses_file_saves_upload_and_updates_session(self) -> None:
        client = self.client()
        session = self.store.create_session()
        content = "第一章 开始\n上传后的教材内容。"

        response = client.post(
            "/api/textbooks/upload",
            data={"session_id": session.session_id},
            files={
                "file": (
                    "../Unsafe Name.txt",
                    content.encode("utf-8"),
                    "text/plain",
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        parsed = response.json()
        self.assertEqual(parsed["filename"], "Unsafe Name.txt")
        self.assertEqual(parsed["file_type"], "txt")
        self.assertEqual(parsed["status"], "parsed")
        self.assertEqual(parsed["total_pages"], 1)
        self.assertEqual(parsed["total_chars"], len(content))
        self.assertEqual(parsed["chapters"][0]["title"], "第一章 开始")
        self.assertNotIn("textbook_id", parsed["chapters"][0])

        upload_dir = Path(self.temp_dir.name) / session.session_id / "uploads"
        [upload_path] = list(upload_dir.rglob(parsed["filename"]))
        self.assertTrue(upload_path.exists())
        self.assertEqual(upload_path.read_text(encoding="utf-8"), content)

        saved = self.store.get_session(session.session_id)
        self.assertEqual(len(saved.textbooks), 1)
        self.assertEqual(saved.textbooks[0]["textbook_id"], parsed["textbook_id"])
        self.assertEqual(saved.textbooks[0]["filename"], "Unsafe Name.txt")
        self.assertEqual(len(saved.chapters), 1)
        self.assertEqual(saved.chapters[0]["textbook_id"], parsed["textbook_id"])
        self.assertEqual(saved.chapters[0]["title"], "第一章 开始")

    def test_uploading_same_original_filename_keeps_distinct_upload_files(self) -> None:
        client = self.client()
        session = self.store.create_session()
        first_content = "第一章 第一次\n第一份教材内容。"
        second_content = "第一章 第二次\n第二份教材内容。"

        first = client.post(
            "/api/textbooks/upload",
            data={"session_id": session.session_id},
            files={
                "file": (
                    "collision.txt",
                    first_content.encode("utf-8"),
                    "text/plain",
                )
            },
        )
        second = client.post(
            "/api/textbooks/upload",
            data={"session_id": session.session_id},
            files={
                "file": (
                    "collision.txt",
                    second_content.encode("utf-8"),
                    "text/plain",
                )
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_payload = first.json()
        second_payload = second.json()
        self.assertNotEqual(first_payload["textbook_id"], second_payload["textbook_id"])

        saved = self.store.get_session(session.session_id)
        self.assertEqual(len(saved.textbooks), 2)
        self.assertEqual(
            [textbook["textbook_id"] for textbook in saved.textbooks],
            [first_payload["textbook_id"], second_payload["textbook_id"]],
        )

        upload_dir = Path(self.temp_dir.name) / session.session_id / "uploads"
        stored_files = sorted(path for path in upload_dir.rglob("*.txt") if path.is_file())
        self.assertEqual(len(stored_files), 2)
        self.assertEqual(
            sorted(path.read_text(encoding="utf-8") for path in stored_files),
            sorted([first_content, second_content]),
        )

    def test_upload_accepts_session_id_from_query(self) -> None:
        client = self.client()
        session = self.store.create_session()

        response = client.post(
            f"/api/textbooks/upload?session_id={session.session_id}",
            files={"file": ("notes.md", b"# Notes", "text/markdown")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["file_type"], "md")

    def test_upload_rejects_invalid_unknown_and_unsupported_requests(self) -> None:
        client = self.client()
        session = self.store.create_session()

        invalid = client.post(
            "/api/textbooks/upload",
            data={"session_id": "not-a-uuid"},
            files={"file": ("book.txt", b"text", "text/plain")},
        )
        self.assertEqual(invalid.status_code, 400)

        unknown = client.post(
            "/api/textbooks/upload",
            data={"session_id": str(uuid4())},
            files={"file": ("book.txt", b"text", "text/plain")},
        )
        self.assertEqual(unknown.status_code, 404)

        unsupported = client.post(
            "/api/textbooks/upload",
            data={"session_id": session.session_id},
            files={"file": ("slides.docx", b"text", "application/octet-stream")},
        )
        self.assertEqual(unsupported.status_code, 400)

    def test_upload_invalid_pdf_returns_400_and_removes_failed_upload(self) -> None:
        client = self.client(raise_server_exceptions=False)
        session = self.store.create_session()

        response = client.post(
            "/api/textbooks/upload",
            data={"session_id": session.session_id},
            files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.get_session(session.session_id).textbooks, [])

        upload_dir = Path(self.temp_dir.name) / session.session_id / "uploads"
        stored_files = list(upload_dir.rglob("*")) if upload_dir.exists() else []
        self.assertEqual([path for path in stored_files if path.is_file()], [])

    def test_list_select_and_delete_textbooks_update_session_state(self) -> None:
        client = self.client()
        session = self.store.create_session()
        session.textbooks.extend(
            [
                {
                    "textbook_id": "book-1",
                    "filename": "one.txt",
                    "title": "one",
                    "file_type": "txt",
                    "total_pages": 1,
                    "total_chars": 3,
                    "chapters": [],
                    "status": "parsed",
                },
                {
                    "textbook_id": "book-2",
                    "filename": "two.txt",
                    "title": "two",
                    "file_type": "txt",
                    "total_pages": 1,
                    "total_chars": 3,
                    "chapters": [],
                    "status": "parsed",
                },
            ]
        )
        session.selected_textbooks.append("book-2")
        session.chapters.extend(
            [
                {"chapter_id": "chapter-1", "textbook_id": "book-1", "title": "一"},
                {"chapter_id": "chapter-2", "textbook_id": "book-2", "title": "二"},
            ]
        )
        self.store.save_session(session)

        listed = client.get(f"/api/textbooks?session_id={session.session_id}")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            [textbook["textbook_id"] for textbook in listed.json()],
            ["book-1", "book-2"],
        )

        selected = client.post(
            f"/api/textbooks/book-1/select?session_id={session.session_id}"
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(
            self.store.get_session(session.session_id).selected_textbooks,
            ["book-2", "book-1"],
        )

        selected_again = client.post(
            f"/api/textbooks/book-1/select?session_id={session.session_id}"
        )
        self.assertEqual(selected_again.status_code, 200)
        self.assertEqual(
            self.store.get_session(session.session_id).selected_textbooks,
            ["book-2", "book-1"],
        )

        deleted = client.delete(
            f"/api/textbooks/book-1?session_id={session.session_id}"
        )
        self.assertEqual(deleted.status_code, 200)

        saved = self.store.get_session(session.session_id)
        self.assertEqual(
            [textbook["textbook_id"] for textbook in saved.textbooks],
            ["book-2"],
        )
        self.assertEqual(saved.selected_textbooks, ["book-2"])
        self.assertEqual(
            [chapter["chapter_id"] for chapter in saved.chapters],
            ["chapter-2"],
        )

    def test_management_endpoints_validate_session_id(self) -> None:
        client = self.client()

        invalid = client.get("/api/textbooks?session_id=not-a-uuid")
        self.assertEqual(invalid.status_code, 400)

        unknown = client.get(f"/api/textbooks?session_id={uuid4()}")
        self.assertEqual(unknown.status_code, 404)


if __name__ == "__main__":
    unittest.main()
