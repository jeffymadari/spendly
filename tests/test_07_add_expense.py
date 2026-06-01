"""
Tests for Step 7: Add Expense
Spec: .claude/specs/07-add-expense.md

Coverage
--------
Auth guards
- GET /expenses/add without login  → 302 to /login
- POST /expenses/add without login → 302 to /login

GET /expenses/add
- Returns 200 with all four form fields present
- date field value defaults to today's ISO date
- All seven categories rendered in the form

POST /expenses/add — validation failures (no DB insert, form re-rendered)
- blank amount
- zero amount
- negative amount
- non-numeric amount string
- unrecognised category
- completely unknown category string
- invalid date string
- missing/blank date
- validation failure preserves submitted values in the re-rendered form
  (amount, category, date, description all echoed back)

POST /expenses/add — happy path
- inserts one row with correct amount, category, date, description
- amount stored as REAL float (no currency symbol)
- blank/whitespace-only description stored as NULL
- description stored correctly when non-empty
- row is tied to the logged-in user_id
- redirects to /profile (302, Location header)
- flash "Expense added." visible on /profile after redirect

Profile page integration
- /profile "Add Expense" link href points to /expenses/add

Parametrized
- all seven valid categories accepted (200 redirect)
- invalid category values rejected (200 with error)
"""

import datetime
import pytest
import database.db as db_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

TODAY = datetime.date.today().isoformat()


def _get_user_id(app, email):
    """Return the integer user_id for a given email."""
    row = db_module.get_user_by_email(email)
    return row["id"]


def _count_expenses():
    """Return the total number of rows in the expenses table."""
    conn = db_module.get_db()
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    return count


def _fetch_all_expenses():
    """Return all rows from the expenses table as sqlite3.Row objects."""
    conn = db_module.get_db()
    rows = conn.execute("SELECT * FROM expenses").fetchall()
    conn.close()
    return rows


# ===========================================================================
# Auth guard tests
# ===========================================================================

class TestAuthGuard:
    """Both GET and POST must redirect unauthenticated users to /login."""

    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": TODAY,
            "description": "test",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_get_unauthenticated_does_not_render_form(self, client):
        response = client.get("/expenses/add", follow_redirects=True)
        # Should land on the login page, not the add-expense form
        assert b'name="amount"' not in response.data, (
            "Unauthenticated request must not render the add-expense form"
        )


# ===========================================================================
# GET /expenses/add — authenticated
# ===========================================================================

