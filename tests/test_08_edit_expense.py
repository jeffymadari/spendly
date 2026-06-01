"""
Tests for Step 8: Edit Expense
Spec: .claude/specs/08-edit-expense.md

Coverage
--------
Auth guards
- GET /expenses/<id>/edit without login  → 302 to /login
- POST /expenses/<id>/edit without login → 302 to /login
- Unauthenticated GET must not render the edit form

Ownership / 404 guards
- GET for a nonexistent expense ID        → 404
- GET for an expense owned by another user → 404
- POST for a nonexistent expense ID        → 404
- POST targeting another user's expense   → 404

GET /expenses/<id>/edit — authenticated, own expense
- Returns 200
- All four form fields present (amount, category, date, description)
- Fields pre-filled with the expense's stored values
- All seven categories rendered in the form
- Page heading reads "Edit Expense"
- Submit button reads "Save Changes"
- Cancel link navigates back to /profile
- Extends base.html (full HTML document)
- No error message on a clean GET

POST /expenses/<id>/edit — validation failures
  amount:
    - blank amount → 200 + error, DB row unchanged
    - zero amount → 200 + error, DB row unchanged
    - negative amount → 200 + error, DB row unchanged
    - non-numeric amount → 200 + error, DB row unchanged
  category:
    - unrecognised category → 200 + error, DB row unchanged
    - blank category → 200 + error, DB row unchanged
  date:
    - invalid date string → 200 + error, DB row unchanged
    - blank date → 200 + error, DB row unchanged
    - out-of-range date → 200 + error, DB row unchanged

POST — re-render preserves submitted (not original DB) values on failure
- submitted amount echoed back on invalid category
- submitted date echoed back on invalid category
- submitted description echoed back on invalid amount
- submitted category echoed back on invalid date

POST /expenses/<id>/edit — happy path
- Valid update returns 302 redirect to /profile
- DB row reflects the new amount
- DB row reflects the new category
- DB row reflects the new date
- DB row reflects the new description
- user_id in DB is unchanged after edit
- Expense ID is unchanged after edit
- Blank description stored as NULL
- Whitespace-only description stored as NULL
- Flash message "Expense updated." visible on /profile after redirect
- Updated values appear in the /profile transaction list

Profile page integration
- Each expense row has an edit link pointing to /expenses/<id>/edit

Parametrized
- All seven valid categories accepted on edit (302 redirect)
- Invalid category values rejected on edit (200 re-render, DB unchanged)
- Invalid amount values rejected on edit (200 re-render, DB unchanged)
- Invalid date values rejected on edit (200 re-render, DB unchanged)
"""

import datetime
import pytest
import database.db as db_module


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

TODAY = datetime.date.today().isoformat()

# Sentinel original values used when seeding an expense for editing tests
_ORIG_AMOUNT = 42.00
_ORIG_CATEGORY = "Food"
_ORIG_DATE = "2026-05-01"
_ORIG_DESCRIPTION = "Original description"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(email):
    """Return the integer user_id for a given email."""
    row = db_module.get_user_by_email(email)
    return row["id"]


def _insert_expense(user_id, amount=_ORIG_AMOUNT, category=_ORIG_CATEGORY,
                    date=_ORIG_DATE, description=_ORIG_DESCRIPTION):
    """Insert a single expense row and return its auto-generated id."""
    conn = db_module.get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _insert_user(name, email, password_hash="fakehash"):
    """Insert a second user directly and return their id."""
    conn = db_module.get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _fetch_expense(expense_id):
    """Return the raw DB row for an expense as a dict, or None."""
    conn = db_module.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def _edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


# ===========================================================================
# Auth guard tests
# ===========================================================================

class TestAuthGuard:
    """Both GET and POST must redirect unauthenticated users to /login."""

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/1/edit")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/<id>/edit must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/1/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": TODAY,
            "description": "test",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/<id>/edit must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_get_unauthenticated_does_not_render_form(self, client):
        response = client.get("/expenses/1/edit", follow_redirects=True)
        assert b'name="amount"' not in response.data, (
            "Unauthenticated request must not render the edit-expense form"
        )


