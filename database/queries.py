import datetime
from database.db import get_db


def _date_filter_clause(date_from, date_to):
    """Returns (sql_fragment, params) for an optional BETWEEN filter."""
    if date_from is not None and date_to is not None:
        return "AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    created_at = datetime.datetime.fromisoformat(row["created_at"])
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created_at.strftime("%B %Y"),
    }


def get_summary_stats(user_id, date_from=None, date_to=None):
    clause, params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT amount, category FROM expenses WHERE user_id = ? {clause}",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    total_spent = sum(r["amount"] for r in rows)
    category_totals: dict = {}
    for r in rows:
        category_totals[r["category"]] = category_totals.get(r["category"], 0) + r["amount"]
    top_category = max(category_totals, key=category_totals.get)
    return {
        "total_spent": total_spent,
        "transaction_count": len(rows),
        "top_category": top_category,
    }


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    clause, params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT id, date, description, category, amount FROM expenses"
            f" WHERE user_id = ? {clause} ORDER BY date DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "date": datetime.date.fromisoformat(r["date"]).strftime("%b %d, %Y"),
            "description": r["description"],
            "category": r["category"],
            "amount": r["amount"],
        })
    return result


def get_expense_by_id(expense_id, user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, user_id, amount, category, date, description"
            " FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, date, description):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE expenses SET amount=?, category=?, date=?, description=?"
            " WHERE id=? AND user_id=?",
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    clause, params = _date_filter_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT category, SUM(amount) AS total FROM expenses"
            f" WHERE user_id = ? {clause} GROUP BY category ORDER BY total DESC",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    grand_total = sum(r["total"] for r in rows)
    result = [
        {
            "name": r["category"],
            "amount": r["total"],
            "pct": round(r["total"] / grand_total * 100),
        }
        for r in rows
    ]
    # Absorb integer-rounding remainder into the largest category
    diff = 100 - sum(item["pct"] for item in result)
    if diff:
        result[0]["pct"] += diff
    return result
