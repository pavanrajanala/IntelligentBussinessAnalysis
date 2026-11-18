"""
main.py - The FastAPI server. Every page of the website talks to these routes.

Run (from the backend folder):   uvicorn main:app --reload
Interactive API docs:            http://127.0.0.1:8000/docs
"""

import os
import re
import tempfile
import time

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import admin as admin_stats
import aggregate
import config
import db
import forecast
import repo
import security
import seasonal
from agent import MAX_QUESTION_CHARS, run_agent
from clean import clean_sales_data, load_csv

COOKIE_NAME = "bac_session"
HISTORY_FOR_MODEL = 6  # earlier messages sent to the model for follow-up questions
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

db.init_schema()

app = FastAPI(title="Intelligent Business Analyst")

# Only needed when the frontend is hosted on a different address than the API.
if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


# Plain `def` endpoints (not `async def`) on purpose: they do blocking work (database, pandas,
# LLM calls) and FastAPI runs them in a thread pool so one slow request does not freeze the server.


# ---------- Helpers ----------

def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def public_user(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"]}


def current_user(request: Request) -> dict:
    user_id = security.read_token(request.cookies.get(COOKIE_NAME))
    user = repo.get_user(user_id) if user_id else None
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return user


# Computed pages (overview, forecast, outlook) are kept for two minutes per user and rebuilt as soon as
# that user's sales or profile change, so moving between pages is instant.
_PAGE_CACHE: dict = {}
PAGE_TTL = 120


def cached_page(kind: str, user_id: str, build):
    key = (kind, user_id)
    stamp = (repo.data_version(user_id), seasonal.today_india().isoformat())
    hit = _PAGE_CACHE.get(key)
    if hit and hit[0] == stamp and time.time() - hit[1] < PAGE_TTL:
        return hit[2]
    value = build()
    if len(_PAGE_CACHE) > 1000:
        _PAGE_CACHE.clear()
    _PAGE_CACHE[key] = (stamp, time.time(), value)
    return value


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="This page is only for administrators.")
    return user


def start_session(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        security.make_token(user_id),
        max_age=config.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=config.COOKIE_SECURE,
        path="/",
    )


# ---------- Health and static info ----------

@app.get("/api/health")
def health():
    return {"status": "running", "database": "postgres" if db.is_postgres() else "sqlite"}


@app.get("/api/meta")
def meta():
    """Lists used by the signup and profile forms."""
    return {
        "business_types": seasonal.BUSINESS_TYPES,
        "customer_types": [{"id": k, "label": v} for k, v in seasonal.CUSTOMER_TYPES.items()],
        "states": seasonal.INDIA_STATES,
    }


@app.get("/api/sample-csv")
def sample_csv():
    if not config.SAMPLE_CSV.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return FileResponse(config.SAMPLE_CSV, media_type="text/csv", filename="sample_sales.csv")


# ---------- Accounts ----------

class ProfileIn(BaseModel):
    business_name: str = Field(default="", max_length=120)
    business_type: str = Field(default="", max_length=80)
    customer_mix: list[str] = Field(default_factory=list)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=80)
    pincode: str = Field(default="", max_length=10)
    latitude: float | None = None
    longitude: float | None = None


class SignupIn(ProfileIn):
    name: str = Field(max_length=80)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


def clean_profile(p: ProfileIn) -> dict:
    """Trim and sanity-check the shop profile."""
    if p.state and p.state not in seasonal.INDIA_STATES:
        raise HTTPException(status_code=422, detail="Please choose your state from the list.")
    if p.pincode and not re.fullmatch(r"\d{6}", p.pincode.strip()):
        raise HTTPException(status_code=422, detail="Pincode should be 6 digits.")
    if p.latitude is not None and not (-90 <= p.latitude <= 90):
        raise HTTPException(status_code=422, detail="Location is not valid.")
    if p.longitude is not None and not (-180 <= p.longitude <= 180):
        raise HTTPException(status_code=422, detail="Location is not valid.")
    mix = [m for m in p.customer_mix if m in seasonal.CUSTOMER_TYPES]
    return {
        "business_name": p.business_name.strip(),
        "business_type": p.business_type.strip(),
        "customer_mix": mix,
        "city": p.city.strip(),
        "state": p.state.strip(),
        "pincode": p.pincode.strip(),
        "latitude": p.latitude,
        "longitude": p.longitude,
    }


@app.post("/api/auth/signup")
def signup(body: SignupIn, request: Request, response: Response):
    ip = client_ip(request)
    if security.signup_limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="Too many sign-ups from this network. Please try again later.")
    name, email = body.name.strip(), body.email.strip().lower()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Please enter your name.")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    profile = clean_profile(body)
    if not profile["business_name"]:
        raise HTTPException(status_code=422, detail="Please enter your shop name.")
    if repo.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists. Try signing in.")

    security.signup_limiter.add(ip)
    user = repo.create_user(email, name, security.hash_password(body.password))
    repo.save_profile(user["id"], profile)
    repo.log_event(user["id"], "signup")
    repo.touch_login(user["id"])  # signing up counts as the first visit
    start_session(response, user["id"])
    return {"user": public_user(user), "profile": repo.get_profile(user["id"])}


_DUMMY_HASH = security.hash_password("not-a-real-password")


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    key = f"{client_ip(request)}|{email}"
    if security.login_limiter.blocked(key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait ten minutes and try again.")

    user = repo.get_user_by_email(email)
    ok = security.verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        security.login_limiter.add(key)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="This account has been suspended. Please contact support.")

    security.login_limiter.reset(key)
    if email in config.ADMIN_EMAILS and user["role"] != "admin":
        repo.set_role(user["id"], "admin")
        user["role"] = "admin"
    repo.touch_login(user["id"])
    repo.log_event(user["id"], "login")
    start_session(response, user["id"])
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user), "profile": repo.get_profile(user["id"]), "summary": repo.data_summary(user["id"])}