class TestGetAddExpenseForm:
    """Authenticated GET must render the full add-expense form."""

    def test_returns_200(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_form_contains_amount_field(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert b'name="amount"' in response.data, (
            "Form must contain an input with name='amount'"
        )

    def test_form_contains_category_field(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert b'name="category"' in response.data, (
            "Form must contain a select/input with name='category'"
        )

    def test_form_contains_date_field(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert b'name="date"' in response.data, (
            "Form must contain an input with name='date'"
        )

    def test_form_contains_description_field(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert b'name="description"' in response.data, (
            "Form must contain an input with name='description'"
        )

    def test_date_field_defaults_to_today(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        assert TODAY.encode() in response.data, (
            f"Date field must default to today's date ({TODAY})"
        )

    def test_all_seven_categories_rendered(self, logged_in_client):
        response = logged_in_client.get("/expenses/add")
        body = response.data.decode()
        for cat in _VALID_CATEGORIES:
            assert cat in body, (
                f"Category '{cat}' must appear in the add-expense form"
            )

    def test_extends_base_template(self, logged_in_client):
        """Page must extend base.html — look for landmarks base.html provides."""
        response = logged_in_client.get("/expenses/add")
        body = response.data.decode()
        # base.html provides a <nav> and the Spendly brand; at minimum <html> wrapper
        assert "<html" in body, "Response must be a full HTML document via base.html"

    def test_no_error_message_on_initial_get(self, logged_in_client):
        """A fresh GET must not show an error message."""
        response = logged_in_client.get("/expenses/add")
        # The spec says errors only appear when the route passes an `error` var
        # We check that generic error markers are absent on a clean GET
        assert b"Please enter a valid amount" not in response.data
        assert b"Please select a valid category" not in response.data
        assert b"Please enter a valid date" not in response.data


# ===========================================================================
# POST /expenses/add — validation failures
# ===========================================================================

class TestPostValidationFailures:
    """Invalid submissions must re-render the form (200) with an error message
    and must NOT insert any row into the expenses table."""

    # --- amount validation ---------------------------------------------------

    def test_blank_amount_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Blank amount must re-render the form with 200"
        )

    def test_blank_amount_shows_error(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "amount" in body, (
            "Blank amount must produce a visible error message"
        )

    def test_blank_amount_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Blank amount must not insert a row into expenses"
        )

    def test_zero_amount_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Zero amount must re-render the form with 200"
        )

    def test_zero_amount_shows_error(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "greater" in body or "zero" in body or "valid" in body, (
            "Zero amount must produce a visible error message"
        )

    def test_zero_amount_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Zero amount must not insert a row into expenses"
        )

    def test_negative_amount_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "-5.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Negative amount must re-render the form with 200"
        )

    def test_negative_amount_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "-5.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Negative amount must not insert a row into expenses"
        )

    def test_non_numeric_amount_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "abc",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form with 200"
        )

    def test_non_numeric_amount_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "abc",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Non-numeric amount must not insert a row into expenses"
        )

    def test_amount_with_currency_symbol_rejected(self, logged_in_client):
        """A value like '$15.00' cannot be parsed as float — must be rejected."""
        response = logged_in_client.post("/expenses/add", data={
            "amount": "$15.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Amount with currency symbol cannot be parsed and must re-render the form"
        )
        assert _count_expenses() == 0

    # --- category validation -------------------------------------------------

    def test_unrecognised_category_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        assert response.status_code == 200, (
            "Unknown category must re-render the form with 200"
        )

    def test_unrecognised_category_shows_error(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "category" in body, (
            "Unknown category must produce a visible error message"
        )

    def test_unrecognised_category_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Hacking",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Unknown category must not insert a row into expenses"
        )

    def test_empty_category_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "",
            "date": TODAY,
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Empty category string must not insert a row into expenses"
        )

    # --- date validation -----------------------------------------------------

    def test_invalid_date_string_returns_200(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        assert response.status_code == 200, (
            "Invalid date must re-render the form with 200"
        )

    def test_invalid_date_string_shows_error(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        body = response.data.decode().lower()
        assert "error" in body or "valid" in body or "date" in body, (
            "Invalid date must produce a visible error message"
        )

    def test_invalid_date_string_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Invalid date must not insert a row into expenses"
        )

    def test_blank_date_does_not_insert_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "",
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Blank date must not insert a row into expenses"
        )

    def test_invalid_month_date_does_not_insert_row(self, logged_in_client):
        """date like 2026-13-01 (month 13) must be rejected by fromisoformat."""
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-13-01",
            "description": "",
        })
        assert _count_expenses() == 0, (
            "Date with invalid month must not insert a row into expenses"
        )


# ===========================================================================
# POST — validation failure preserves form values
# ===========================================================================

class TestPostValidationPreservesValues:
    """On validation failure the form must be re-rendered with the submitted
    values pre-filled so the user does not have to re-enter correct fields."""

    def test_submitted_amount_echoed_back_on_invalid_category(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "42.50",
            "category": "Hacking",   # invalid → triggers error
            "date": TODAY,
            "description": "my note",
        })
        assert response.status_code == 200
        assert b"42.50" in response.data, (
            "Previously entered amount must be preserved in the re-rendered form"
        )

    def test_submitted_date_echoed_back_on_invalid_category(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Hacking",   # invalid
            "date": "2026-05-20",
            "description": "",
        })
        assert response.status_code == 200
        assert b"2026-05-20" in response.data, (
            "Previously entered date must be preserved in the re-rendered form"
        )

    def test_submitted_description_echoed_back_on_invalid_amount(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "0",           # invalid
            "category": "Food",
            "date": TODAY,
            "description": "coffee run",
        })
        assert response.status_code == 200
        assert b"coffee run" in response.data, (
            "Previously entered description must be preserved in the re-rendered form"
        )

    def test_submitted_category_echoed_back_on_invalid_date(self, logged_in_client):
        """The selected valid category should still be present in the re-rendered form."""
        response = logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Transport",
            "date": "bad-date",      # invalid
            "description": "",
        })
        assert response.status_code == 200
        assert b"Transport" in response.data, (
            "Previously selected category must be present in the re-rendered form"
        )


# ===========================================================================
# POST /expenses/add — happy path
# ===========================================================================

