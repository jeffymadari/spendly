# Spec: Date Filter for Profile Page

## Overview
This feature replaces the hardcoded profile data with real database queries and adds a date-range filter so users can view their spending for a chosen period. A period selector (This Month, Last 3 Months, All Time, and a custom date range) is rendered as a GET form on the profile page; the route re-queries the `expenses` table on each request and recomputes the stats and category breakdown for the selected window. This step is the backend-connection step that spec 04 deferred.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables must exist)
- Step 2: Registration (real user accounts must exist)
- Step 3: Login + Logout (session must carry `user_id`)
- Step 4: Profile Page (profile template and route must already exist)

## Routes
- `GET /profile` — render the profile page with optional query params `from_date` (YYYY-MM-DD) and `to_date` (YYYY-MM-DD); defaults to the current calendar month — logged-in only

## Database changes
No new tables or columns. The existing `users` and `expenses` tables are sufficient.

A new helper function `get_expenses_for_user` is added to `database/db.py` that accepts `user_id`, `from_date`, and `to_date` and returns filtered rows.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the transaction table with:
    - Four preset buttons: **This Month**, **Last 3 Months**, **All Time**, and **Custom**
    - A collapsible custom date-range picker (two `<input type="date">` fields + Apply button) that appears only when Custom is active
    - Active preset highlighted with the `--accent` colour
  - Stats row, transaction table, and category breakdown must all reflect the filtered data passed from the route (remove any hardcoded fallbacks)

## Files to change
- `app.py` — update `/profile` view to:
  1. Read `from_date` and `to_date` query parameters (default: first and last day of current month)
  2. Detect which preset is active (for highlighting in the template)
  3. Query real user row from DB using `session["user_id"]`
  4. Call `get_expenses_for_user(user_id, from_date, to_date)` from `db.py`
  5. Compute `total_spent`, `transaction_count`, and `top_category` from the returned rows
  6. Build `category_breakdown` list from the returned rows
  7. Pass `from_date`, `to_date`, and `active_preset` to the template alongside all existing context vars
- `database/db.py` — add `get_expenses_for_user(user_id, from_date, to_date)` that returns all expense rows for the user within the inclusive date range, ordered by date descending

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()`
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date defaults computed in Python (`datetime.date.today()`) — never rely on client-side JS for the default window
- Preset detection logic: compare `from_date`/`to_date` against known presets to set `active_preset` (values: `"this_month"`, `"last_3_months"`, `"all_time"`, `"custom"`)
- `get_expenses_for_user` must use `WHERE user_id = ? AND date BETWEEN ? AND ?` — no dynamic SQL construction
- If the filtered result is empty, the stats must show 0 / 0 / "—" gracefully (no crashes on empty lists)
- The custom date range picker must be shown/hidden with a CSS class toggle via inline JS in `{% block scripts %}` — no external JS libraries

## Definition of done
- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] The profile page loads real user name and email from the database (not hardcoded)
- [ ] By default, only expenses from the current calendar month are shown
- [ ] Clicking **This Month** reloads the page showing only the current month's expenses
- [ ] Clicking **Last 3 Months** reloads the page showing expenses from the past 3 calendar months
- [ ] Clicking **All Time** reloads the page showing all expenses for the user
- [ ] The **Custom** option reveals two date inputs; submitting them reloads the page filtered to that range
- [ ] The active preset button is visually highlighted
- [ ] Stats (total spent, transaction count, top category) update to match the filtered set
- [ ] Category breakdown reflects only the filtered expenses
- [ ] When no expenses exist in the selected range, the page shows zeros/empty state without crashing
- [ ] No hardcoded expense data remains in `app.py`
- [ ] No hex colour values appear in `profile.html` — only CSS variables
