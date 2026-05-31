from flask import Flask, render_template, request, session, redirect, url_for, flash
import sqlite3
import datetime
import calendar
from database.db import get_db, init_db, seed_db, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_filtered_stats,
    get_filtered_transactions,
    get_filtered_breakdown,
)
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


def _compute_preset_dates(today):
    first_of_month = today.replace(day=1)
    last_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    m3, y3 = today.month - 2, today.year
    if m3 <= 0:
        m3 += 12
        y3 -= 1
    three_months_start = datetime.date(y3, m3, 1)

    m6, y6 = today.month - 5, today.year
    if m6 <= 0:
        m6 += 12
        y6 -= 1
    six_months_start = datetime.date(y6, m6, 1)

    return {
        "this_month":    (first_of_month.isoformat(), last_of_month.isoformat()),
        "last_3_months": (three_months_start.isoformat(), last_of_month.isoformat()),
        "last_6_months": (six_months_start.isoformat(), last_of_month.isoformat()),
    }


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = datetime.date.today()
    presets = _compute_preset_dates(today)

    raw_from = request.args.get("date_from", "")
    raw_to = request.args.get("date_to", "")

    date_from = None
    date_to = None

    if raw_from:
        try:
            datetime.datetime.strptime(raw_from, "%Y-%m-%d")
            date_from = raw_from
        except ValueError:
            pass

    if raw_to:
        try:
            datetime.datetime.strptime(raw_to, "%Y-%m-%d")
            date_to = raw_to
        except ValueError:
            pass

    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.")
        date_from = None
        date_to = None

    if date_from is None and date_to is None:
        active_preset = "all_time"
    elif (date_from, date_to) == presets["this_month"]:
        active_preset = "this_month"
    elif (date_from, date_to) == presets["last_3_months"]:
        active_preset = "last_3_months"
    elif (date_from, date_to) == presets["last_6_months"]:
        active_preset = "last_6_months"
    else:
        active_preset = "custom"

    user_data = get_user_by_id(session["user_id"])
    user = {
        **user_data,
        "initials": "".join(p[0].upper() for p in user_data["name"].split()[:2]),
    }

    return render_template(
        "profile.html",
        user=user,
        stats=get_filtered_stats(session["user_id"], date_from, date_to),
        expenses=get_filtered_transactions(session["user_id"], date_from, date_to),
        category_breakdown=get_filtered_breakdown(session["user_id"], date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        active_preset=active_preset,
        presets=presets,
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
