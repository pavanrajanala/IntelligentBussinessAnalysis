"""
API tests: sign up, sign in, private data, forecast, chat, admin. Exercises the real routes.
Needs `pip install fastapi httpx` (httpx powers FastAPI's TestClient).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `_testenv` is found however the tests are started
import _testenv  # noqa: F401,E402  (must come first)

import importlib.util
import os
import unittest

import db

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "sample_sales.csv")

SIGNUP = {
    "name": "Ravi Kumar", "email": "ravi@example.com", "password": "password123",
    "business_name": "Ravi Stores", "business_type": "Kirana / general store", "customer_mix": ["families", "students"],
    "city": "Chennai", "state": "Tamil Nadu", "pincode": "600001", "latitude": 13.0827, "longitude": 80.2707,
}


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "fastapi not installed")
class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        db.configure(os.environ["DATABASE_URL"])
        import main

        cls.main = main
        cls.TestClient = TestClient
        cls.anon = TestClient(main.app)

    def client(self):
        return self.TestClient(self.main.app)

    def signup(self, c, **over):
        return c.post("/api/auth/signup", json={**SIGNUP, **over})

    # ---- auth ----

    def test_01_protected_routes_need_login(self):
        for path in ("/api/overview", "/api/forecast", "/api/outlook", "/api/data-status", "/api/chat/history", "/api/auth/me"):
            self.assertEqual(self.anon.get(path).status_code, 401, path)
        self.assertEqual(self.anon.get("/api/admin/stats").status_code, 401)

    def test_02_signup_validation(self):
        c = self.client()
        self.assertEqual(self.signup(c, password="short").status_code, 422)
        self.assertEqual(self.signup(c, email="nope").status_code, 422)
        self.assertEqual(self.signup(c, business_name="").status_code, 422)
        self.assertEqual(self.signup(c, state="Narnia").status_code, 422)
        self.assertEqual(self.signup(c, pincode="12").status_code, 422)

    def test_03_signup_login_logout_flow(self):
        c = self.client()
        r = self.signup(c)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["user"]["role"], "user")
        self.assertIn("httponly", r.headers["set-cookie"].lower())
        me = c.get("/api/auth/me").json()
        self.assertEqual(me["profile"]["city"], "Chennai")
        self.assertEqual(me["profile"]["customer_mix"], ["families", "students"])
        self.assertFalse(me["summary"]["has_data"])
        self.assertNotIn("password", r.text)

        self.assertEqual(self.signup(self.client()).status_code, 409)  # duplicate email
        c.post("/api/auth/logout")
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

        bad = self.client().post("/api/auth/login", json={"email": SIGNUP["email"], "password": "wrongwrong"})
        self.assertEqual(bad.status_code, 401)
        good = self.client()
        self.assertEqual(good.post("/api/auth/login", json={"email": "RAVI@example.com", "password": "password123"}).status_code, 200)
        self.assertEqual(good.get("/api/auth/me").status_code, 200)

    def test_04_login_is_rate_limited(self):
        c = self.client()
        self.signup(c, email="limit@example.com")
        codes = [self.client().post("/api/auth/login", json={"email": "limit@example.com", "password": "x" * 9}).status_code for _ in range(10)]
        self.assertIn(429, codes)

    # ---- data, privacy, insights ----

    def test_05_upload_forecast_and_privacy(self):
        a, b = self.client(), self.client()
        self.signup(a, email="a@example.com")
        self.signup(b, email="b@example.com", state="Kerala")

        self.assertEqual(a.post("/api/upload", files={"file": ("x.txt", b"hi")}).status_code, 400)
        bad = a.post("/api/upload", files={"file": ("x.csv", b"date,product\n2026-01-01,A\n")})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("Missing required", bad.json()["detail"])

        with open(SAMPLE, "rb") as f:
            r = a.post("/api/upload", files={"file": ("sample.csv", f)}, data={"mode": "replace"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertGreater(r.json()["rows_saved"], 2000)

        self.assertTrue(a.get("/api/data-status").json()["has_data"])
        self.assertFalse(b.get("/api/data-status").json()["has_data"])  # b sees nothing of a's data
        self.assertFalse(b.get("/api/overview").json()["has_data"])

        ov = a.get("/api/overview").json()
        self.assertTrue(ov["has_data"])
        self.assertGreater(ov["kpi"]["total_revenue"], 0)
        self.assertTrue(ov["declining"])

        fc = a.get("/api/forecast").json()
        self.assertTrue(fc["found"])
        self.assertTrue(all("suggested_order" in p for p in fc["products"]))

        out = a.get("/api/outlook").json()
        self.assertEqual(out["state"], "Tamil Nadu")
        self.assertTrue(out["upcoming"])

        # data survives logging out and back in
        a.post("/api/auth/logout")
        a.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
        self.assertTrue(a.get("/api/data-status").json()["has_data"])
        self.assertEqual(len(a.get("/api/uploads").json()), 1)

        # append mode: same file again adds nothing
        before = a.get("/api/data-status").json()["rows"]
        with open(SAMPLE, "rb") as f:
            a.post("/api/upload", files={"file": ("again.csv", f)}, data={"mode": "append"})
        self.assertEqual(a.get("/api/data-status").json()["rows"], before)

        self.assertEqual(a.delete("/api/data").status_code, 200)
        self.assertFalse(a.get("/api/data-status").json()["has_data"])

    def test_06_profile_update(self):
        c = self.client()
        self.signup(c, email="p@example.com")
        r = c.put("/api/profile", json={"business_name": "New Name", "state": "Kerala", "city": "Kochi", "customer_mix": ["tourists", "bogus"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["profile"]["customer_mix"], ["tourists"])
        self.assertEqual(c.put("/api/profile", json={"business_name": ""}).status_code, 422)

    # ---- chat ----

    def test_07_chat_flow_with_fake_model(self):
        import agent
        c = self.client()
        self.signup(c, email="chat@example.com")
        self.assertEqual(c.post("/api/chat", json={"question": "hello"}).status_code, 400)  # no data yet
        c.post("/api/load-sample")

        seen = {}

        def fake_run(user_id, question, history=None, allow_news=False):
            seen.update(question=question, allow_news=allow_news, history=history)
            return {"answer": "Colgate fell ₹100.", "trace": [{"tool": "get_sales_trend", "arguments": {"product": "Colgate"}}],
                    "sources": [], "used_news": allow_news, "iterations_used": 1}

        original = self.main.run_agent
        self.main.run_agent = fake_run
        try:
            r = c.post("/api/chat", json={"question": "Why is Colgate declining?"})
            self.assertEqual(r.status_code, 200)
            self.assertFalse(seen["allow_news"])  # news off by default
            r = c.post("/api/chat", json={"question": "Any news?", "use_news": True})
            self.assertTrue(seen["allow_news"])
            self.assertEqual(len(seen["history"]), 2)  # previous Q and A passed along
        finally:
            self.main.run_agent = original

        hist = c.get("/api/chat/history").json()
        self.assertEqual([m["role"] for m in hist], ["user", "assistant", "user", "assistant"])
        self.assertEqual(hist[1]["trace"]["trace"][0]["tool"], "get_sales_trend")
        c.delete("/api/chat/history")
        self.assertEqual(c.get("/api/chat/history").json(), [])
        self.assertEqual(c.post("/api/chat", json={"question": ""}).status_code, 422)

    # ---- admin ----

    def test_08_admin_stats_and_permissions(self):
        user = self.client()
        self.signup(user, email="plain@example.com")
        self.assertEqual(user.get("/api/admin/stats").status_code, 403)
        self.assertEqual(user.get("/api/admin/users").status_code, 403)

        admin = self.client()
        self.assertEqual(self.signup(admin, email="boss@example.com", name="Boss").json()["user"]["role"], "admin")
        stats = admin.get("/api/admin/stats").json()
        self.assertGreaterEqual(stats["totals"]["customers"], 3)
        self.assertEqual(len(stats["signups_per_day"]), 30)
        self.assertTrue(stats["business_types"])
        users = admin.get("/api/admin/users").json()
        row = next(u for u in users if u["email"] == "plain@example.com")
        self.assertNotIn("password_hash", row)
        self.assertEqual(admin.get("/api/admin/users", params={"q": "plain@"}).json()[0]["email"], "plain@example.com")

        # suspend: the user is locked out immediately and cannot log in
        self.assertEqual(admin.patch(f"/api/admin/users/{row['id']}", json={"is_active": False}).status_code, 200)
        self.assertEqual(user.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "plain@example.com", "password": "password123"}).status_code, 403)
        admin.patch(f"/api/admin/users/{row['id']}", json={"is_active": True})
        self.assertEqual(user.get("/api/auth/me").status_code, 200)

        me = admin.get("/api/auth/me").json()["user"]
        self.assertEqual(admin.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}).status_code, 400)

    def test_09_delete_account(self):
        c = self.client()
        self.signup(c, email="gone@example.com")
        c.post("/api/load-sample")
        self.assertEqual(c.post("/api/account/delete", json={"password": "wrong-pass"}).status_code, 403)
        self.assertEqual(c.post("/api/account/delete", json={"password": "password123"}).status_code, 200)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.client().post("/api/auth/login", json={"email": "gone@example.com", "password": "password123"}).status_code, 401)

    def test_10_meta_and_headers(self):
        r = self.anon.get("/api/meta")
        self.assertIn("Tamil Nadu", r.json()["states"])
        self.assertEqual(r.headers.get("x-frame-options"), "DENY")
        self.assertEqual(self.anon.get("/api/health").json()["database"], "sqlite")


if __name__ == "__main__":
    unittest.main()
