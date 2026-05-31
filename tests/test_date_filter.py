import pytest
import database.db as db_module
import database.queries as queries
from app import app as flask_app


class TestGetFilteredStats:
    def test_includes_expenses_in_range(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 50.00, "Bills", "2026-04-10", "In range")
            result = queries.get_filtered_stats(user["id"], "2026-04-01", "2026-04-30")
        assert result["total_spent"] == pytest.approx(50.00)
        assert result["transaction_count"] == 1
        assert result["top_category"] == "Bills"

    def test_excludes_expenses_outside_range(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 50.00, "Bills", "2026-03-15", "Out of range")
            result = queries.get_filtered_stats(user["id"], "2026-04-01", "2026-04-30")
        assert result == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

    def test_returns_zeros_when_no_expenses_in_range(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            result = queries.get_filtered_stats(user["id"], "2026-04-01", "2026-04-30")
        assert result == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


class TestGetFilteredTransactions:
    def test_returns_transactions_in_range_newest_first(
        self, app, test_user, insert_expense
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",  "2026-04-01", "Earlier")
            insert_expense(user["id"], 20.00, "Bills", "2026-04-15", "Later")
            result = queries.get_filtered_transactions(user["id"], "2026-04-01", "2026-04-30")
        assert len(result) == 2
        assert result[0]["description"] == "Later"
        assert result[1]["description"] == "Earlier"

    def test_excludes_transactions_outside_range(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-03-01", "Out of range")
            result = queries.get_filtered_transactions(user["id"], "2026-04-01", "2026-04-30")
        assert result == []

    def test_date_formatted_as_month_day_year(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-04-05", "Lunch")
            result = queries.get_filtered_transactions(user["id"], "2026-04-01", "2026-04-30")
        assert result[0]["date"] == "Apr 05, 2026"


class TestGetFilteredBreakdown:
    def test_returns_breakdown_for_range_only(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 80.00, "Bills", "2026-04-01", "In range")
            insert_expense(user["id"], 20.00, "Food",  "2026-03-01", "Out of range")
            result = queries.get_filtered_breakdown(user["id"], "2026-04-01", "2026-04-30")
        assert len(result) == 1
        assert result[0]["name"] == "Bills"

    def test_pct_values_sum_to_100(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",      "2026-04-01", "a")
            insert_expense(user["id"], 20.00, "Transport", "2026-04-02", "b")
            insert_expense(user["id"], 30.00, "Bills",     "2026-04-03", "c")
            result = queries.get_filtered_breakdown(user["id"], "2026-04-01", "2026-04-30")
        assert sum(item["pct"] for item in result) == 100

    def test_returns_empty_list_for_empty_range(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            result = queries.get_filtered_breakdown(user["id"], "2026-04-01", "2026-04-30")
        assert result == []


class TestProfileDateFilter:
    def test_default_shows_current_month_only(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 99.00, "Bills", "2024-01-15", "Ancient")
        response = logged_in_client.get("/profile")
        assert b"Ancient" not in response.data

    def test_custom_range_filters_correctly(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 25.00, "Food",      "2026-02-10", "Feb lunch")
            insert_expense(user["id"], 30.00, "Transport", "2026-03-20", "Mar bus")
        response = logged_in_client.get(
            "/profile?from_date=2026-02-01&to_date=2026-02-28"
        )
        assert b"Feb lunch" in response.data
        assert b"Mar bus" not in response.data

    def test_all_time_shows_all_expenses(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2010-01-01", "Very old")
        response = logged_in_client.get(
            "/profile?from_date=0001-01-01&to_date=9999-12-31"
        )
        assert b"Very old" in response.data

    def test_empty_range_shows_zero_stats(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?from_date=2020-01-01&to_date=2020-01-31"
        )
        assert "₹0.00".encode() in response.data

    def test_active_preset_class_in_html(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert b"filter-btn--active" in response.data


class TestFilteredHelpersWithNoneParams:
    def test_stats_with_none_returns_all(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",  "2020-01-01", "Old")
            insert_expense(user["id"], 20.00, "Bills", "2026-05-01", "New")
            result = queries.get_filtered_stats(user["id"], None, None)
        assert result["transaction_count"] == 2
        assert result["total_spent"] == pytest.approx(30.00)

    def test_transactions_with_none_returns_all(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",  "2020-01-01", "Old")
            insert_expense(user["id"], 20.00, "Bills", "2026-05-01", "New")
            result = queries.get_filtered_transactions(user["id"], None, None)
        assert len(result) == 2

    def test_breakdown_with_none_returns_all(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 50.00, "Food",  "2020-01-01", "Old")
            insert_expense(user["id"], 50.00, "Bills", "2026-05-01", "New")
            result = queries.get_filtered_breakdown(user["id"], None, None)
        assert len(result) == 2
