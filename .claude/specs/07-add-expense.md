# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` stub with a fully working GET/POST route
that lets a logged-in user submit a new expense through a form. The GET request
renders a form with fields for amount, category, date, and an optional
description. The POST request validates the input, inserts a row into the
`expenses` table, and redirects the user back to `/profile` with a flash
confirmation. This is the first write-path for expenses and makes the tracker
genuinely usable for recording real spending.

## Depends on
- Step 1: Database setup (`expenses` table with `user_id`, `amount`, `category`,
  `date`, `description` columns must exist)
- Step 3: Login and Logout (session must be set; route must be login-guarded)
- Step 4: Profile page (redirect target after successful add)

## Routes
- `GET /expenses/add` — render the add expense form — logged-in only
- `POST /expenses/add` — validate input, insert expense, redirect — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/add_expense.html` — form page extending `base.html`;
  contains:
  - Amount field: `<input type="number" step="0.01" min="0.01">`
  - Category field: `<select>` with options Food, Transport, Bills, Health,
    Entertainment, Shopping, Other
  - Date field: `<input type="date">` defaulting to today's date
  - Description field: `<input type="text">` (optional)
  - Submit button
  - Inline error message area (rendered when the route passes an `error` var)
- **Modify:** `templates/profile.html` — ensure the "Add Expense" button/link
  points to `url_for('add_expense')`

## Files to change
- `app.py`
  - Replace the `add_expense()` stub with a full GET/POST view:
    - Auth guard: redirect to `/login` if `session.get("user_id")` is absent
    - GET: render `add_expense.html` with today's date pre-filled
    - POST: read `amount`, `category`, `date`, `description` from `request.form`;
      validate; insert into `expenses`; flash success; redirect to `/profile`
- `templates/profile.html` — wire "Add Expense" CTA to `url_for('add_expense')`

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format user input into SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Auth guard on both GET and POST: check `session.get("user_id")`; if absent,
  `redirect(url_for("login"))`
- Amount validation: must be convertible to `float` and greater than 0; on
  failure re-render the form with an `error` variable
- Category validation: must be one of the fixed set — Food, Transport, Bills,
  Health, Entertainment, Shopping, Other; reject unknown values
- Date validation: must parse with `datetime.date.fromisoformat()`; on failure
  re-render the form with an error
- Description: optional; strip whitespace; store `None` if blank
- On successful insert: `flash("Expense added.")` then
  `redirect(url_for("profile"))`
- On validation failure: re-render the form with previously entered values
  preserved (pass `amount`, `category`, `date`, `description` back to template)
- Amount stored as `REAL` — no currency symbol in the DB value

## Definition of done
- [ ] Visiting `/expenses/add` without being logged in redirects to `/login`
- [ ] GET `/expenses/add` returns HTTP 200 and renders a form with amount,
  category, date, and description fields
- [ ] The date field defaults to today's date
- [ ] Submitting valid data (e.g. amount=15.00, category=Food, date=today)
  inserts a row in the `expenses` table and redirects to `/profile`
- [ ] A flash message "Expense added." is visible on the profile page after
  a successful submission
- [ ] The new expense appears in the transaction list on `/profile`
- [ ] Submitting with a missing or zero amount re-renders the form with an
  error message and does not insert a row
- [ ] Submitting with an invalid date re-renders the form with an error message
- [ ] Submitting with an unrecognised category re-renders the form with an error
- [ ] Previously entered form values are preserved when re-rendering after a
  validation error
- [ ] The "Add Expense" button on `/profile` navigates to `/expenses/add`
- [ ] No hex colour values appear in `add_expense.html` — only CSS variables