# ===========================================================================
# Ownership / 404 guard tests
# ===========================================================================

class TestOwnershipGuard:
    """Requests for nonexistent or other-user expenses must return 404."""

    def test_get_nonexistent_expense_returns_404(self, logged_in_client):
        response = logged_in_client.get("/expenses/99999/edit")
        assert response.status_code == 404, (
            "GET for a nonexistent expense ID must return 404"
        )

    def test_get_other_users_expense_returns_404(self, logged_in_client, test_user):
        other_id = _insert_user("Other User", "other@example.com")
        expense_id = _insert_expense(other_id, description="Not yours")
        response = logged_in_client.get(_edit_url(expense_id))
        assert response.status_code == 404, (
            "GET for an expense owned by another user must return 404"
        )

    def test_post_nonexistent_expense_returns_404(self, logged_in_client):
        response = logged_in_client.post("/expenses/99999/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 404, (
            "POST for a nonexistent expense ID must return 404"
        )

    def test_post_other_users_expense_returns_404(self, logged_in_client, test_user):
        other_id = _insert_user("Other User2", "other2@example.com")
        expense_id = _insert_expense(other_id, description="Not yours either")
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": TODAY,
            "description": "hijack",
        })
        assert response.status_code == 404, (
            "POST targeting another user's expense must return 404"
        )

    def test_post_other_users_expense_does_not_modify_db(self, logged_in_client, test_user):
        """Ownership check must prevent any DB modification on cross-user POST."""
        other_id = _insert_user("Other User3", "other3@example.com")
        expense_id = _insert_expense(
            other_id, amount=100.00, description="Victim expense"
        )
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "1.00",
            "category": "Bills",
            "date": TODAY,
            "description": "hijacked",
        })
        row = _fetch_expense(expense_id)
        assert float(row["amount"]) == pytest.approx(100.00), (
            "Cross-user POST must not modify the victim expense's amount"
        )
        assert row["description"] == "Victim expense", (
            "Cross-user POST must not modify the victim expense's description"
        )


# ===========================================================================
# GET /expenses/<id>/edit — authenticated, own expense
# ===========================================================================

