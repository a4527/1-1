"""인증 · Task 분리 시나리오. 임시 DB에 alembic upgrade head 를 적용해 실행한다.

    uv run python -m unittest discover -s tests
"""
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
DB = Path(_tmp.name) / "test.db"
os.environ["TASKFLOW_DB"] = str(DB)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

API_DIR = Path(__file__).parents[1]
CRED_A = {"email": "a@example.com", "password": "password-a1"}
CRED_B = {"email": "b@example.com", "password": "password-b1"}


def migrate(target: str = "head") -> None:
    subprocess.run(["alembic", "upgrade", target], cwd=API_DIR, check=True, capture_output=True)


def tearDownModule() -> None:
    _tmp.cleanup()


class AuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        migrate()

    def client(self) -> TestClient:
        return TestClient(app, base_url="http://localhost")

    def test_task_api_requires_login(self) -> None:
        c = self.client()
        self.assertEqual(c.get("/api/tasks").status_code, 401)
        self.assertEqual(c.post("/api/tasks", json={"title": "x"}).status_code, 401)
        self.assertEqual(c.patch("/api/tasks/1", json={"title": "x"}).status_code, 401)
        self.assertEqual(c.delete("/api/tasks/1").status_code, 401)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

    def test_signup_login_me_logout(self) -> None:
        c = self.client()
        r = c.post("/api/auth/signup", json={"email": " Flow@Example.com ", "password": "password-1"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["email"], "flow@example.com")
        self.assertNotIn("password", r.text)
        self.assertEqual(c.get("/api/auth/me").json()["email"], "flow@example.com")
        self.assertEqual(c.post("/api/auth/logout").status_code, 204)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)
        self.assertEqual(c.post("/api/auth/signup", json={"email": "flow@example.com", "password": "password-2"}).status_code, 409)
        self.assertEqual(c.post("/api/auth/login", json={"email": "flow@example.com", "password": "wrong-pass1"}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "password-1"}).status_code, 401)
        r = c.post("/api/auth/login", json={"email": "flow@example.com", "password": "password-1"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("hash", r.text)
        self.assertEqual(c.get("/api/auth/me").status_code, 200)

    def test_signup_validation(self) -> None:
        c = self.client()
        self.assertEqual(c.post("/api/auth/signup", json={"email": "not-an-email", "password": "password-1"}).status_code, 422)
        self.assertEqual(c.post("/api/auth/signup", json={"email": "v@example.com", "password": "short"}).status_code, 422)

    def test_isolation_and_scenario(self) -> None:
        a, b = self.client(), self.client()
        self.assertEqual(a.post("/api/auth/signup", json=CRED_A).status_code, 201)
        self.assertEqual(b.post("/api/auth/signup", json=CRED_B).status_code, 201)
        b_task = b.post("/api/tasks", json={"title": "B의 Task"}).json()
        a_task = a.post("/api/tasks", json={"title": "A의 Task"}).json()

        self.assertEqual([t["id"] for t in a.get("/api/tasks").json()], [a_task["id"]])
        self.assertEqual(a.patch(f"/api/tasks/{b_task['id']}", json={"title": "바꿔 보기"}).status_code, 404)
        self.assertEqual(a.patch(f"/api/tasks/{b_task['id']}", json={"status": "done"}).status_code, 404)
        self.assertEqual(a.delete(f"/api/tasks/{b_task['id']}").status_code, 404)
        self.assertEqual(b.get("/api/tasks").json()[0]["title"], "B의 Task")
        self.assertEqual(b.get("/api/tasks").json()[0]["status"], "todo")

        # 로그인 뒤 시나리오: 생성 -> 수정 -> 상태 변경 -> 삭제
        t = a.post("/api/tasks", json={"title": "시나리오"}).json()
        self.assertEqual(a.patch(f"/api/tasks/{t['id']}", json={"title": "수정됨", "priority": "urgent"}).json()["title"], "수정됨")
        self.assertEqual(a.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()["status"], "done")
        self.assertEqual(a.delete(f"/api/tasks/{t['id']}").status_code, 204)
        self.assertEqual(a.delete(f"/api/tasks/{t['id']}").status_code, 404)

        a.post("/api/auth/logout")
        self.assertEqual(a.get("/api/tasks").status_code, 401)

    def test_secrets_not_stored_in_plain(self) -> None:
        c = self.client()
        r = c.post("/api/auth/signup", json={"email": "s@example.com", "password": "plain-secret-1"})
        token = c.cookies.get("taskflow_session")
        self.assertIsNotNone(token)
        self.assertIn("httponly", r.headers["set-cookie"].lower())
        self.assertNotIn(token, r.text)
        conn = sqlite3.connect(DB)
        pw, hashes = conn.execute("select password_hash from users where email='s@example.com'").fetchone()[0], [
            x[0] for x in conn.execute("select token_hash from sessions")
        ]
        conn.close()
        self.assertNotIn("plain-secret-1", pw)
        self.assertTrue(pw.startswith("scrypt$"))
        self.assertNotIn(token, hashes)


class LegacyMigration(unittest.TestCase):
    def test_existing_tasks_get_an_owner_and_can_be_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "legacy.db"
            env = {**os.environ, "TASKFLOW_DB": str(db)}
            subprocess.run(["alembic", "upgrade", "0001"], cwd=API_DIR, check=True, capture_output=True, env=env)
            conn = sqlite3.connect(db)
            conn.executemany("INSERT INTO tasks (title, status) VALUES (?, ?)", [("옛 Task 1", "done"), ("옛 Task 2", "todo")])
            conn.commit()
            conn.close()
            subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True, env=env)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("select count(*) from tasks").fetchone()[0], 2)
            self.assertEqual(conn.execute("select count(*) from tasks where owner_id is null").fetchone()[0], 0)
            self.assertEqual(conn.execute("select count(*) from tasks t join users u on u.id=t.owner_id where u.password_hash is null").fetchone()[0], 2)
            conn.close()


if __name__ == "__main__":
    unittest.main()
