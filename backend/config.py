"""
config.py - All settings in one place, read from environment variables
(or from backend/.env during development).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Database. Leave empty to use a local SQLite file (zero setup).
# For production paste your Neon connection string, e.g.
#   postgresql://user:password@ep-xxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip() or f"sqlite:///{BASE_DIR / 'app.db'}"

# Used to sign login cookies. Set a long random value in production:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()

# Comma-separated emails that become admins automatically.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

# Set to "true" when the site is served over HTTPS (production).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "7"))

# Extra origins allowed to call the API (only needed if the frontend is hosted separately).
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
SAMPLE_CSV = BASE_DIR.parent / "data" / "sample_sales.csv"
FESTIVALS_FILE = BASE_DIR / "data" / "festivals.json"
