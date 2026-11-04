import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core import auth
from app import main


class AuthTests(unittest.TestCase):
    @staticmethod
    def run_sync_coroutine(coroutine):
        try:
            coroutine.send(None)
        except StopIteration as finished:
            return finished.value
        raise AssertionError("Expected a coroutine with no asynchronous I/O")

    def test_register_login_and_legacy_migration(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            db = str(Path(directory) / "login.db")
            with patch.object(main, "DB_PATH", db), patch.object(auth, "DB_PATH", db):
                main.init_db()
                self.run_sync_coroutine(main.register(main.AuthRequest(username="alice", password="long enough")))
                self.assertTrue(auth.is_admin("alice"))
                self.run_sync_coroutine(main.register(main.AuthRequest(username="bob", password="long enough")))
                self.assertFalse(auth.is_admin("bob"))
                with closing(sqlite3.connect(db)) as conn:
                    stored = conn.execute("SELECT password FROM users WHERE username='alice'").fetchone()[0]
                    self.assertTrue(stored.startswith("pbkdf2_sha256$"))
                    conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("legacy", "old password"))
                    conn.commit()
                result = self.run_sync_coroutine(main.login(main.AuthRequest(username="legacy", password="old password")))
                self.assertEqual(auth.current_user(f"Bearer {result['token']}"), "legacy")
                with closing(sqlite3.connect(db)) as conn:
                    migrated = conn.execute("SELECT password FROM users WHERE username='legacy'").fetchone()[0]
                self.assertTrue(migrated.startswith("pbkdf2_sha256$"))

    def test_password_hash_and_expiring_token(self):
        password = auth.hash_password("a long password")
        self.assertNotIn("a long password", password)
        self.assertTrue(auth.verify_password("a long password", password))
        self.assertFalse(auth.verify_password("incorrect", password))

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            db = str(Path(directory) / "auth.db")
            with closing(sqlite3.connect(db)) as conn:
                conn.execute("CREATE TABLE auth_tokens (token_hash TEXT PRIMARY KEY, username TEXT, expires_at INTEGER)")
                conn.commit()
            with patch.object(auth, "DB_PATH", db):
                token = auth.issue_token("alice")
                self.assertEqual(auth.current_user(f"Bearer {token}"), "alice")
                with closing(sqlite3.connect(db)) as conn:
                    conn.execute("UPDATE auth_tokens SET expires_at=0")
                    conn.commit()
                with self.assertRaises(HTTPException):
                    auth.current_user(f"Bearer {token}")
                next_token = auth.issue_token("alice")
                auth.revoke_token(next_token)
                with self.assertRaises(HTTPException):
                    auth.current_user(f"Bearer {next_token}")


if __name__ == "__main__":
    unittest.main()
