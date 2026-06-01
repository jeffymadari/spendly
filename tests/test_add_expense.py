# tests/test_add_expense.py
import datetime
import pytest
import database.db as db_module


def test_get_redirects_when_not_logged_in(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_get_renders_form_when_logged_in(logged_in_client):
    response = logged_in_client.get("/expenses/add")
    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body
    assert 'name="description"' in body


def test_get_defaults_date_to_today(logged_in_client):
    response = logged_in_client.get("/expenses/add")
    today = datetime.date.today().isoformat()
    assert today.encode() in response.data


def test_get_includes_all_categories(logged_in_client):
    response = logged_in_client.get("/expenses/add")
    body = response.data.decode()
    for cat in ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]:
        assert cat in body


def test_post_missing_amount_rerenders_form(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "",
        "category": "Food",
        "date": "2026-06-01",
        "description": "",
    })
    assert response.status_code == 200
    body = response.data.decode().lower()
    assert "error" in body or "valid" in body or "amount" in body


def test_post_zero_amount_rerenders_form(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "0",
        "category": "Food",
        "date": "2026-06-01",
        "description": "",
    })
    assert response.status_code == 200
    body = response.data.decode().lower()
    assert "error" in body or "greater" in body or "positive" in body


def test_post_invalid_category_rerenders_form(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "10.00",
        "category": "Hacking",
        "date": "2026-06-01",
        "description": "",
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_invalid_date_rerenders_form(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "10.00",
        "category": "Food",
        "date": "not-a-date",
        "description": "",
    })
    assert response.status_code == 200
    assert b"error" in response.data.lower()


def test_post_validation_failure_preserves_amount(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "42.50",
        "category": "Hacking",   # invalid — triggers error
        "date": "2026-06-01",
        "description": "test",
    })
    assert response.status_code == 200
    assert b"42.50" in response.data


def test_post_invalid_does_not_insert_row(logged_in_client):
    logged_in_client.post("/expenses/add", data={
        "amount": "0",           # zero — invalid
        "category": "Food",
        "date": "2026-06-01",
        "description": "",
    })
    conn = db_module.get_db()
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    assert count == 0


def test_post_valid_expense_redirects_to_profile(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "15.00",
        "category": "Food",
        "date": "2026-06-01",
        "description": "Lunch",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]


def test_post_valid_expense_inserts_row(logged_in_client):
    logged_in_client.post("/expenses/add", data={
        "amount": "15.00",
        "category": "Food",
        "date": "2026-06-01",
        "description": "Lunch",
    })
    conn = db_module.get_db()
    row = conn.execute("SELECT * FROM expenses").fetchone()
    conn.close()
    assert row is not None
    assert float(row["amount"]) == 15.00
    assert row["category"] == "Food"
    assert row["date"] == "2026-06-01"
    assert row["description"] == "Lunch"


def test_post_blank_description_stores_none(logged_in_client):
    logged_in_client.post("/expenses/add", data={
        "amount": "8.00",
        "category": "Transport",
        "date": "2026-06-01",
        "description": "   ",    # whitespace only → should store None
    })
    conn = db_module.get_db()
    row = conn.execute("SELECT description FROM expenses").fetchone()
    conn.close()
    assert row["description"] is None


def test_post_valid_expense_shows_flash_on_profile(logged_in_client):
    response = logged_in_client.post("/expenses/add", data={
        "amount": "15.00",
        "category": "Food",
        "date": "2026-06-01",
        "description": "",
    }, follow_redirects=True)
    assert b"Expense added" in response.data
