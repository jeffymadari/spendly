import datetime
from database.db import get_db


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


def get_summary_stats(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT amount, category FROM expenses WHERE user_id = ?",
            (user_id,),
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


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses"
            " WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        result.append({
            "date": datetime.date.fromisoformat(r["date"]).strftime("%b %d, %Y"),
            "description": r["description"],
            "category": r["category"],
            "amount": r["amount"],
        })
    return result


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses"
            " WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
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


def get_filtered_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            rows = conn.execute(
                "SELECT amount, category FROM expenses"
                " WHERE user_id = ? AND date BETWEEN ? AND ?",
                (user_id, date_from, date_to),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT amount, category FROM expenses WHERE user_id = ?",
                (user_id,),
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


def get_filtered_transactions(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses"
                " WHERE user_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC",
                (user_id, date_from, date_to),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses"
                " WHERE user_id = ? ORDER BY date DESC",
                (user_id,),
            ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        result.append({
            "date": datetime.date.fromisoformat(r["date"]).strftime("%b %d, %Y"),
            "description": r["description"],
            "category": r["category"],
            "amount": r["amount"],
        })
    return result


def get_filtered_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            rows = conn.execute(
                "SELECT category, SUM(amount) AS total FROM expenses"
                " WHERE user_id = ? AND date BETWEEN ? AND ?"
                " GROUP BY category ORDER BY total DESC",
                (user_id, date_from, date_to),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category, SUM(amount) AS total FROM expenses"
                " WHERE user_id = ? GROUP BY category ORDER BY total DESC",
                (user_id,),
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
    diff = 100 - sum(item["pct"] for item in result)
    if diff:
        result[0]["pct"] += diff
    return result
