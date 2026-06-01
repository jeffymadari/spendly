# Spec: Edit Expense

## Overview
Step 8 replaces the `/expenses/<int:id>/edit` stub with a fully working GET/POST
route that lets a logged-in user update an existing expense. The GET request loads
the expense from the database and pre-fills a form identical in structure to the
add-expense form. The POST request validates the submitted data and runs an UPDATE
query. Ownership is enforced: a user can only edit their own expenses — any attempt
to access another user's expense returns a 404. This closes the basic expense CRUD
loop (add was Step 7; delete is Step 9) and makes the tracker fully editable.

## Depends on
- Step 1: Database setup (`expenses` table must exist)
- Step 3: Login and Logout (session required; route is login-guarded)
- Step 4/5: Profile page (the transaction list where the Edit link lives)
- Step 7: Add Expense (`add_expense.html` design and `EXPENSE_CATEGORIES` constant
  already exist and will be reused as the pattern for the edit form)

## Routes
- `GET /expenses/<int:id>/edit` — render edit form pre-filled with existing data — logged-in only
- `POST /expenses/<int:id>/edit` — validate input, update expense, redirect — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns.

## Templates
- **Create:** `templates/edit_expense.html` — edit form page extending `base.html`;
  mirrors `add_expense.html` in structure but:
  - Heading reads "Edit Expense" instead of "Add Expense"
  - All fields pre-filled from the existing expense row
  - Submit button reads "Save Changes"
  - A "Cancel" link navigates back to `/profile`
- **Modify:** `templates/profile.html` — add an "Edit" link/button on each expense
  row in the transaction list, pointing to
  `url_for('edit_expense', id=expense.id)`

## Files to change
- `app.py`
  - Replace the `edit_expense()` stub with a full GET/POST view:
    - Auth guard: redirect to `/login` if `session.get("user_id")` is absent
    - GET: fetch expense by `id` **and** `user_id`; 404 if not found; render
      `edit_expense.html` pre-filled with existing values
    - POST: read `amount`, `category`, `date`, `description` from `request.form`;
      validate (same rules as add); run UPDATE; flash success; redirect to `/profile`
- `database/queries.py`
  - Add `get_expense_by_id(expense_id, user_id)` — fetches a single expense row
    only if it belongs to `user_id`; returns a dict or `None`
  - Add `update_expense(expense_id, user_id, amount, category, date, description)`
    — runs a parameterised UPDATE; uses `user_id` in the WHERE clause as an
    ownership guard

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format user input into SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard on both GET and POST: check `session.get("user_id")`; if absent,
  `redirect(url_for("login"))`
- Ownership guard: the SELECT and UPDATE queries must both include
  `WHERE id = ? AND user_id = ?`; if the row is not returned, call `abort(404)`
- Amount validation: must be convertible to `float` and greater than 0
- Category validation: must be one of `EXPENSE_CATEGORIES`
- Date validation: must parse with `datetime.date.fromisoformat()`
- Description: optional; strip whitespace; store `None` if blank
- On validation failure: re-render `edit_expense.html` with previously submitted
  values preserved (not the original DB values)
- On successful update: `flash("Expense updated.")` then
  `redirect(url_for("profile"))`
- The profile template must pass `id` on each expense dict so the edit link can
  be rendered; verify `get_recent_transactions` returns the `id` field (add it if
  missing)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` without being logged in redirects to `/login`
- [ ] GET `/expenses/<id>/edit` for an expense owned by the logged-in user returns
  HTTP 200 with all fields pre-filled (amount, category, date, description)
- [ ] Submitting valid changes updates the row in the `expenses` table and
  redirects to `/profile`
- [ ] A flash message "Expense updated." is visible on the profile page after a
  successful save
- [ ] The updated values are reflected in the transaction list on `/profile`
- [ ] GET `/expenses/<id>/edit` where `id` does not exist or belongs to a
  different user returns HTTP 404
- [ ] Submitting with a missing or zero amount re-renders the form with an error
  and does not modify the database
- [ ] Submitting with an invalid date re-renders the form with an error
- [ ] Submitting with an unrecognised category re-renders the form with an error
- [ ] Each expense row on `/profile` has a working "Edit" link that navigates to
  the correct edit URL
- [ ] No hex colour values appear in `edit_expense.html` — only CSS variables
