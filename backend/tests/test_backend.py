"""
Unit tests. Run from the backend folder:

    python -m unittest discover -s tests -v

No API keys or internet needed (the LLM is replaced by a fake client).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # so `_testenv` is found however the tests are started
import _testenv  # noqa: F401,E402  (must come first: points the app at a temporary database)

import os
import types
import unittest
from datetime import date
from io import StringIO

import pandas as pd

import agent
import aggregate
import clean
import db
import forecast
import repo
import security
import seasonal
import tools

db.configure(os.environ["DATABASE_URL"])
db.init_schema()

DIRTY_CSV = """Date,Product Name,Category,Qty,Unit Price,Customer,Region
2026-01-05,colgate ,Oral Care,2,100,c1,Chennai
2026-01-06,Colgate,Oral Care,,100,c2,Chennai
2026-01-06,Colgate,Oral Care,,100,c2,Chennai
2026-02-10,Pepsodent,Oral Care,3,90,c1,Chennai
2026-02-11,Pepsodent,Oral Care,500,90,c3,Chennai
2026-02-12,Pepsodent,Oral Care,2,90,c3,Chennai
2026-02-13,Pepsodent,Oral Care,3,90,c4,Chennai
2026-02-14,Pepsodent,Oral Care,2,90,c5,Chennai
12/03/2026,Colgate,Oral Care,1,100,c1,Chennai
garbage,Colgate,Oral Care,1,100,c1,Chennai
2026-03-01,Colgate,Oral Care,1,abc,c1,Chennai
2026-03-02,Colgate,Oral Care,-4,100,c1,Chennai
"""


def _clean(csv_text):
    return clean.clean_sales_data(pd.read_csv(StringIO(csv_text)))


def _new_user(email):
    return repo.create_user(email, "Test", security.hash_password("password123"))


class CleaningTests(unittest.TestCase):
    def test_pipeline_fixes_messy_data(self):
        df, report = _clean(DIRTY_CSV)
        self.assertIn("Colgate", set(df["product"]))
        self.assertEqual(report["rows_with_unparseable_dates"], 1)
        self.assertEqual(report["rows_with_invalid_price_dropped"], 1)
        self.assertEqual(report["rows_with_invalid_quantity_dropped"], 1)
        self.assertEqual(report["duplicate_rows_removed"], 1)
        self.assertEqual(report["outliers_flagged"], 1)
        self.assertEqual(report["rows_with_missing_quantity_filled"], 2)
        self.assertFalse(df["quantity"].isna().any())

    def test_iso_dates_not_flipped_but_slash_dates_are_day_first(self):
        df, _ = _clean("date,product,quantity,price\n2026-09-12,A,1,10\n05/03/2026,A,1,10\n")
        self.assertEqual(sorted(df["date"].dt.strftime("%Y-%m-%d")), ["2026-03-05", "2026-09-12"])

    def test_missing_required_column_gives_friendly_error(self):
        with self.assertRaises(ValueError) as ctx:
            _clean("date,product,quantity\n2026-01-01,A,1\n")
        self.assertIn("price", str(ctx.exception))

    def test_empty_file_rejected(self):
        with self.assertRaises(ValueError):
            clean.clean_sales_data(pd.DataFrame())


class SecurityTests(unittest.TestCase):
    def test_password_hash_roundtrip(self):
        h = security.hash_password("correct horse")
        self.assertTrue(security.verify_password("correct horse", h))
        self.assertFalse(security.verify_password("wrong", h))
        self.assertNotEqual(h, security.hash_password("correct horse"))  # random salt
        self.assertFalse(security.verify_password("x", "garbage"))

    def test_token_roundtrip_tamper_and_expiry(self):
        t = security.make_token("user-1")
        self.assertEqual(security.read_token(t), "user-1")
        body, sig = t.split(".")
        self.assertIsNone(security.read_token(body + "." + sig[:-2] + "aa"))
        self.assertIsNone(security.read_token(None))
        self.assertIsNone(security.read_token(security.make_token("u", days=-1)))

    def test_rate_limiter(self):
        rl = security.RateLimiter(limit=2, window_seconds=60)
        rl.add("k"); self.assertFalse(rl.blocked("k"))
        rl.add("k"); self.assertTrue(rl.blocked("k"))
        rl.reset("k"); self.assertFalse(rl.blocked("k"))


class PerUserDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = ["date,product,category,quantity,price,customer_id"]
        for m, custs in ((1, "c1 c2 c3 c4"), (2, "c1 c2 c3 c4"), (3, "c1"), (4, "c1")):
            for c in custs.split():
                rows.append(f"2026-0{m}-10,Colgate,Oral Care,2,100,{c}")
        for m in (3, 4):
            for c in ("c2", "c3", "c4"):
                rows.append(f"2026-0{m}-12,Pepsodent,Oral Care,2,90,{c}")
        cls.df, _ = _clean("\n".join(rows))
        cls.alice = _new_user("alice@example.com")
        cls.bob = _new_user("bob@example.com")
        repo.save_sales(cls.alice["id"], cls.df)

    def test_data_is_private_per_user(self):
        self.assertTrue(repo.data_summary(self.alice["id"])["has_data"])
        self.assertFalse(repo.data_summary(self.bob["id"])["has_data"])
        self.assertTrue(tools.get_sales_trend(self.alice["id"], "Colgate")["found"])
        self.assertFalse(tools.get_sales_trend(self.bob["id"], "Colgate")["found"])

    def test_append_mode_dedupes_and_replace_overwrites(self):
        carol = _new_user("carol@example.com")
        n = repo.save_sales(carol["id"], self.df)
        self.assertEqual(repo.save_sales(carol["id"], self.df, "append"), n)  # exact duplicates dropped
        extra, _ = _clean("date,product,category,quantity,price,customer_id\n2026-05-01,Lux,Soap,3,40,c9\n")
        self.assertEqual(repo.save_sales(carol["id"], extra, "append"), n + 1)
        self.assertEqual(repo.save_sales(carol["id"], extra, "replace"), 1)

    def test_profile_roundtrip(self):
        repo.save_profile(self.alice["id"], {"business_name": "Alice Stores", "business_type": "Kirana / general store",
                                             "customer_mix": ["students"], "state": "Tamil Nadu", "latitude": 13.08, "longitude": 80.27})
        p = repo.get_profile(self.alice["id"])
        self.assertEqual(p["business_name"], "Alice Stores")
        self.assertEqual(p["customer_mix"], ["students"])
        self.assertAlmostEqual(p["latitude"], 13.08)

    def test_aggregates_and_tools(self):
        df = repo.read_sales(self.alice["id"], True)
        self.assertEqual(len(aggregate.revenue_trend(df)), 4)
        self.assertEqual(aggregate.declining_products(df)[0]["product"], "Colgate")
        self.assertEqual(tools.find_customer_switching(self.alice["id"], "Colgate")["top_switched_to"][0]["product"], "Pepsodent")
        self.assertTrue(tools.get_sales_trend(self.alice["id"], "Colgat")["found"])  # typo tolerated

    def test_delete_user_removes_everything(self):
        dave = _new_user("dave@example.com")
        repo.save_sales(dave["id"], self.df)
        repo.add_chat(dave["id"], "user", "hi")
        repo.delete_user(dave["id"])
        self.assertIsNone(repo.get_user(dave["id"]))
        self.assertFalse(repo.data_summary(dave["id"])["has_data"])
        self.assertEqual(repo.recent_chat(dave["id"]), [])


def _monthly_df(product, category, units_by_month, year=2026, price=10.0):
    rows = []
    for m, units in units_by_month.items():
        rows.append({"date": pd.Timestamp(year=year, month=m, day=15), "product": product, "category": category,
                     "quantity": float(units), "price": price, "customer_id": "c1", "region": "x", "is_outlier": False,
                     "revenue": float(units) * price})
    return pd.DataFrame(rows)


class SeasonalTests(unittest.TestCase):
    def test_classification_uses_word_starts(self):
        self.assertIn("home_care", seasonal.classify_product("Toilet cleaner", "Home"))
        self.assertNotIn("oil_ghee", seasonal.classify_product("Toilet cleaner", "Home"))
        self.assertIn("hot_beverages", seasonal.classify_product("Tata Tea", "Beverages"))
        self.assertEqual(seasonal.classify_product("Capsicum", ""), set())

    def test_festival_is_regional(self):
        names = lambda state: {f["name"] for f in seasonal.festivals_between(date(2027, 9, 1), date(2027, 9, 30), state)}  # noqa: E731
        self.assertIn("Onam", names("Kerala"))
        self.assertNotIn("Onam", names("Punjab"))
        self.assertIn("Ganesh Chaturthi", names("Maharashtra"))

    def test_festival_raises_multiplier(self):
        mult, reasons = seasonal.demand_multiplier({"sweets"}, date(2026, 11, 1), "Delhi")
        self.assertGreater(mult, 1.3)
        self.assertTrue(any("Diwali" in r for r in reasons))

    def test_outlook_lists_upcoming_festivals_with_own_products(self):
        df = _monthly_df("Haldiram Sweets", "Sweets", {8: 50, 9: 60})
        out = seasonal.build_outlook(df, {"state": "Delhi", "customer_mix": ["students"]}, date(2026, 10, 17))
        diwali = next(f for f in out["upcoming"] if f["name"] == "Diwali")
        self.assertEqual(diwali["days_away"], 22)
        sweets = next(i for i in diwali["items"] if i["group"].startswith("Sweets"))
        self.assertIn("Haldiram Sweets", sweets["your_products"])
        self.assertTrue(out["tips"])


class ForecastTests(unittest.TestCase):
    def test_rising_product_is_ordered_more(self):
        df = _monthly_df("Widget", "Misc", {3: 100, 4: 120, 5: 140, 6: 160, 7: 180, 8: 200})
        res = forecast.predict_next_month(df, {"state": "Delhi"}, date(2026, 9, 10))
        row = res["products"][0]
        self.assertEqual(res["target_month"], "2026-10")
        self.assertGreater(row["forecast_units"], 200)
        self.assertEqual(row["action"], "Order more")
        self.assertGreaterEqual(row["suggested_order"], row["forecast_units"])

    def test_festival_month_adds_buffer_and_reason(self):
        df = _monthly_df("Kaju Katli", "Sweets", {6: 100, 7: 100, 8: 100, 9: 100})
        res = forecast.predict_next_month(df, {"state": "Delhi"}, date(2026, 10, 10))
        row = res["products"][0]
        self.assertTrue(any("Diwali" in w for w in row["why"]))
        self.assertGreater(row["forecast_units"], 130)

    def test_incomplete_last_month_is_ignored(self):
        df = _monthly_df("Widget", "Misc", {6: 100, 7: 100, 8: 100})
        partial = _monthly_df("Widget", "Misc", {9: 10})
        partial["date"] = pd.Timestamp(year=2026, month=9, day=3)
        res = forecast.predict_next_month(pd.concat([df, partial]), {}, date(2026, 9, 20))
        self.assertTrue(res["warnings"])
        self.assertAlmostEqual(res["products"][0]["forecast_units"], 100, delta=15)

    def test_no_data(self):
        self.assertFalse(forecast.predict_next_month(pd.DataFrame(), {})["found"])


# ---------- Agent with a fake LLM ----------

def _tool_call(call_id, name, arguments):
    return types.SimpleNamespace(id=call_id, function=types.SimpleNamespace(name=name, arguments=arguments))


def _response(content=None, tool_calls=None):
    msg = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = _new_user("agent@example.com")
        df, _ = _clean("date,product,category,quantity,price,customer_id\n" + "\n".join(
            f"2026-0{m}-10,Colgate,Oral Care,{q},100,c{m}" for m, q in ((1, 5), (2, 4), (3, 3), (4, 2))))
        repo.save_sales(cls.user["id"], df)

    def setUp(self):
        os.environ["GROQ_API_KEY"] = "test-key"
        agent.time.sleep = lambda *_: None
        self._orig = agent._make_client

    def tearDown(self):
        agent._make_client = self._orig

    def _use(self, client):
        agent._make_client = lambda: client

    def test_tool_then_answer_is_plain_and_in_rupees(self):
        client = FakeClient([
            _response(tool_calls=[_tool_call("1", "get_sales_trend", '{"product": "Colgate"}')]),
            _response(content="**Colgate** earned $1,400 and Rs. 200. See https://example.com"),
        ])
        self._use(client)
        out = agent.run_agent(self.user["id"], "Why is Colgate declining?")
        self.assertEqual(out["answer"], "Colgate earned ₹1,400 and ₹200. See")
        self.assertEqual(out["trace"][0]["tool"], "get_sales_trend")
        self.assertNotIn("result", out["trace"][0])  # full results are not sent to the browser

    def test_news_tool_hidden_unless_requested(self):
        names = lambda call: {t["function"]["name"] for t in call["tools"]}  # noqa: E731
        c1 = FakeClient([_response(content="ok")]); self._use(c1)
        agent.run_agent(self.user["id"], "Why is Colgate declining?")
        self.assertNotIn("check_external_news", names(c1.calls[0]))
        self.assertIn("switched off", c1.calls[0]["messages"][0]["content"])

        c2 = FakeClient([_response(content="ok")]); self._use(c2)
        agent.run_agent(self.user["id"], "Why is Colgate declining?", allow_news=True)
        self.assertIn("check_external_news", names(c2.calls[0]))

        c3 = FakeClient([_response(content="ok")]); self._use(c3)
        agent.run_agent(self.user["id"], "Any news about Colgate?")  # wording alone enables it
        self.assertIn("check_external_news", names(c3.calls[0]))

    def test_model_cannot_call_news_when_off_or_pick_another_user(self):
        client = FakeClient([
            _response(tool_calls=[_tool_call("1", "check_external_news", '{"product": "Colgate"}'),
                                  _tool_call("2", "get_sales_trend", '{"product": "Colgate", "user_id": "someone-else"}')]),
            _response(content="Done."),
        ])
        self._use(client)
        out = agent.run_agent(self.user["id"], "Why is Colgate declining?")
        self.assertTrue(out["trace"][0].get("error"))      # news tool refused
        self.assertFalse(out["trace"][1].get("error"))     # trend ran with the real user id

    def test_news_sources_are_collected(self):
        orig = agent.TOOL_FUNCTIONS["check_external_news"]
        agent.TOOL_FUNCTIONS["check_external_news"] = lambda uid, product: {
            "found": True, "search_summary": "x",
            "articles": [{"title": "T", "source": "example.com", "snippet": "s", "url": "https://example.com/a"}]}
        try:
            client = FakeClient([
                _response(tool_calls=[_tool_call("1", "check_external_news", '{"product": "Colgate"}')]),
                _response(content="No problem found (example.com)."),
            ])
            self._use(client)
            out = agent.run_agent(self.user["id"], "check news for Colgate")
        finally:
            agent.TOOL_FUNCTIONS["check_external_news"] = orig
        self.assertTrue(out["used_news"])
        self.assertEqual(out["sources"][0]["url"], "https://example.com/a")

    def test_news_tool_returns_summary_and_is_cached(self):
        import tools
        from unittest import mock
        calls = []

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"answer": "Colgate faced no recall; prices rose slightly.",
                        "results": [{"title": "Colgate prices", "url": "https://www.example.com/a", "content": "x" * 900}]}

        def fake_post(url, **kw):
            calls.append(kw["json"]["query"])
            return FakeResp()

        tools._NEWS_CACHE.clear()
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "k"}), mock.patch("requests.post", fake_post):
            first = tools.check_external_news(self.user["id"], "Colgate")
            again = tools.check_external_news(self.user["id"], " colgate ")
            other = tools.check_external_news(self.user["id"], "Lux")
        tools._NEWS_CACHE.clear()
        self.assertEqual(first["search_summary"], "Colgate faced no recall; prices rose slightly.")
        self.assertEqual(first["articles"][0]["source"], "example.com")
        self.assertLessEqual(len(first["articles"][0]["snippet"]), 450)
        self.assertEqual(len(calls), 2)  # Colgate once (second call came from the cache), Lux once
        self.assertEqual(again, first)
        self.assertTrue(other["found"])

    def test_history_is_sent_for_follow_ups(self):
        client = FakeClient([_response(content="ok")]); self._use(client)
        agent.run_agent(self.user["id"], "and next month?", history=[{"role": "user", "content": "Tell me about Colgate"}, {"role": "assistant", "content": "It is falling."}])
        roles = [m["role"] for m in client.calls[0]["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])

    def test_empty_arguments_and_bad_arguments(self):
        client = FakeClient([
            _response(tool_calls=[_tool_call("1", "get_category_performance", ""), _tool_call("2", "get_sales_trend", "{not json"),
                                  _tool_call("3", "nope", "{}")]),
            _response(content="Done."),
        ])
        self._use(client)
        out = agent.run_agent(self.user["id"], "x")
        self.assertFalse(out["trace"][0].get("error"))
        self.assertTrue(out["trace"][1].get("error") and out["trace"][2].get("error"))

    def test_retry_then_give_up(self):
        self._use(FakeClient([RuntimeError("boom"), _response(content="Recovered.")]))
        self.assertEqual(agent.run_agent(self.user["id"], "hi")["answer"], "Recovered.")
        self._use(FakeClient([RuntimeError("down")] * agent.MAX_RETRIES_PER_CALL))
        self.assertIn("did not respond", agent.run_agent(self.user["id"], "hi")["answer"])

    def test_last_turn_forbids_tools(self):
        loop = [_response(tool_calls=[_tool_call(str(i), "compare_periods", "{}")]) for i in range(agent.MAX_ITERATIONS - 1)]
        client = FakeClient(loop + [_response(content="Final answer.")]); self._use(client)
        self.assertEqual(agent.run_agent(self.user["id"], "loop")["answer"], "Final answer.")
        self.assertNotIn("tools", client.calls[-1])

    def test_new_tools_run(self):
        self.assertTrue(tools.forecast_next_month(self.user["id"])["found"])
        out = tools.festival_outlook(self.user["id"])
        self.assertTrue(out["found"])


class RupeeTests(unittest.TestCase):
    def test_all_currency_forms_become_rupees(self):
        cases = {
            "Revenue was $12,500": "Revenue was ₹12,500",
            "Rs. 3,000 and Rs 40": "₹3,000 and ₹40",
            "INR 4500": "₹4500",
            "2,000 rupees": "₹2,000",
            "7500 USD": "₹7500",
            "5 dollars": "₹5",
            "Sold 120 units": "Sold 120 units",
        }
        for src, want in cases.items():
            self.assertEqual(agent._plain_text(src), want, src)


class SpeedTests(unittest.TestCase):
    """Reused connections and short caches (what keeps pages quick on a hosted database)."""

    def test_cache_is_refreshed_when_data_changes(self):
        u = _new_user("cache@example.com")
        uid = u["id"]
        self.assertFalse(repo.data_summary(uid)["has_data"])
        v0 = repo.data_version(uid)
        df = _clean(DIRTY_CSV)[0]
        repo.save_sales(uid, df)
        self.assertGreater(repo.data_version(uid), v0)
        self.assertTrue(repo.data_summary(uid)["has_data"])          # not the stale "no data"
        self.assertFalse(repo.read_sales(uid).empty)
        repo.save_profile(uid, {"business_name": "A", "state": "Kerala", "customer_mix": []})
        self.assertEqual(repo.get_profile(uid)["state"], "Kerala")
        repo.save_profile(uid, {"business_name": "A", "state": "Goa", "customer_mix": []})
        self.assertEqual(repo.get_profile(uid)["state"], "Goa")      # profile edit shows at once
        repo.clear_sales(uid)
        self.assertTrue(repo.read_sales(uid).empty)
        repo.set_active(uid, False)
        self.assertFalse(repo.get_user(uid)["is_active"])            # suspension is not delayed by the cache

    def test_cached_frames_cannot_be_changed_by_callers(self):
        u = _new_user("cache2@example.com")
        repo.save_sales(u["id"], _clean(DIRTY_CSV)[0])
        first = repo.read_sales(u["id"])
        first.loc[:, "quantity"] = -1
        self.assertTrue((repo.read_sales(u["id"])["quantity"] > 0).all())

    def test_postgres_connections_are_reused_and_dead_ones_dropped(self):
        class Raw:
            closed = False
            def __init__(self): self.n = 0
            def execute(self, *a): self.n += 1
            def rollback(self): pass
            def close(self): self.closed = True

        made = []
        def fake_connect():
            r = Raw(); made.append(r); return r

        orig = db._pg_connect
        db._pg_connect = fake_connect
        db.reset_pool()
        try:
            a = db._pg_borrow(); db._pg_return(a, True)
            b = db._pg_borrow()
            self.assertIs(a, b)                       # reused, no second connect
            db._pg_return(b, True)
            b.closed = True                           # the server dropped it meanwhile
            c = db._pg_borrow()
            self.assertIsNot(c, b)                    # a fresh one is opened instead
            self.assertEqual(len(made), 2)
        finally:
            db._pg_connect = orig
            db.reset_pool()


if __name__ == "__main__":
    unittest.main()
