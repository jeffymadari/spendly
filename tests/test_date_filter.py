import pytest
import database.db as db_module
import database.queries as queries


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
