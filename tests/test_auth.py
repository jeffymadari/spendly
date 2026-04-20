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


class TestLoginPost:
    def test_valid_credentials_set_session_and_redirect_to_landing(self, client, test_user):
        response = client.post("/login", data={
            "email": test_user["email"],
            "password": test_user["password"],
        })
        assert response.status_code == 302
        assert urlparse(response.location).path == "/"
        with client.session_transaction() as sess:
            assert sess["user_id"] is not None

    def test_wrong_password_shows_generic_error(self, client, test_user):
        response = client.post("/login", data={
            "email": test_user["email"],
            "password": "wrongpassword",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid email or password." in response.data

    def test_wrong_password_does_not_set_session(self, client, test_user):
        client.post("/login", data={
            "email": test_user["email"],
            "password": "wrongpassword",
        })
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_unknown_email_shows_generic_error(self, client):
        response = client.post("/login", data={
            "email": "nobody@example.com",
            "password": "anypassword",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid email or password." in response.data

    def test_error_repopulates_email_field(self, client, test_user):
        response = client.post("/login", data={
            "email": test_user["email"],
            "password": "wrongpassword",
        }, follow_redirects=True)
        assert test_user["email"].encode() in response.data


class TestLogout:
    def _login(self, client, test_user):
        client.post("/login", data={
            "email": test_user["email"],
            "password": test_user["password"],
        })

    def test_logout_redirects_to_landing(self, client, test_user):
        self._login(client, test_user)
        response = client.get("/logout")
        assert response.status_code == 302
        assert urlparse(response.location).path == "/"

    def test_logout_clears_user_id_from_session(self, client, test_user):
        self._login(client, test_user)
        with client.session_transaction() as sess:
            assert "user_id" in sess

        client.get("/logout")

        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_without_prior_login_still_redirects(self, client):
        response = client.get("/logout")
        assert response.status_code == 302
        assert urlparse(response.location).path == "/"
