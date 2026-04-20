# Spec: Registration

## Overview
Implement the user registration flow so new visitors can create a Spendly account. The `/register` route currently only renders a static form — this step wires it up with `POST` handling, server-side validation, password hashing, a database insert, and session creation so the user lands on a dashboard after signing up.

## Depends on
- Step 01 (Database Setup) — requires the `users` table and `get_db()` to be in place.

## Routes
- `GET /register` — render the registration form — public
- `POST /register` — handle form submission, create user, start session — public

## Database changes
No new tables or columns. The `users` table from Step 01 is sufficient:
- `id`, `name`, `email`, `password_hash`, `created_at`

## Templates
- **Modify:** `templates/register.html`
  - Display flash/inline error messages for validation failures (field already present as `{{ error }}`)
  - Re-populate `name` and `email` fields on validation error (preserve input)
  - Show success redirect (no template change needed — redirect after success)

## Files to change
- `app.py` — add `POST` handler for `/register`; import `session`, `redirect`, `url_for`, `request`, `flash` from Flask; add `app.secret_key`
- `templates/register.html` — add `value="{{ name or '' }}"` and `value="{{ email or '' }}"` to preserve input on error

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.generate_password_hash` (already installed).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — no string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set (use a hard-coded dev string for now; a comment noting it should come from env in production is sufficient)
- Validation must happen server-side before any DB insert:
  - `name` non-empty
  - `email` non-empty and contains `@`
  - `password` minimum 8 characters
  - Email uniqueness — catch `sqlite3.IntegrityError` or pre-check with a SELECT
- On success: create `session['user_id']` and `session['user_name']`, then redirect to `/dashboard` (placeholder route ok for now)
- On failure: re-render `register.html` with `error` message and preserved `name`/`email` values

## Definition of done
- [ ] `GET /register` still renders the form correctly
- [ ] Submitting a blank form shows a validation error without crashing
- [ ] Submitting a password shorter than 8 characters shows an error
- [ ] Submitting a duplicate email shows "Email already registered" (or similar) error
- [ ] Valid submission inserts one new row into the `users` table with a hashed password
- [ ] After valid submission, `session['user_id']` is set
- [ ] After valid submission, the browser is redirected (not re-rendered)
- [ ] `name` and `email` fields are repopulated when the form is re-shown after an error
- [ ] App starts without errors after changes to `app.py`
