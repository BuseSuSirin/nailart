"""Panel (ana sayfa): bugünün özeti ve müşterilerle ilgili hatırlatmalar."""
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template

from database import APPOINTMENT_SELECT, get_db
from helpers import week_start

bp = Blueprint("dashboard", __name__)

# Son randevunun üstünden bu kadar gün geçince müşteri "bakım zamanı gelenler" listesine giriyor
REFILL_DAYS = int(os.environ.get("REFILL_DAYS", 21))


@bp.route("/")
def index():
    db = get_db()
    now = datetime.now()
    today = now.date()
    this_month = today.isoformat()[:7]          # "2026-11"
    monday = week_start(today)
    sunday = monday + timedelta(days=6)

    todays_appointments = db.execute(
        f"{APPOINTMENT_SELECT} WHERE date(a.start_at) = ? ORDER BY a.start_at",
        (today.isoformat(),),
    ).fetchall()

    stats = {
        "month_revenue": db.execute(
            "SELECT COALESCE(SUM(price), 0) FROM appointments "
            "WHERE status = 'completed' AND substr(start_at, 1, 7) = ?", (this_month,)).fetchone()[0],
        "week_appointments": db.execute(
            "SELECT COUNT(*) FROM appointments "
            "WHERE status IN ('planned', 'completed') AND date(start_at) BETWEEN ? AND ?",
            (monday.isoformat(), sunday.isoformat())).fetchone()[0],
        "customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "new_customers": db.execute(
            "SELECT COUNT(*) FROM customers WHERE substr(created_at, 1, 7) = ?", (this_month,)).fetchone()[0],
    }

    # Uzun süredir gelmeyen ve ileride randevusu olmayan müşteriler
    refill_due = db.execute("""
        SELECT c.id, c.name, c.phone, MAX(a.start_at) AS last_visit,
               CAST(julianday(?) - julianday(MAX(a.start_at)) AS INTEGER) AS days
        FROM customers c
        JOIN appointments a ON a.customer_id = c.id AND a.status = 'completed'
        WHERE NOT EXISTS (
            SELECT 1 FROM appointments f
            WHERE f.customer_id = c.id AND f.status = 'planned' AND f.start_at >= ?)
        GROUP BY c.id
        HAVING days >= ?
        ORDER BY days DESC
        LIMIT 12
    """, (today.isoformat(), now.strftime("%Y-%m-%dT%H:%M"), REFILL_DAYS)).fetchall()

    top_services = db.execute("""
        SELECT s.name, COUNT(*) AS times
        FROM appointment_services x
        JOIN services s ON s.id = x.service_id
        JOIN appointments a ON a.id = x.appointment_id
        WHERE a.status = 'completed' AND substr(a.start_at, 1, 7) = ?
        GROUP BY s.id ORDER BY times DESC LIMIT 5
    """, (this_month,)).fetchall()

    return render_template(
        "dashboard.html",
        todays_appointments=todays_appointments,
        stats=stats,
        refill_due=refill_due,
        refill_days=REFILL_DAYS,
        birthdays=upcoming_birthdays(db, today),
        top_services=top_services,
    )


def upcoming_birthdays(db, today, within_days=30):
    """Önümüzdeki 30 gün içinde doğum günü olan müşteriler, en yakını en başta."""
    result = []
    rows = db.execute("SELECT id, name, phone, birthday FROM customers "
                      "WHERE birthday IS NOT NULL AND birthday != ''").fetchall()
    for customer in rows:
        try:
            born = date.fromisoformat(customer["birthday"])
        except ValueError:
            continue
        next_birthday = birthday_in_year(born, today.year)
        if next_birthday < today:
            next_birthday = birthday_in_year(born, today.year + 1)
        days_left = (next_birthday - today).days
        if days_left <= within_days:
            result.append({**dict(customer), "next": next_birthday.isoformat(), "in_days": days_left})
    return sorted(result, key=lambda c: c["in_days"])


def birthday_in_year(born, year):
    """29 Şubat doğumluların doğum günü, artık yıl değilse 28 Şubat'a alınıyor."""
    try:
        return born.replace(year=year)
    except ValueError:
        return born.replace(year=year, day=28)
