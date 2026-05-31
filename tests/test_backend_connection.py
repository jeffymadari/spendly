import pytest
from werkzeug.security import generate_password_hash
import database.db as db_module
import database.queries as queries


# ------------------------------------------------------------------ #
# get_user_by_id                                                       #
# ------------------------------------------------------------------ #

class TestGetUserById:
    def test_returns_dict_with_name_email_member_since(self, app, test_user):
        with app.app_context():
            row = db_module.get_user_by_email(test_user["email"])
            result = queries.get_user_by_id(row["id"])
        assert result is not None
        assert result["name"] == test_user["name"]
        assert result["email"] == test_user["email"]
        assert "member_since" in result

    def test_member_since_formatted_as_month_year(self, app, test_user):
        import re
        with app.app_context():
            row = db_module.get_user_by_email(test_user["email"])
            result = queries.get_user_by_id(row["id"])
        # Expect "Month YYYY" e.g. "May 2026"
        assert re.match(r"^[A-Z][a-z]+ \d{4}$", result["member_since"])

    def test_returns_none_for_unknown_id(self, app):
        with app.app_context():
            result = queries.get_user_by_id(9999)
        assert result is None


# ------------------------------------------------------------------ #
# get_summary_stats                                                    #
# ------------------------------------------------------------------ #

class TestGetSummaryStats:
    def test_returns_correct_stats_for_user_with_expenses(
        self, app, test_user, insert_expense
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 40.00, "Food",  "2026-04-01", "Lunch")
            insert_expense(user["id"], 30.00, "Bills", "2026-04-02", "Internet")
            insert_expense(user["id"], 25.00, "Bills", "2026-04-03", "Water bill")
            result = queries.get_summary_stats(user["id"])
        assert result["total_spent"] == pytest.approx(95.00)
        assert result["transaction_count"] == 3
        assert result["top_category"] == "Bills"

    def test_returns_zeros_for_user_with_no_expenses(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            result = queries.get_summary_stats(user["id"])
        assert result == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }


# ------------------------------------------------------------------ #
# get_recent_transactions                                              #
# ------------------------------------------------------------------ #

class TestGetRecentTransactions:
    def test_returns_list_newest_first(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",  "2026-04-01", "Earlier")
            insert_expense(user["id"], 20.00, "Bills", "2026-04-15", "Later")
            result = queries.get_recent_transactions(user["id"])
        assert result[0]["description"] == "Later"
        assert result[1]["description"] == "Earlier"

    def test_each_item_has_required_keys(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-04-01", "Lunch")
            result = queries.get_recent_transactions(user["id"])
        item = result[0]
        assert set(item.keys()) >= {"date", "description", "category", "amount"}

    def test_date_formatted_as_month_day_year(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-04-01", "Lunch")
            result = queries.get_recent_transactions(user["id"])
        assert result[0]["date"] == "Apr 01, 2026"

    def test_respects_limit_parameter(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            for i in range(15):
                insert_expense(user["id"], 5.00, "Food", f"2026-04-{i+1:02d}", f"Item {i}")
            result = queries.get_recent_transactions(user["id"], limit=5)
        assert len(result) == 5

    def test_returns_empty_list_for_user_with_no_expenses(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            result = queries.get_recent_transactions(user["id"])
        assert result == []


# ------------------------------------------------------------------ #
# get_category_breakdown                                               #
# ------------------------------------------------------------------ #

class TestGetCategoryBreakdown:
    def test_returns_list_ordered_by_amount_desc(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",  "2026-04-01", "Cheap")
            insert_expense(user["id"], 90.00, "Bills", "2026-04-02", "Expensive")
            result = queries.get_category_breakdown(user["id"])
        assert result[0]["name"] == "Bills"
        assert result[1]["name"] == "Food"

    def test_pct_values_sum_to_100(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food",      "2026-04-01", "a")
            insert_expense(user["id"], 20.00, "Transport", "2026-04-02", "b")
            insert_expense(user["id"], 30.00, "Bills",     "2026-04-03", "c")
            result = queries.get_category_breakdown(user["id"])
        assert sum(item["pct"] for item in result) == 100

    def test_each_item_has_name_amount_pct(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 50.00, "Food", "2026-04-01", "a")
            result = queries.get_category_breakdown(user["id"])
        assert set(result[0].keys()) >= {"name", "amount", "pct"}

    def test_returns_empty_list_for_user_with_no_expenses(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            result = queries.get_category_breakdown(user["id"])
        assert result == []


# ------------------------------------------------------------------ #
# /profile route integration                                           #
# ------------------------------------------------------------------ #

class TestProfileRouteBackendConnection:
    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_authenticated_returns_200(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200

    def test_shows_real_user_name(self, logged_in_client, test_user):
        response = logged_in_client.get("/profile")
        assert test_user["name"].encode() in response.data

    def test_shows_real_user_email(self, logged_in_client, test_user):
        response = logged_in_client.get("/profile")
        assert test_user["email"].encode() in response.data

    def test_shows_rupee_symbol(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert "₹".encode() in response.data

    def test_shows_zero_total_for_new_user(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert "₹0.00".encode() in response.data

    def test_stats_reflect_real_expenses(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 50.00, "Bills", "2026-04-01", "Internet")
            insert_expense(user["id"], 30.00, "Food",  "2026-04-02", "Lunch")
        response = logged_in_client.get("/profile")
        assert "₹80.00".encode() in response.data
        assert b"Bills" in response.data

    def test_empty_state_no_crash(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert response.status_code == 200
        assert b"0" in response.data
