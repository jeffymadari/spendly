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
