from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
from database.db import get_db, init_db, seed_db, get_user_by_email
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name:
        return render_template("register.html", error="Name is required.", name=name, email=email)
    if not email or "@" not in email:
        return render_template("register.html", error="A valid email address is required.", name=name, email=email)
    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.", name=name, email=email)
    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.", name=name, email=email)

    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        session["user_id"] = cursor.lastrowid
        session["user_name"] = name
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.", name=name, email=email)
    finally:
        conn.close()

    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.", email=email)

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Alex Rivera",
        "email": "alex@example.com",
        "member_since": "January 2025",
        "initials": "AR",
    }

    stats = {
        "total_spent": 268.63,
        "transaction_count": 8,
        "top_category": "Bills",
    }

    expenses = [
        {"date": "Apr 13, 2026", "description": "Miscellaneous",         "category": "Other",         "amount": 20.00},
        {"date": "Apr 11, 2026", "description": "Groceries",             "category": "Food",          "amount": 8.75},
        {"date": "Apr 09, 2026", "description": "Clothing",              "category": "Shopping",      "amount": 62.40},
        {"date": "Apr 07, 2026", "description": "Streaming subscription","category": "Entertainment", "amount": 14.99},
        {"date": "Apr 05, 2026", "description": "Pharmacy",              "category": "Health",        "amount": 25.00},
        {"date": "Apr 03, 2026", "description": "Internet bill",         "category": "Bills",         "amount": 89.99},
        {"date": "Apr 02, 2026", "description": "Monthly bus pass",      "category": "Transport",     "amount": 35.00},
        {"date": "Apr 01, 2026", "description": "Lunch at cafe",         "category": "Food",          "amount": 12.50},
    ]

    category_breakdown = [
        {"name": "Bills",         "amount": 89.99, "pct": 33},
        {"name": "Shopping",      "amount": 62.40, "pct": 23},
        {"name": "Transport",     "amount": 35.00, "pct": 13},
        {"name": "Health",        "amount": 25.00, "pct":  9},
        {"name": "Food",          "amount": 21.25, "pct":  8},
        {"name": "Entertainment", "amount": 14.99, "pct":  6},
        {"name": "Other",         "amount": 20.00, "pct":  7},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        expenses=expenses,
        category_breakdown=category_breakdown,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


@app.route("/dashboard")
def dashboard():
    return "Dashboard — coming in Step 3"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