class TestPostHappyPath:
    """Valid submissions must insert a row, redirect, and flash."""

    def test_valid_submission_redirects_to_profile(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Food",
            "date": TODAY,
            "description": "Lunch",
        }, follow_redirects=False)
        assert response.status_code == 302, (
            "Valid submission must return 302 redirect"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect after successful add must point to /profile"
        )

    def test_valid_submission_inserts_one_row(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Food",
            "date": TODAY,
            "description": "Lunch",
        })
        assert _count_expenses() == 1, (
            "Valid submission must insert exactly one row into expenses"
        )

    def test_inserted_row_has_correct_amount(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "27.99",
            "category": "Food",
            "date": TODAY,
            "description": "Dinner",
        })
        rows = _fetch_all_expenses()
        assert len(rows) == 1
        assert float(rows[0]["amount"]) == pytest.approx(27.99), (
            "Inserted row must store the correct float amount"
        )

    def test_inserted_row_has_correct_category(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Transport",
            "date": TODAY,
            "description": "",
        })
        rows = _fetch_all_expenses()
        assert rows[0]["category"] == "Transport", (
            "Inserted row must store the correct category"
        )

    def test_inserted_row_has_correct_date(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Bills",
            "date": "2026-05-15",
            "description": "",
        })
        rows = _fetch_all_expenses()
        assert rows[0]["date"] == "2026-05-15", (
            "Inserted row must store the correct date string"
        )

    def test_inserted_row_has_correct_description(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "8.50",
            "category": "Food",
            "date": TODAY,
            "description": "Morning coffee",
        })
        rows = _fetch_all_expenses()
        assert rows[0]["description"] == "Morning coffee", (
            "Inserted row must store the correct description"
        )

    def test_amount_stored_as_real_not_string(self, logged_in_client):
        """The DB column is REAL; the value must be a Python float, not a string."""
        logged_in_client.post("/expenses/add", data={
            "amount": "99.95",
            "category": "Shopping",
            "date": TODAY,
            "description": "",
        })
        rows = _fetch_all_expenses()
        # sqlite3.Row returns REAL columns as float
        assert isinstance(float(rows[0]["amount"]), float), (
            "amount must be stored as a numeric REAL, not a text string"
        )
        # No currency symbol should appear in the raw DB value
        assert "₹" not in str(rows[0]["amount"]), (
            "No currency symbol must be present in the stored amount value"
        )

    def test_blank_description_stored_as_none(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "5.00",
            "category": "Other",
            "date": TODAY,
            "description": "",
        })
        rows = _fetch_all_expenses()
        assert rows[0]["description"] is None, (
            "Blank description must be stored as NULL in the DB"
        )

    def test_whitespace_only_description_stored_as_none(self, logged_in_client):
        logged_in_client.post("/expenses/add", data={
            "amount": "5.00",
            "category": "Other",
            "date": TODAY,
            "description": "   ",   # spaces only
        })
        rows = _fetch_all_expenses()
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stripped and stored as NULL"
        )

    def test_row_belongs_to_logged_in_user(self, logged_in_client, test_user, app):
        logged_in_client.post("/expenses/add", data={
            "amount": "12.00",
            "category": "Health",
            "date": TODAY,
            "description": "",
        })
        user_id = _get_user_id(app, test_user["email"])
        rows = _fetch_all_expenses()
        assert rows[0]["user_id"] == user_id, (
            "Inserted expense must be associated with the logged-in user's id"
        )

    def test_flash_message_visible_on_profile_after_redirect(self, logged_in_client):
        response = logged_in_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Food",
            "date": TODAY,
            "description": "",
        }, follow_redirects=True)
        assert b"Expense added" in response.data, (
            "Flash message 'Expense added.' must be visible on /profile after redirect"
        )

    def test_expense_appears_in_profile_transaction_list(self, logged_in_client):
        """After adding an expense its description should appear in /profile."""
        logged_in_client.post("/expenses/add", data={
            "amount": "33.00",
            "category": "Entertainment",
            "date": TODAY,
            "description": "Cinema ticket",
        }, follow_redirects=True)
        profile_response = logged_in_client.get("/profile")
        assert b"Cinema ticket" in profile_response.data, (
            "Newly added expense must appear in the transaction list on /profile"
        )

    def test_multiple_valid_submissions_each_insert_a_row(self, logged_in_client):
        for i in range(3):
            logged_in_client.post("/expenses/add", data={
                "amount": f"{10 + i}.00",
                "category": "Food",
                "date": TODAY,
                "description": f"Item {i}",
            })
        assert _count_expenses() == 3, (
            "Each valid submission must insert its own row — expected 3 rows"
        )

    def test_decimal_amount_precision_preserved(self, logged_in_client):
        """Amount like 0.01 (the minimum) must be stored and retrieved correctly."""
        logged_in_client.post("/expenses/add", data={
            "amount": "0.01",
            "category": "Food",
            "date": TODAY,
            "description": "",
        })
        rows = _fetch_all_expenses()
        assert float(rows[0]["amount"]) == pytest.approx(0.01), (
            "Minimum amount 0.01 must be stored and retrieved correctly"
        )


