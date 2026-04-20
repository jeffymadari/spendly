from urllib.parse import urlparse
import database.db as db_module


class TestGetUserByEmail:
    def test_returns_user_row_for_known_email(self, app, test_user):
        with app.app_context():
            user = db_module.get_user_by_email(test_user["email"])
        assert user is not None
        assert user["email"] == test_user["email"]
        assert user["name"] == test_user["name"]

    def test_returns_none_for_unknown_email(self, app):
        with app.app_context():
            user = db_module.get_user_by_email("nobody@example.com")
        assert user is None
