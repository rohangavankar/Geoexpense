# GeoExpense — Enhancement Roadmap

## Phase 1 · Auth & Multi-tenancy
_Foundation everything else depends on_

### User Authentication
- [ ] Sign up / sign in with email + password (JWT tokens)
- [ ] Google OAuth ("Sign in with Google") via OAuth2
- [ ] Persistent sessions with refresh tokens
- [ ] Protected API routes — all `/api/expenses` endpoints require auth

### Company-based Storage
- [ ] `companies` table — name, slug, created_at
- [ ] `users` table — email, hashed_password, company_id, role (owner / admin / member)
- [ ] All expenses scoped to `company_id` — users only see their company's data
- [ ] Invite teammates by email
- [ ] Roles: **Owner** (billing, settings), **Admin** (manage members), **Member** (own expenses only)

### Database migrations
- [ ] Swap SQLite → PostgreSQL (production-ready, multi-user safe)
- [ ] Alembic for schema migrations

---

## Phase 2 · Expense Management
_Make the core product more powerful_

### Receipt Upload + AI Extraction
- [ ] Upload a photo of a receipt
- [ ] Claude Vision extracts: vendor, amount, date, line items automatically
- [ ] No manual entry needed — just snap and confirm

### Filtering & Reporting
- [ ] Filter by date range, category, employee, tax-deductible status
- [ ] Monthly / quarterly summary view
- [ ] Export to CSV or PDF (ready for accountant / tax prep)

### Approval Workflow
- [ ] Employees submit expenses → Manager gets notified
- [ ] Manager approves or rejects with a note
- [ ] Approved expenses mark as reimbursed
- [ ] Audit trail for every status change

### Recurring Expenses
- [ ] Mark an expense as recurring (monthly SaaS subscriptions, etc.)
- [ ] Auto-create next month's entry
- [ ] Alert if a recurring expense hasn't appeared

---

## Phase 3 · Integrations
_Connect to tools businesses already use_

### Accounting Export
- [ ] Export approved expenses as CSV, ready to import into any accounting tool
- [ ] PDF expense report with company logo, date range, totals by category
- [ ] Generate IRS-ready mileage / expense summary at tax time

### Slack / Email Notifications
- [ ] Notify manager in Slack when expense submitted
- [ ] Weekly expense digest email per employee
- [ ] Alert when approaching budget limit

### Bank / Card Feed
- [ ] Connect a business credit card via Plaid
- [ ] Auto-import transactions — Claude matches them to existing expenses or creates new ones
- [ ] Reconciliation view: imported vs manually entered

---

## Phase 4 · Analytics & AI
_Insights that justify the product_

### Spend Intelligence
- [ ] Spending trends over time per category / employee / city
- [ ] Anomaly detection — "this vendor is 3× your usual spend"
- [ ] Top vendors, top spenders, busiest travel cities on the map

### AI Budget Assistant
- [ ] Set monthly budgets per category
- [ ] Claude warns when approaching limit: "You're 80% through your Meals budget with 2 weeks left"
- [ ] End-of-quarter tax summary: "You have $X deductible, estimated savings of $Y"

### Natural Language Expense Entry
- [ ] Type: "Lunch at Chipotle in Austin yesterday, $14.50" → Claude parses and fills the form
- [ ] Voice input on mobile

---

## Phase 5 · Polish & Scale
_Production-ready_

### Mobile
- [ ] Responsive layout for phones
- [ ] PWA — add to home screen, works offline
- [ ] Camera access for receipt capture on mobile

### Performance
- [ ] Paginate expense list (currently loads all)
- [ ] Cache `/api/expenses/summary` — invalidate on write
- [ ] Lazy-load map markers when zoomed out (cluster them)

### Deployment
- [ ] Dockerize — `docker compose up` spins everything
- [ ] Deploy to Railway / Render / Fly.io
- [ ] Custom domain
- [ ] Environment-based config (dev / staging / prod)

---

## Quick Wins (do anytime)
_Small, high-impact, no dependencies_

- [ ] Delete expense from the map popup
- [ ] Edit expense — click a marker and update fields
- [ ] Date picker filter on the sidebar
- [ ] Color-coded map clusters when zoomed out
- [ ] Receipt image field (URL for now, upload later)
- [ ] Keyboard shortcut: `N` to add new expense at current map center
- [ ] Share a read-only link to your expense map

---

## What to Build Next

Highest impact in order:

1. **Google OAuth** — removes the biggest friction for new users
2. **Receipt upload + AI extraction** — the core "wow" feature
3. **Approval workflow** — unlocks the team use case
4. **Accounting export** — makes the product immediately useful at tax time
5. **Bank card feed** — closes the loop on manual entry entirely
