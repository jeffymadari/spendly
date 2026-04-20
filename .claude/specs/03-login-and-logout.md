# Spec: Login and Logout

## Overview
Wire up the login and logout flows so registered users can authenticate and end their session. The `/login` route currently only renders a static form and `/logout` is a placeholder string. This step adds `POST /login` with credential verification and session creation, implements `GET /logout` to clear the session, creates a minimal dashboard landing page for authenticated users, and updates the navbar to reflect login state.

## Depends on
- Step 01 (Database Setup) — requires the `users` table and `get_db()` to be in place.
- Step 02 (Registration) — requires the password hashing scheme (`werkzeug`) and session variables (`user_id`, `user_name`) established there.

## Routes
- `GET /login` — render the login form — public
- `POST /login` — verify credentials, start session, redirect to dashboard — public
- `GET /logout` — clear session, redirect to landing — logged-in
- `GET /dashboard` — render the dashboard page — logged-in

## Database changes
No database changes. The existing `users` table with `id`, `email`, and `password_hash` columns is sufficient.

## Templates
- **Modify:** `templates/login.html`
  - Repopulate `email` field on validation error: add `value="{{ email or '' }}"` to the email input
- **Modify:** `templates/base.html`
  - Update `.nav-links` to show conditional nav based on `session`:
    - Logged-out: "Sign in" + "Get started" (current behaviour)
    - Logged-in: user name display + "Dashboard" link + "Sign out" link
- **Create:** `templates/dashboard.html`
  - Extends `base.html`
  - Shows a welcome heading with `{{ session['user_name'] }}`
  - Placeholder message: expenses list coming in a later step

## Files to change
- `app.py`
  - Convert `GET /login` to handle both GET and POST methods
  - Implement `POST /login`: read email + password, look up user, verify hash, set session, redirect to dashboard
  - Implement `GET /logout`: clear session, redirect to landing
  - Implement `GET /dashboard`: require login (redirect to `/login` if no session), render `dashboard.html`
  - Import `check_password_hash` from `werkzeug.security`
- `templates/login.html` — repopulate email on error
- `templates/base.html` — conditional nav links based on `session`

## Files to create
- `templates/dashboard.html` — minimal authenticated landing page

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed with werkzeug).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — no string formatting in SQL
- Passwords verified with `werkzeug.security.check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Login error message must be intentionally vague: "Invalid email or password." — never reveal which field is wrong
- On successful login: set `session['user_id']` and `session['user_name']`, then redirect to `/dashboard`
- On failed login: re-render `login.html` with `error` message and preserved `email` value
- Logout must use `session.clear()` (not individual key deletion), then redirect to `url_for('landing')`
- Dashboard must guard against unauthenticated access: `if 'user_id' not in session: return redirect(url_for('login'))`
- After registration (Step 02) the user is redirected to `/login` — this step does not change that behaviour; the user must log in manually after registering

## Definition of done
- [ ] `GET /login` renders the form correctly
- [ ] Submitting an email that does not exist shows "Invalid email or password." without crashing
- [ ] Submitting a correct email with the wrong password shows "Invalid email or password."
- [ ] Submitting valid credentials sets `session['user_id']` and redirects to `/dashboard`
- [ ] `GET /dashboard` is accessible after login and shows the user's name
- [ ] `GET /dashboard` redirects unauthenticated visitors to `/login`
- [ ] `GET /logout` clears the session and redirects to the landing page
- [ ] After logout, visiting `/dashboard` redirects back to `/login`
- [ ] Navbar shows "Dashboard" and "Sign out" when a user is logged in
- [ ] Navbar shows "Sign in" and "Get started" when no user is logged in
- [ ] Email field is repopulated when the login form is re-shown after an error
- [ ] App starts without errors after all changes