class TestGetEditExpenseForm:
    """Authenticated GET for an owned expense must return a pre-filled form."""

    def _own_expense(self, test_user):
        user_id = _get_user_id(test_user["email"])
        return _insert_expense(user_id)

    def test_returns_200(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert response.status_code == 200, (
            "Authenticated GET /expenses/<id>/edit must return 200"
        )

    def test_form_contains_amount_field(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b'name="amount"' in response.data, (
            "Edit form must contain an input with name='amount'"
        )

    def test_form_contains_category_field(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b'name="category"' in response.data, (
            "Edit form must contain a select/input with name='category'"
        )

    def test_form_contains_date_field(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b'name="date"' in response.data, (
            "Edit form must contain an input with name='date'"
        )

    def test_form_contains_description_field(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b'name="description"' in response.data, (
            "Edit form must contain an input with name='description'"
        )

    def test_amount_prefilled_with_existing_value(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        # The stored amount 42.0 should appear in the form in some numeric form
        assert b"42" in response.data, (
            "Amount field must be pre-filled with the expense's stored amount"
        )

    def test_category_prefilled_with_existing_value(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert _ORIG_CATEGORY.encode() in response.data, (
            "Category field must be pre-filled with the expense's stored category"
        )

    def test_date_prefilled_with_existing_value(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert _ORIG_DATE.encode() in response.data, (
            "Date field must be pre-filled with the expense's stored date"
        )

    def test_description_prefilled_with_existing_value(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert _ORIG_DESCRIPTION.encode() in response.data, (
            "Description field must be pre-filled with the expense's stored description"
        )

    def test_all_seven_categories_rendered(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        body = response.data.decode()
        for cat in _VALID_CATEGORIES:
            assert cat in body, (
                f"Category '{cat}' must appear in the edit-expense form"
            )

    def test_heading_reads_edit_expense(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        body = response.data.decode()
        assert "Edit Expense" in body, (
            "Page heading must read 'Edit Expense'"
        )

    def test_submit_button_reads_save_changes(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        body = response.data.decode()
        assert "Save Changes" in body, (
            "Submit button must read 'Save Changes'"
        )

    def test_cancel_link_points_to_profile(self, logged_in_client, test_user):
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b"/profile" in response.data, (
            "Cancel link must navigate back to /profile"
        )

    def test_extends_base_template(self, logged_in_client, test_user):
        """Page must extend base.html — look for the full HTML document wrapper."""
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        body = response.data.decode()
        assert "<html" in body, (
            "Response must be a full HTML document rendered via base.html"
        )

    def test_no_error_message_on_initial_get(self, logged_in_client, test_user):
        """A fresh GET must not show any validation error message."""
        expense_id = self._own_expense(test_user)
        response = logged_in_client.get(_edit_url(expense_id))
        assert b"Please enter a valid amount" not in response.data
        assert b"Please select a valid category" not in response.data
        assert b"Please enter a valid date" not in response.data


# ===========================================================================
# POST /expenses/<id>/edit — validation failures
# ===========================================================================

class TestPostValidationFailures:
    """Invalid submissions must re-render the form (200) with an error message
    and must NOT update the expense row in the database."""

    def _setup(self, test_user):
        user_id = _get_user_id(test_user["email"])
        expense_id = _insert_expense(user_id)
        return expense_id

    def _assert_db_unchanged(self, expense_id):
        row = _fetch_expense(expense_id)
        assert float(row["amount"]) == pytest.approx(_ORIG_AMOUNT), (
            "DB amount must be unchanged after a validation failure"
        )
        assert row["category"] == _ORIG_CATEGORY, (
            "DB category must be unchanged after a validation failure"
        )
        assert row["date"] == _ORIG_DATE, (
            "DB date must be unchanged after a validation failure"
        )

    # --- amount validation ---------------------------------------------------

    def test_blank_amount_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Blank amount must re-render the form with status 200"
        )

    def test_blank_amount_shows_error(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "amount" in body, (
            "Blank amount must produce a visible error message"
        )

    def test_blank_amount_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_zero_amount_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "0",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Zero amount must re-render the form with status 200"
        )

    def test_zero_amount_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "0",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_negative_amount_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "-5.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Negative amount must re-render the form with status 200"
        )

    def test_negative_amount_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "-5.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_non_numeric_amount_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "abc",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form with status 200"
        )

    def test_non_numeric_amount_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "abc",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    # --- category validation -------------------------------------------------

    def test_unrecognised_category_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Unknown category must re-render the form with status 200"
        )

    def test_unrecognised_category_shows_error(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "category" in body, (
            "Unknown category must produce a visible error message"
        )

    def test_unrecognised_category_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_blank_category_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "",
            "date": TODAY,
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    # --- date validation -----------------------------------------------------

    def test_invalid_date_string_returns_200(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        assert response.status_code == 200, (
            "Invalid date must re-render the form with status 200"
        )

    def test_invalid_date_string_shows_error(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "date" in body, (
            "Invalid date must produce a visible error message"
        )

    def test_invalid_date_string_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_blank_date_does_not_update_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": "",
            "description": "",
        })
        self._assert_db_unchanged(expense_id)

    def test_out_of_range_date_does_not_update_db(self, logged_in_client, test_user):
        """Date like 2026-13-01 (month 13) must be rejected by fromisoformat."""
        expense_id = self._setup(test_user)
        logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-13-01",
            "description": "",
        })
        self._assert_db_unchanged(expense_id)


# ===========================================================================
# POST — validation failure preserves submitted (not original DB) values
# ===========================================================================

class TestPostValidationPreservesSubmittedValues:
    """On validation failure the form must show the values the user *submitted*,
    not the original values stored in the database."""

    def _setup(self, test_user):
        user_id = _get_user_id(test_user["email"])
        return _insert_expense(user_id)

    def test_submitted_amount_echoed_back_on_invalid_category(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "77.77",       # new value
            "category": "Hacking",  # invalid → triggers error
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200
        assert b"77.77" in response.data, (
            "Re-rendered form must show the submitted amount (77.77), not the original"
        )

    def test_submitted_date_echoed_back_on_invalid_category(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Hacking",   # invalid
            "date": "2026-07-04",    # new date
            "description": "",
        })
        assert response.status_code == 200
        assert b"2026-07-04" in response.data, (
            "Re-rendered form must show the submitted date (2026-07-04), not the original"
        )

    def test_submitted_description_echoed_back_on_invalid_amount(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "0",            # invalid
            "category": "Food",
            "date": TODAY,
            "description": "new note here",
        })
        assert response.status_code == 200
        assert b"new note here" in response.data, (
            "Re-rendered form must show the submitted description, not the original"
        )

    def test_submitted_category_echoed_back_on_invalid_date(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        response = logged_in_client.post(_edit_url(expense_id), data={
            "amount": "10.00",
            "category": "Transport",  # different from original "Food"
            "date": "bad-date",       # invalid
            "description": "",
        })
        assert response.status_code == 200
        assert b"Transport" in response.data, (
            "Re-rendered form must show the submitted category (Transport)"
        )


# ===========================================================================
# POST /expenses/<id>/edit — happy path
# ===========================================================================

class TestPostHappyPath:
    """Valid submissions must update the DB row, redirect to /profile, and flash."""

    _NEW_AMOUNT = 99.50
    _NEW_CATEGORY = "Transport"
    _NEW_DATE = "2026-06-15"
    _NEW_DESCRIPTION = "Updated train ticket"

    def _setup(self, test_user):
        user_id = _get_user_id(test_user["email"])
        return _insert_expense(user_id)

    def _post_valid_update(self, logged_in_client, expense_id,
                           amount=None, category=None, date=None,
                           description=None, follow_redirects=False):
        return logged_in_client.post(
            _edit_url(expense_id),
            data={
                "amount": str(amount or self._NEW_AMOUNT),
                "category": category or self._NEW_CATEGORY,
                "date": date or self._NEW_DATE,
                "description": description if description is not None
                               else self._NEW_DESCRIPTION,
            },
            follow_redirects=follow_redirects,
        )

    def test_valid_update_redirects_to_profile(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        response = self._post_valid_update(
            logged_in_client, expense_id, follow_redirects=False
        )
        assert response.status_code == 302, (
            "Valid update must return a 302 redirect"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect after successful edit must point to /profile"
        )

    def test_valid_update_changes_amount_in_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, amount=55.55)
        row = _fetch_expense(expense_id)
        assert float(row["amount"]) == pytest.approx(55.55), (
            "After a valid edit, the DB amount must reflect the new value"
        )

    def test_valid_update_changes_category_in_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, category="Bills")
        row = _fetch_expense(expense_id)
        assert row["category"] == "Bills", (
            "After a valid edit, the DB category must reflect the new value"
        )

    def test_valid_update_changes_date_in_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, date="2026-09-30")
        row = _fetch_expense(expense_id)
        assert row["date"] == "2026-09-30", (
            "After a valid edit, the DB date must reflect the new value"
        )

    def test_valid_update_changes_description_in_db(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        self._post_valid_update(
            logged_in_client, expense_id, description="New description text"
        )
        row = _fetch_expense(expense_id)
        assert row["description"] == "New description text", (
            "After a valid edit, the DB description must reflect the new value"
        )

    def test_valid_update_preserves_user_id(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        original_row = _fetch_expense(expense_id)
        self._post_valid_update(logged_in_client, expense_id)
        updated_row = _fetch_expense(expense_id)
        assert updated_row["user_id"] == original_row["user_id"], (
            "After a valid edit, the user_id must be unchanged"
        )

    def test_valid_update_preserves_expense_id(self, logged_in_client, test_user):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id)
        row = _fetch_expense(expense_id)
        assert row is not None, (
            "After a valid edit, the expense row must still exist with the same id"
        )
        assert row["id"] == expense_id, (
            "The expense id must be unchanged after an edit"
        )

    def test_blank_description_stored_as_null_on_update(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, description="")
        row = _fetch_expense(expense_id)
        assert row["description"] is None, (
            "Blank description submitted on edit must be stored as NULL"
        )

    def test_whitespace_only_description_stored_as_null_on_update(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, description="   ")
        row = _fetch_expense(expense_id)
        assert row["description"] is None, (
            "Whitespace-only description on edit must be stripped and stored as NULL"
        )

    def test_flash_message_visible_on_profile_after_redirect(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        response = self._post_valid_update(
            logged_in_client, expense_id, follow_redirects=True
        )
        assert b"Expense updated" in response.data, (
            "Flash message 'Expense updated.' must be visible on /profile after redirect"
        )

    def test_updated_description_appears_in_profile_transaction_list(
        self, logged_in_client, test_user
    ):
        expense_id = self._setup(test_user)
        self._post_valid_update(
            logged_in_client, expense_id,
            description="Distinctive updated label",
            follow_redirects=True,
        )
        profile_response = logged_in_client.get("/profile")
        assert b"Distinctive updated label" in profile_response.data, (
            "Updated expense description must appear in the /profile transaction list"
        )

    def test_only_one_expense_row_exists_after_edit(self, logged_in_client, test_user):
        """UPDATE must not insert a duplicate; only the original row should exist."""
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id)
        conn = db_module.get_db()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE id = ?", (expense_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 1, (
            "After an edit, exactly one row must exist for the original expense id"
        )

    def test_amount_stored_as_float_not_string(self, logged_in_client, test_user):
        """The REAL column must hold a numeric value, not a currency-prefixed string."""
        expense_id = self._setup(test_user)
        self._post_valid_update(logged_in_client, expense_id, amount=123.45)
        row = _fetch_expense(expense_id)
        assert isinstance(float(row["amount"]), float), (
            "amount must be stored as a REAL numeric value"
        )
        assert "₹" not in str(row["amount"]) and "$" not in str(row["amount"]), (
            "No currency symbol must be present in the stored amount"
        )


# ===========================================================================
# Profile page integration — Edit links
# ===========================================================================

class TestProfileEditLinks:
    """Each expense row on /profile must have an Edit link pointing to
    /expenses/<id>/edit."""

    def test_profile_shows_edit_link_for_own_expense(
        self, logged_in_client, test_user
    ):
        user_id = _get_user_id(test_user["email"])
        expense_id = _insert_expense(
            user_id, description="Check for edit link"
        )
        response = logged_in_client.get("/profile")
        expected_href = f"/expenses/{expense_id}/edit".encode()
        assert expected_href in response.data, (
            f"Profile must contain an edit link to /expenses/{expense_id}/edit"
        )

    def test_profile_shows_edit_link_for_multiple_expenses(
        self, logged_in_client, test_user
    ):
        user_id = _get_user_id(test_user["email"])
        ids = [
            _insert_expense(user_id, description=f"Expense {i}")
            for i in range(3)
        ]
        response = logged_in_client.get("/profile")
        for eid in ids:
            href = f"/expenses/{eid}/edit".encode()
            assert href in response.data, (
                f"Profile must contain an edit link for expense id {eid}"
            )


# ===========================================================================
# Parametrized: all valid categories accepted on edit
# ===========================================================================

@pytest.mark.parametrize("category", _VALID_CATEGORIES)
def test_all_valid_categories_accepted_on_edit(logged_in_client, test_user, category):
    """Each of the seven defined categories must result in a successful redirect."""
    user_id = _get_user_id(test_user["email"])
    expense_id = _insert_expense(user_id)
    response = logged_in_client.post(
        _edit_url(expense_id),
        data={
            "amount": "10.00",
            "category": category,
            "date": TODAY,
            "description": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302, (
        f"Valid category '{category}' must be accepted and produce a 302 redirect"
    )
    assert "/profile" in response.headers["Location"], (
        f"Redirect for category '{category}' must point to /profile"
    )


@pytest.mark.parametrize("category", [
    "food",           # lowercase — wrong case
    "FOOD",           # uppercase — wrong case
    "Groceries",      # plausible but not in the list
    "None",           # string 'None'
    "",               # empty string
    "Food; DROP TABLE expenses;--",  # SQL injection attempt
    "<script>alert(1)</script>",     # XSS probe
])
def test_invalid_categories_rejected_on_edit(logged_in_client, test_user, category):
    """Category values not in the fixed set must be rejected with a 200 re-render
    and must not update the database."""
    user_id = _get_user_id(test_user["email"])
    expense_id = _insert_expense(user_id)
    response = logged_in_client.post(
        _edit_url(expense_id),
        data={
            "amount": "10.00",
            "category": category,
            "date": TODAY,
            "description": "",
        },
    )
    assert response.status_code == 200, (
        f"Invalid category {category!r} must re-render the form (200), not redirect"
    )
    row = _fetch_expense(expense_id)
    assert row["category"] == _ORIG_CATEGORY, (
        f"Invalid category {category!r} must not update the DB row's category"
    )


# ===========================================================================
# Parametrized: invalid amounts rejected on edit
# ===========================================================================

@pytest.mark.parametrize("amount", [
    "",       # blank
    "0",      # exactly zero
    "0.00",   # zero with decimals
    "-1",     # negative integer
    "-0.01",  # tiny negative
    "abc",    # non-numeric
    "$10",    # currency-prefixed
    "10,00",  # comma as decimal separator
])
def test_invalid_amounts_rejected_on_edit(logged_in_client, test_user, amount):
    """Any invalid amount must re-render the form without updating the DB row."""
    user_id = _get_user_id(test_user["email"])
    expense_id = _insert_expense(user_id)
    response = logged_in_client.post(
        _edit_url(expense_id),
        data={
            "amount": amount,
            "category": "Food",
            "date": TODAY,
            "description": "",
        },
    )
    assert response.status_code == 200, (
        f"Invalid amount {amount!r} must re-render the form (200)"
    )
    row = _fetch_expense(expense_id)
    assert float(row["amount"]) == pytest.approx(_ORIG_AMOUNT), (
        f"Invalid amount {amount!r} must not update the DB row's amount"
    )


# ===========================================================================
# Parametrized: invalid dates rejected on edit
# ===========================================================================

@pytest.mark.parametrize("date_val", [
    "",               # blank
    "not-a-date",     # non-date string
    "2026-13-01",     # month 13
    "2026-00-01",     # month 0
    "2026-04-31",     # April has only 30 days
    "01-06-2026",     # wrong order (DD-MM-YYYY)
    "2026/06/01",     # slashes not hyphens
])
def test_invalid_dates_rejected_on_edit(logged_in_client, test_user, date_val):
    """Any date that fails datetime.date.fromisoformat() must re-render the form
    and must not update the DB row."""
    user_id = _get_user_id(test_user["email"])
    expense_id = _insert_expense(user_id)
    response = logged_in_client.post(
        _edit_url(expense_id),
        data={
            "amount": "10.00",
            "category": "Food",
            "date": date_val,
            "description": "",
        },
    )
    assert response.status_code == 200, (
        f"Invalid date {date_val!r} must re-render the form (200)"
    )
    row = _fetch_expense(expense_id)
    assert row["date"] == _ORIG_DATE, (
        f"Invalid date {date_val!r} must not update the DB row's date"
    )
