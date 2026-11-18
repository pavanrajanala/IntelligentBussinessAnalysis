# Product Requirements: Intelligent Business Analyst

Status: v1 built · Owner: student minor project · Last updated: 24 Oct 2026

## 1. Problem

Small shop owners in India decide what to order from memory and habit. They overstock slow items, run out of fast ones, and are caught out by festivals and seasons. Spreadsheets and BI tools are too heavy; generic chatbots invent numbers and answer in dollars.

## 2. Users

- **Shop owner (primary).** Runs a kirana, general store, medical, stationery or similar shop. Comfortable with a phone and WhatsApp, not with analytics. Keeps sales in a billing app that exports CSV. Wants a list to send to the supplier.
- **Service admin.** Runs Intelligent Business Analyst. Needs to know how many shops use it, who is active, where they are and what they use, without reading anyone's business data.

## 3. Goals

1. Give the owner a next-month order list they can act on in under two minutes after uploading data.
2. Make the list reflect the owner's own sales, the season in their state and nearby festivals.
3. Let the owner ask questions about their own data in plain language, with amounts in ₹ and news summarised, not linked.
4. Save each customer's data and history under their own account.
5. Give the admin usage visibility while keeping customer business data private.
6. Look and feel like a considered, simple tool, not a template dashboard.

## 4. Non-goals (v1)

Billing or invoicing; inventory sync with a POS; supplier ordering or payments; multi-shop or multi-user accounts; native mobile apps; learning from other shops' data; languages other than English.

## 5. Features and requirements

### 5.1 Accounts
- Sign up in three steps: account (name, email, password ≥ 8 chars), shop (name, type, who the customers are), location (state, city, pincode; optional "use my current location").
- Sign in, sign out, session for 7 days. Wrong credentials give one generic message.
- Edit shop details and location later. Delete account (password required) and remove all sales data.
- Rate limit sign-in attempts and sign-ups. Admin can suspend and reactivate accounts; suspended users are signed out.

### 5.2 Data
- Upload CSV (≤ 10 MB) with date, product, quantity, price; optional category, customer, region. Column aliases accepted.
- Automatic cleaning with a visible report: duplicates, missing quantities, unreadable dates, invalid rows, unusually large orders (kept but excluded from totals).
- Replace or add to existing data; repeated rows skipped on add. Upload history. Sample data for trying the app.

### 5.3 Order list (next month)
- Per product: last month, expected, suggested order, action (more / less / same), confidence, reasons.
- User can enter current stock; the quantity to buy updates and is remembered in the browser for that month.
- Copy as text, send on WhatsApp, print.
- Warnings when data is short or the latest month is incomplete.
- Acceptance: with the sample data the list renders for every product, quantities are whole numbers, all money is shown as ₹.

### 5.4 Season and festivals
- Current and next-month regional season.
- Festivals in the next 75 days, filtered to the user's state, with date, days away, stock-by date, affected product groups with expected lift, the user's own products in those groups, and ideas.
- Tips by shop type and customer mix. Approximate dates are labelled.

### 5.5 Assistant
- Tools over the user's own data: sales trend, customers who stopped buying, top products, categories, period comparison, next-month forecast, festival outlook, optional web news.
- Always answers in rupees; no dollar amounts in output.
- News is used only when the user ticks "Include recent web news" or clearly asks for news; results are summarised in the model's own words with source names, links shown as source chips; repeated searches for the same product are cached for six hours.
- Conversation history is saved per user and restored in order; the last few messages give follow-ups context. Clear chat available.

### 5.6 Overview
Total sales, bills, average bill, latest-month change, next month at a glance, monthly sales chart, best sellers, category split, products to watch with "Ask why".

### 5.7 Admin
- Totals: customers, new this week, active in 7 and 30 days, customers with data, sales rows, questions asked, news searches.
- Charts: new customers and questions per day for 30 days. Breakdowns by shop type, state and customer mix.
- Searchable customer table with joined date, last seen, location, row and question counts; suspend or reactivate.
- Admin never sees sales rows or chat text. Admin routes return 403 to non-admins.

## 6. Non-functional requirements

- **Privacy and security:** per-user data isolation on every query; the model cannot choose a user id; scrypt password hashes; signed HttpOnly cookies; security headers; upload size limit; secrets only in environment variables.
- **Portability:** SQLite for local use, Neon Postgres in production, selected by one variable; schema created automatically.
- **Accessibility and usability:** labelled form fields, keyboard operable, visible focus, readable contrast, works at phone width without sideways scrolling, order list prints cleanly.
- **Performance:** database connections are reused, per-user data is briefly cached and computed pages are cached for two minutes; a repeat page load makes no database connections; typical uploads (thousands of rows) clean in about a second.

## 7. Data model

| Table | Purpose |
|---|---|
| users | id, email (unique), name, password hash, role (user/admin), is_active, created_at, last_login_at |
| profiles | one per user: shop name, type, customer mix, city, state, pincode, latitude, longitude |
| sales | cleaned rows per user: date, product, category, quantity, price, revenue, customer, region, outlier flag |
| uploads | filename, mode, rows received/saved, cleaning report, time |
| chat_messages | role, content, trace/sources, microsecond timestamp |
| events | signup / chat / news usage events for the admin counts |

## 8. API summary

Auth: `POST /api/auth/signup`, `/login`, `/logout`; `GET /api/auth/me`. Profile: `PUT /api/profile`; `POST /api/account/delete`. Data: `POST /api/upload`, `/api/load-sample`; `GET /api/data-status`, `/uploads`, `/overview`, `/forecast`, `/outlook`; `DELETE /api/data`. Assistant: `POST /api/chat`; `GET`/`DELETE /api/chat/history`. Admin: `GET /api/admin/stats`, `/api/admin/users?q=`; `PATCH /api/admin/users/{id}`. Misc: `/api/health`, `/api/meta`, `/api/sample-csv`.

## 9. Success measures

- Share of new accounts that upload data in their first session (target 60%).
- Share of uploaders who open the order list and use Copy, WhatsApp or Print (target 40%).
- Returning shops in the following month (target 40%).
- Assistant answers containing a non-₹ currency symbol: 0.
- Support-visible incidents of one customer seeing another's data: 0.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Forecast is wrong with little data | Confidence labels, warnings, safety buffer, owner enters stock and decides |
| Model invents numbers | All figures come from tools; instructions and code-level rupee normalisation |
| News costs or hallucinations | Opt-in, cached, summarised only from returned articles with sources named |
| Festival dates go stale | Dated calendar file with `approx` flag; yearly update documented |
| Admin overreach | Admin queries return counts and profile fields only |
| Free hosting sleeps or resets | Neon holds data; in-memory rate limits are harmless to lose |
| Location sharing feels invasive | Optional; manual state selection; explained on screen |

## 11. Status

Built and tested: everything in section 5. Verified: 44 automated backend tests, frontend lint, and a 33-check browser run. Not yet verified against live services: Neon/Postgres, Groq, Tavily, browser geolocation, and `vite build` (see README, "Honest limits").

## 12. Roadmap

Next: email verification and password reset; stock levels carried month to month; supplier-wise lists; Hindi and Tamil; weekly WhatsApp or email reminder before festivals; export to Excel. Later: shared lists for staff; learning festival lifts anonymously across shops (with consent).
