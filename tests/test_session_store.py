import json
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SessionStoreTest(unittest.TestCase):
    def test_create_session_persists_default_session_json(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))

            session = store.create_session()

            UUID(session.session_id)
            self.assertEqual(session.selected_textbooks, [])
            self.assertEqual(session.textbooks, [])
            self.assertEqual(session.chapters, [])
            self.assertEqual(session.chunks, [])
            self.assertEqual(session.graph_nodes, [])
            self.assertEqual(session.graph_edges, [])
            self.assertEqual(session.integration_decisions, [])
            self.assertEqual(session.messages, [])
            self.assertEqual(session.memory_summary, "")
            self.assertEqual(session.token_usage.total_tokens, 0)
            self.assertEqual(session.report.markdown, "")
            self.assertIsNone(session.report.updated_at)

            session_file = Path(temp_dir) / session.session_id / "session.json"
            self.assertTrue(session_file.exists())
            persisted = json.loads(session_file.read_text(encoding="utf-8"))
            self.assertEqual(persisted["session_id"], session.session_id)

    def test_save_and_get_session_round_trip_mutated_state(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))
            session = store.create_session()
            session.selected_textbooks.append("biology-101")
            session.messages.append({"role": "user", "content": "Explain mitosis"})
            session.memory_summary = "The learner is reviewing cell division."
            session.token_usage.calls = 1
            session.token_usage.input_tokens = 10
            session.token_usage.output_tokens = 20
            session.token_usage.total_tokens = 30
            session.report.markdown = "# Mitosis"
            session.report.updated_at = "2026-05-10T12:00:00Z"

            saved = store.save_session(session)
            loaded = store.get_session(session.session_id)

            self.assertEqual(saved, session)
            self.assertEqual(loaded.selected_textbooks, ["biology-101"])
            self.assertEqual(
                loaded.messages,
                [{"role": "user", "content": "Explain mitosis"}],
            )
            self.assertEqual(
                loaded.memory_summary,
                "The learner is reviewing cell division.",
            )
            self.assertEqual(loaded.token_usage.calls, 1)
            self.assertEqual(loaded.token_usage.total_tokens, 30)
            self.assertEqual(loaded.report.markdown, "# Mitosis")
            self.assertEqual(loaded.report.updated_at, "2026-05-10T12:00:00Z")

    def test_reset_session_preserves_id_and_clears_state(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))
            session = store.create_session()
            session.messages.append({"role": "assistant", "content": "Saved"})
            session.memory_summary = "Saved context"
            session.token_usage.calls = 3
            store.save_session(session)

            reset = store.reset_session(session.session_id)
            loaded = store.get_session(session.session_id)

            self.assertEqual(reset.session_id, session.session_id)
            self.assertEqual(reset.messages, [])
            self.assertEqual(reset.memory_summary, "")
            self.assertEqual(reset.token_usage.calls, 0)
            self.assertEqual(loaded, reset)

    def test_save_rejects_unsafe_session_id_without_writing_outside_storage(self) -> None:
        from backend.schemas.session import KIBotSession
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            storage_dir = base_dir / "sessions"
            escape_file = base_dir / "escape" / "session.json"
            store = SessionStore(storage_dir=storage_dir)

            with self.assertRaises(ValueError):
                store.save_session(KIBotSession(session_id="../escape"))

            self.assertFalse(escape_file.exists())

    def test_save_rejects_absolute_session_id_without_writing_outside_storage(self) -> None:
        from backend.schemas.session import KIBotSession
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            storage_dir = base_dir / "sessions"
            escape_file = base_dir / "absolute" / "session.json"
            store = SessionStore(storage_dir=storage_dir)

            with self.assertRaises(ValueError):
                store.save_session(KIBotSession(session_id=str(base_dir / "absolute")))

            self.assertFalse(escape_file.exists())

    def test_get_and_reset_reject_invalid_session_ids(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))

            with self.assertRaises(ValueError):
                store.get_session("../escape")
            with self.assertRaises(ValueError):
                store.reset_session("/tmp/escape")

    def test_get_missing_valid_session_id_raises_file_not_found(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))

            with self.assertRaises(FileNotFoundError):
                store.get_session(str(uuid4()))

    def test_delete_session_removes_session_directory_and_validates_id(self) -> None:
        from backend.services.session_store import SessionStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(storage_dir=Path(temp_dir))
            session = store.create_session()
            session_dir = Path(temp_dir) / session.session_id

            self.assertTrue(session_dir.exists())
            store.delete_session(session.session_id)

            self.assertFalse(session_dir.exists())
            with self.assertRaises(FileNotFoundError):
                store.get_session(session.session_id)
            with self.assertRaises(ValueError):
                store.delete_session("../escape")


if __name__ == "__main__":
    unittest.main()
