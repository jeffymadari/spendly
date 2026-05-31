from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import datetime
import calendar
from database.db import get_db, init_db, seed_db, get_user_by_email, get_user_by_id, get_expenses_for_user
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
    m, y = today.month - 2, today.year
    if m <= 0:
        m += 12
        y -= 1
    three_months_start = datetime.date(y, m, 1)
    return {
        "this_month":    (first_of_month.isoformat(), last_of_month.isoformat()),
        "last_3_months": (three_months_start.isoformat(), last_of_month.isoformat()),
        "all_time":      ("0001-01-01", "9999-12-31"),
    }


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = datetime.date.today()
    presets = _compute_preset_dates(today)

    from_date = request.args.get("from_date", presets["this_month"][0])
    to_date   = request.args.get("to_date",   presets["this_month"][1])

    current = (from_date, to_date)
    if current == presets["this_month"]:
        active_preset = "this_month"
    elif current == presets["last_3_months"]:
        active_preset = "last_3_months"
    elif current == presets["all_time"]:
        active_preset = "all_time"
    else:
        active_preset = "custom"

    user_row = get_user_by_id(session["user_id"])
    created_at = datetime.datetime.fromisoformat(user_row["created_at"])
    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "member_since": created_at.strftime("%B %Y"),
        "initials": "".join(p[0].upper() for p in user_row["name"].split()[:2]),
    }

    expenses = get_expenses_for_user(session["user_id"], from_date, to_date)

    total_spent = sum(e["amount"] for e in expenses)
    transaction_count = len(expenses)
    category_totals: dict = {}
    for e in expenses:
        category_totals[e["category"]] = category_totals.get(e["category"], 0) + e["amount"]
    top_category = max(category_totals, key=category_totals.get) if category_totals else "—"

    stats = {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category,
    }

    total_for_pct = total_spent or 1
    category_breakdown = sorted(
        [
            {"name": cat, "amount": amt, "pct": round(amt / total_for_pct * 100)}
            for cat, amt in category_totals.items()
        ],
        key=lambda x: x["amount"],
        reverse=True,
    )

    for e in expenses:
        e["date"] = datetime.date.fromisoformat(e["date"]).strftime("%b %d, %Y")

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        expenses=expenses,
        category_breakdown=category_breakdown,
        from_date=from_date,
        to_date=to_date,
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
