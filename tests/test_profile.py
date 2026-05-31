import database.db as db_module


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
