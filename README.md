# Intelligent Business Analyst

*(the college minor project formerly called "AI Business Analyst Copilot")*

Intelligent Business Analyst helps a small shop owner decide **what to order next month**. The owner signs up, tells the app about the shop (kind of shop, who the customers are, where it is), uploads a sales CSV, and gets:

- an **order list** for next month, with quantities, a short reason for each item, and an "already in stock" column that works out what is left to buy;
- a **season and festival calendar** for the owner's state, with the date to stock up by and which of the shop's products are affected;
- an **assistant** that answers questions in plain language using only the owner's own numbers (always in rupees, ₹), and can optionally summarise recent web news about a brand;
- an **overview** of sales, best sellers, categories and products that are slipping;
- an **admin page** for the person running the service: how many shops signed up, who is active, what they ask, where they are. It never shows anyone's sales rows or chat text.

Every account's data is separate and saved, so the owner finds everything as they left it.

Stack: FastAPI, pandas, SQLite (local) or Neon Postgres (production), React 19 (Vite), Chart.js, Groq for the assistant, Tavily for optional news.

---

## Why Neon (Postgres) instead of MongoDB

The data is tabular and belongs to one user each (accounts, shop profiles, sales rows, uploads, chat, usage events). The app reads whole months of sales into pandas, filters by user, and the admin page counts and groups across users. A relational database does that naturally, enforces "one email per account" and cascading deletes, and Neon has a free tier with the same connection-string workflow as MongoDB Atlas. So the app uses SQL.

You do not need to install anything to start: with no `DATABASE_URL` it uses a local SQLite file. Set `DATABASE_URL` to a Neon connection string and the same code runs on Postgres. The schema uses only portable types, and tables are created automatically on start (there are no migrations to run).

---

## Project layout

```
backend/
  main.py          FastAPI app: every /api route, security headers, serves the built frontend
  config.py        settings read from environment variables
  db.py            small SQL layer: SQLite or Postgres chosen by DATABASE_URL, schema created on start
  repo.py          all database reads and writes (users, profiles, sales, uploads, chat, events)
  security.py      password hashing (scrypt), signed session cookie, login and signup rate limits
  clean.py         automatic cleaning of uploaded CSVs + cleaning report
  aggregate.py     overview numbers and charts data
  seasonal.py      product tagging, regional seasons, festival calendar, "outlook" for the Season page
  forecast.py      next month's order quantities
  agent.py         the assistant loop (LLM <-> tools), rupee enforcement, summarised news
  tools.py         the tools the assistant can call (all scoped to the signed-in user)
  tool_schemas.py  tool descriptions the model sees
  admin.py         usage statistics and customer list for the admin page
  create_admin.py  command-line helper to create or promote an admin
  data/festivals.json   festival calendar (Oct 2026 to Dec 2027)
  tests/           44 automated tests
frontend/src/      React app: pages/, components/, styles.css (single stylesheet)
data/              sample_sales.csv and the script that made it
PRD.md             product requirements
```

---

## Run it on your computer

You need Python 3.10+ and Node 18+.

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows.  On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env
```

Open `backend/.env` and fill in:

| Variable | Required | What it is |
|---|---|---|
| `GROQ_API_KEY` | for the assistant | Free key from console.groq.com/keys. Without it everything except the assistant works. |
| `TAVILY_API_KEY` | optional | Free key from tavily.com. Enables "Include recent web news". |
| `DATABASE_URL` | optional | Empty = local SQLite (`backend/app.db`). Or a Neon string like `postgresql://user:pass@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require`. |
| `SECRET_KEY` | recommended | Long random text that signs login cookies. Make one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. If empty, a key is generated into `backend/.secret_key` (fine locally, set it in production). |
| `ADMIN_EMAILS` | optional | Comma-separated emails that become admins when they sign up or sign in. |
| `COOKIE_SECURE` | production | Set `true` once the site is on HTTPS. |
| `SESSION_DAYS` | optional | Login length, default 7. |
| `CORS_ORIGINS` | optional | Only if the frontend is hosted on a different address than the API. |
| `GROQ_MODEL` | optional | Override the model name. |

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend (development)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` calls to port 8000.

### 3. One-server mode (what production uses)

```bash
cd frontend && npm install && npm run build
cd ../backend && uvicorn main:app --port 8000
```

Open http://localhost:8000. FastAPI serves the built app from `frontend/dist`.

### Making yourself an admin

Either put your email in `ADMIN_EMAILS` before signing up, or run:

```bash
cd backend
python create_admin.py you@example.com      # promotes an existing account
python create_admin.py                      # or answer the prompts to create one
```

An **Admin** link then appears in the sidebar.

### Try it

Sign up (three short steps; "Use my current location" is optional, you can pick your state instead), then on **My data** press *Try with sample data*. Your CSV needs the columns `date`, `product`, `quantity`, `price`; `category`, `customer_id` and `region` are optional, and common alternatives such as `qty` or `unit_price` are understood.

---

## How the main features work

**Order list.** For each product the app takes the last three months (the most recent months count more), adds a damped trend, and multiplies by a season and festival factor for the owner's state and the products' type (for example tea in the Northeast monsoon, sweets before Diwali). It adds a 10% safety buffer (20% close to a festival) and rounds up. Items are marked *Order more* (+10% or more against last month), *Order less* (−12% or less) or *Keep the same*, with a confidence level and plain-language reasons. An incomplete latest month is ignored. With 13+ months of data the shop's own seasonality is blended in. Treat it as a careful estimate, not a promise.

**Season and festivals.** Regional seasons plus festivals within the next 75 days, each with the date to stock up by, the products of yours that are affected and ideas you may not stock yet. A few festival dates depend on the moon and are marked "approximate".

**Assistant.** The model can only call tools that read the signed-in user's own data; the user id is injected by the server and cannot be chosen by the model. Amounts are normalised to ₹ in code, not just by instruction. The news search is offered to the model only when the "Include recent web news" box is ticked or the question is clearly about news; the model is told to summarise what the articles say in its own words, naming the source, and the sources appear as small chips. News results are cached for six hours per product to save API credits.

**Accounts and privacy.** Passwords are hashed with scrypt. Sessions are an HMAC-signed cookie (`HttpOnly`, `SameSite=Lax`). Login and signup are rate limited. Suspended accounts are signed out. Users can delete their account (password required) and remove all their sales data. Admins see profile fields and counts only.

---

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m unittest discover -s tests          # or: pytest
cd ../frontend && npm run lint
```

