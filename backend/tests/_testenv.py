"""Imported first by every test file: points the app at a throw-away database and test settings."""
import os
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

if "TEST_DB" not in os.environ:
    os.environ["TEST_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + os.environ["TEST_DB"]
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only"
os.environ["ADMIN_EMAILS"] = "boss@example.com"
os.environ.pop("GROQ_API_KEY", None)