@app.put("/api/profile")
def update_profile(body: ProfileIn, user: dict = Depends(current_user)):
    profile = clean_profile(body)
    if not profile["business_name"]:
        raise HTTPException(status_code=422, detail="Please enter your shop name.")
    repo.save_profile(user["id"], profile)
    return {"profile": repo.get_profile(user["id"])}


class DeleteAccountIn(BaseModel):
    password: str = Field(max_length=200)


@app.post("/api/account/delete")
def delete_account(body: DeleteAccountIn, response: Response, user: dict = Depends(current_user)):
    """Permanently removes the account and everything stored for it."""
    if not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=403, detail="Password is incorrect.")
    repo.delete_user(user["id"])
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


# ---------- Sales data ----------

def _store_upload(user_id: str, filename: str, mode: str, path: str) -> dict:
    raw = load_csv(path)
    cleaned, report = clean_sales_data(raw)
    stored = repo.save_sales(user_id, cleaned, mode)
    report["rows_in_account"] = stored
    repo.log_upload(user_id, filename, mode, report["original_row_count"], report["final_row_count"], report)
    repo.log_event(user_id, "upload")
    return {"message": "Upload successful", "rows_saved": stored, "mode": mode, "cleaning_report": report}


@app.post("/api/upload")
def upload_csv(file: UploadFile = File(...), mode: str = Form("replace"), user: dict = Depends(current_user)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")
    if mode not in ("replace", "append"):
        raise HTTPException(status_code=400, detail="Mode must be 'replace' or 'append'.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name
            written = 0
            while chunk := file.file.read(1024 * 1024):
                written += len(chunk)
                if written > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File is too large (limit 10 MB).")
                tmp.write(chunk)
        return _store_upload(user["id"], file.filename, mode, tmp_path)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process the CSV: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/load-sample")
def load_sample(user: dict = Depends(current_user)):
    if not config.SAMPLE_CSV.exists():
        raise HTTPException(status_code=404, detail="Sample file not found.")
    return _store_upload(user["id"], "sample_sales.csv", "replace", str(config.SAMPLE_CSV))


@app.get("/api/data-status")
def data_status(user: dict = Depends(current_user)):
    return repo.data_summary(user["id"])


@app.get("/api/uploads")
def uploads(user: dict = Depends(current_user)):
    return repo.list_uploads(user["id"])


@app.delete("/api/data")
def delete_data(user: dict = Depends(current_user)):
    repo.clear_sales(user["id"])
    return {"ok": True}


# ---------- Insights ----------

@app.get("/api/overview")
def overview(user: dict = Depends(current_user)):
    def build():
        df = repo.read_sales(user["id"], exclude_outliers=True)
        if df.empty:
            return {"has_data": False}
        return {"has_data": True, **aggregate.overview(df)}

    return cached_page("overview", user["id"], build)


@app.get("/api/forecast")
def forecast_route(user: dict = Depends(current_user)):
    def build():
        df = repo.read_sales(user["id"], exclude_outliers=True)
        result = forecast.predict_next_month(df, repo.get_profile(user["id"]))
        return {"has_data": not df.empty, **result}

    return cached_page("forecast", user["id"], build)


@app.get("/api/outlook")
def outlook(user: dict = Depends(current_user)):
    def build():
        df = repo.read_sales(user["id"], exclude_outliers=True)
        return {"has_data": not df.empty, **seasonal.build_outlook(df, repo.get_profile(user["id"]))}

    return cached_page("outlook", user["id"], build)


# ---------- Chat ----------

class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    use_news: bool = False


@app.post("/api/chat")
def chat(body: ChatIn, user: dict = Depends(current_user)):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please type a question.")
    if not repo.data_summary(user["id"])["has_data"]:
        raise HTTPException(status_code=400, detail="Upload your sales data first, then ask questions about it.")

    history = repo.recent_chat(user["id"], limit=HISTORY_FOR_MODEL)
    try:
        result = run_agent(user["id"], question, history=history, allow_news=body.use_news)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"The assistant hit an error: {e}")

    repo.add_chat(user["id"], "user", question)
    repo.add_chat(user["id"], "assistant", result["answer"], {"trace": result["trace"], "sources": result["sources"]})
    repo.log_event(user["id"], "chat")
    if result.get("used_news"):
        repo.log_event(user["id"], "news")
    return result



@app.get("/api/chat/history")
def chat_history(user: dict = Depends(current_user)):
    return repo.recent_chat(user["id"], limit=40)


@app.delete("/api/chat/history")
def clear_chat_history(user: dict = Depends(current_user)):
    repo.clear_chat(user["id"])
    return {"ok": True}


# ---------- Admin ----------

@app.get("/api/admin/stats")
def admin_overview(_: dict = Depends(require_admin)):
    return admin_stats.stats()


@app.get("/api/admin/users")
def admin_users(q: str = "", _: dict = Depends(require_admin)):
    return admin_stats.list_users(q)


class AdminUserPatch(BaseModel):
    is_active: bool | None = None


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, body: AdminUserPatch, admin: dict = Depends(require_admin)):
    target = repo.get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    if body.is_active is not None:
        repo.set_active(user_id, body.is_active)
    return {"ok": True}


# ---------- Frontend (production build) ----------
# Mounted LAST so it never hides the /api routes. If the frontend has not been built yet,
# the API still starts and says what to do.

if config.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIST), html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "API is running. Build the frontend with 'npm run build' in the frontend folder.", "docs": "/docs"}