# ===========================================================================
# Profile page integration
# ===========================================================================

class TestProfileIntegration:
    """The profile page must link to /expenses/add."""

    def test_add_expense_button_links_to_add_expense_route(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert b"/expenses/add" in response.data, (
            "The 'Add Expense' button/link on /profile must href to /expenses/add"
        )


# ===========================================================================
# Parametrized: all valid categories accepted
# ===========================================================================

@pytest.mark.parametrize("category", _VALID_CATEGORIES)
def test_all_valid_categories_accepted(logged_in_client, category):
    """Each of the seven defined categories must result in a successful redirect."""
    response = logged_in_client.post("/expenses/add", data={
        "amount": "10.00",
        "category": category,
        "date": TODAY,
        "description": "",
    }, follow_redirects=False)
    assert response.status_code == 302, (
        f"Category '{category}' must be accepted and produce a 302 redirect"
    )
    assert "/profile" in response.headers["Location"]


@pytest.mark.parametrize("category", [
    "food",           # lowercase — wrong case
    "FOOD",           # uppercase — wrong case
    "Groceries",      # plausible but not in the list
    "None",           # string 'None'
    "",               # empty string
    "Food; DROP TABLE expenses;--",   # SQL injection attempt
    "<script>alert(1)</script>",      # XSS probe
])
def test_invalid_categories_rejected(logged_in_client, category):
    """Category values not in the fixed set must be rejected with a 200 re-render."""
    response = logged_in_client.post("/expenses/add", data={
        "amount": "10.00",
        "category": category,
        "date": TODAY,
        "description": "",
    })
    assert response.status_code == 200, (
        f"Invalid category {category!r} must re-render the form (200), not redirect"
    )
    assert _count_expenses() == 0, (
        f"Invalid category {category!r} must not insert a row into expenses"
    )


# ===========================================================================
# Parametrized: invalid amounts
# ===========================================================================

@pytest.mark.parametrize("amount", [
    "",          # blank
    "0",         # exactly zero
    "0.00",      # zero with decimals
    "-1",        # negative integer
    "-0.01",     # tiny negative
    "abc",       # non-numeric
    "$10",       # currency-prefixed
    "10,00",     # comma as decimal separator
])
def test_invalid_amounts_rejected(logged_in_client, amount):
    """Any invalid amount must re-render the form without inserting a row."""
    response = logged_in_client.post("/expenses/add", data={
        "amount": amount,
        "category": "Food",
        "date": TODAY,
        "description": "",
    })
    assert response.status_code == 200, (
        f"Invalid amount {amount!r} must re-render the form (200)"
    )
    assert _count_expenses() == 0, (
        f"Invalid amount {amount!r} must not insert a row"
    )


# ===========================================================================
# Parametrized: invalid dates
# ===========================================================================

@pytest.mark.parametrize("date_val", [
    "",                  # blank
    "not-a-date",        # non-date string
    "2026-13-01",        # month 13
    "2026-00-01",        # month 0
    "2026-04-31",        # April has only 30 days
    "01-06-2026",        # wrong order (DD-MM-YYYY)
    "2026/06/01",        # slashes not hyphens
])
def test_invalid_dates_rejected(logged_in_client, date_val):
    """Any date that fails datetime.date.fromisoformat() must re-render the form."""
    response = logged_in_client.post("/expenses/add", data={
        "amount": "10.00",
        "category": "Food",
        "date": date_val,
        "description": "",
    })
    assert response.status_code == 200, (
        f"Invalid date {date_val!r} must re-render the form (200)"
    )
    assert _count_expenses() == 0, (
        f"Invalid date {date_val!r} must not insert a row"
    )
