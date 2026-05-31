import database.db as db_module
from app import app as flask_app


class TestGetUserById:
    def test_returns_user_for_known_id(self, app, test_user):
        with app.app_context():
            existing = db_module.get_user_by_email(test_user["email"])
            result = db_module.get_user_by_id(existing["id"])
        assert result is not None
        assert result["name"] == test_user["name"]

    def test_returns_none_for_unknown_id(self, app):
        with app.app_context():
            result = db_module.get_user_by_id(9999)
        assert result is None


class TestGetExpensesForUser:
    def test_returns_expenses_within_date_range(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-04-15", "Lunch")
            rows = db_module.get_expenses_for_user(user["id"], "2026-04-01", "2026-04-30")
        assert len(rows) == 1
        assert rows[0]["description"] == "Lunch"

    def test_excludes_expenses_outside_date_range(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2026-03-01", "Old expense")
            rows = db_module.get_expenses_for_user(user["id"], "2026-04-01", "2026-04-30")
        assert len(rows) == 0

    def test_returns_empty_list_when_no_expenses(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            rows = db_module.get_expenses_for_user(user["id"], "2026-04-01", "2026-04-30")
        assert rows == []

    def test_ordered_by_date_descending(self, app, test_user, insert_expense):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 5.00, "Food", "2026-04-01", "Earlier")
            insert_expense(user["id"], 5.00, "Food", "2026-04-15", "Later")
            rows = db_module.get_expenses_for_user(user["id"], "2026-04-01", "2026-04-30")
        assert rows[0]["description"] == "Later"
        assert rows[1]["description"] == "Earlier"

    def test_does_not_return_other_users_expenses(self, app, test_user, insert_expense):
        with app.app_context():
            # Create a second user directly — no fixture for multi-user scenarios
            conn = db_module.get_db()
            try:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ("Other", "other@example.com", "hash"),
                )
                conn.commit()
                other = conn.execute(
                    "SELECT id FROM users WHERE email = ?", ("other@example.com",)
                ).fetchone()
                other_id = other["id"]
            finally:
                conn.close()
            insert_expense(other_id, 50.00, "Bills", "2026-04-10", "Not mine")
            user = db_module.get_user_by_email(test_user["email"])
            rows = db_module.get_expenses_for_user(user["id"], "2026-04-01", "2026-04-30")
        assert len(rows) == 0


class TestProfileRoute:
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

    def test_default_excludes_old_expense(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 99.00, "Bills", "2024-01-15", "Ancient bill")
        response = logged_in_client.get("/profile")
        assert b"Ancient bill" not in response.data

    def test_custom_date_range_filters_expenses(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 25.00, "Food", "2026-02-10", "Feb lunch")
            insert_expense(user["id"], 30.00, "Transport", "2026-03-20", "Mar bus")
        response = logged_in_client.get(
            "/profile?from_date=2026-02-01&to_date=2026-02-28"
        )
        assert b"Feb lunch" in response.data
        assert b"Mar bus" not in response.data

    def test_empty_range_shows_zero_total(self, logged_in_client):
        response = logged_in_client.get(
            "/profile?from_date=2020-01-01&to_date=2020-01-31"
        )
        assert b"$0.00" in response.data

    def test_all_time_shows_old_expense(
        self, logged_in_client, test_user, insert_expense, app
    ):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
            insert_expense(user["id"], 10.00, "Food", "2010-06-01", "Very old")
        response = logged_in_client.get(
            "/profile?from_date=0001-01-01&to_date=9999-12-31"
        )
        assert b"Very old" in response.data

    def test_active_preset_class_present(self, logged_in_client):
        response = logged_in_client.get("/profile")
        assert b"filter-btn--active" in response.data