Results from the last full run (details and caveats below): **44 tests, all passing**; ESLint clean; a 33-check browser run (desktop and phone width) with no failures and no console errors.

What the tests cover: cleaning, password and token security, per-user data isolation, seasonal tagging and festivals, the forecast, the assistant loop with a fake model (news gating, user-id stripping, history, rupees), the news tool and its cache, and the API (signup, login, rate limiting, privacy, forecast, chat with a fake model, admin, suspend, account deletion, chat history ordering).

**Honest limits of what has been verified**

- The automated API tests in the development sandbox ran against a small stand-in for FastAPI because packages could not be installed there. The code is plain FastAPI, but run `python -m unittest discover -s tests` once on your machine with the real packages installed; that is the result that counts.
- `npm run build` could not be run in the sandbox (the `node_modules` came from Windows). The frontend was bundled with esbuild for testing instead. Run `npm install` and `npm run build` yourself.
- The Neon/Postgres path, live Groq answers, live Tavily news and the browser location lookup have **not** been run against the real services. The news tool is tested with a mocked Tavily response.
- Fonts load from Google Fonts; offline the browser falls back to a system font.

---

## Speed

Hosted databases such as Neon are slow to *connect* (hundreds of milliseconds), and one page used to open several connections. Now: Postgres connections are kept and reused (`backend/db.py`); the signed-in user, shop profile and sales are cached for a few seconds and dropped the moment this server changes them (`backend/repo.py`); and the overview, order list and season pages are cached per user for two minutes and rebuilt when the data changes (`backend/main.py`). Measured on the sample data: the first page load makes 2 database connections and the next makes 0 (about 100 ms and 9 ms in the sandbox). If you run several server workers, a change made through one worker can take up to 30 seconds to show in the others; with one worker (the default) it shows at once. Choose a Neon region close to your host (Singapore for India) and keep the host in the same region.

## Deploying

1. Create a Neon project and copy the pooled connection string into `DATABASE_URL`.
2. Pick a host that runs Python (Render, Railway, a VPS). Build step: `pip install -r backend/requirements.txt && cd frontend && npm install && npm run build`. Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Set the environment variables above, with `COOKIE_SECURE=true`, a real `SECRET_KEY`, your `ADMIN_EMAILS`, and the Groq and Tavily keys.
4. Open the site over HTTPS, sign up with an admin email, and check the Admin page.

Keep `SECRET_KEY` stable between deploys, otherwise everyone is signed out. Free hosts that sleep will lose the in-memory rate-limit counters, which is harmless.

## Security notes

- Never commit `.env`; it is in `.gitignore`. Rotate any key that was ever shared.
- Rate limits are kept in memory, so they apply per server process.
- Uploads are limited to 10 MB and must be CSV.
- The location the user shares is stored only on their own profile and used to choose seasons and festivals.

## Known limitations

- The festival calendar covers October 2026 to December 2027. Edit `backend/data/festivals.json` each year (the format is easy to copy). Dates marked `approx` should be checked.
- Forecasts need at least a few months of history; accuracy improves with 12+ months.
- Season and festival effects are rule-based estimates, not learned from other shops.
- No email verification or password reset yet (see the roadmap in PRD.md).
