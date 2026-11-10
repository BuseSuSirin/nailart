"""Müşteriler: liste, profil sayfası, ekleme, düzenleme ve silme."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import APPOINTMENT_SELECT, get_db
from helpers import clean, matches_search, turkish_sort_key
from designs import delete_photo

bp = Blueprint("customers", __name__, url_prefix="/customers")

FIELDS = ["name", "phone", "email", "instagram", "birthday", "nail_notes", "preferences", "notes"]


@bp.route("/")
def index():
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    rows = get_db().execute("""
        SELECT c.*,
          (SELECT COUNT(*) FROM appointments a
            WHERE a.customer_id = c.id AND a.status = 'completed') AS visits,
          (SELECT COALESCE(SUM(price), 0) FROM appointments a
            WHERE a.customer_id = c.id AND a.status = 'completed') AS total_spent,
          (SELECT MAX(start_at) FROM appointments a
            WHERE a.customer_id = c.id AND a.status = 'completed') AS last_visit,
          (SELECT MIN(start_at) FROM appointments a
            WHERE a.customer_id = c.id AND a.status = 'planned' AND a.start_at >= ?) AS next_appointment
        FROM customers c
    """, (now,)).fetchall()

    query = request.args.get("q", "")
    customers = [c for c in rows if matches_search(query, c["name"], c["phone"], c["instagram"], c["email"])]
    customers.sort(key=lambda c: turkish_sort_key(c["name"]))
    return render_template("customers/list.html", customers=customers, query=query, total=len(rows))


@bp.route("/<int:customer_id>")
def detail(customer_id):
    db = get_db()
    customer = get_customer(customer_id)
    appointments = db.execute(f"{APPOINTMENT_SELECT} WHERE a.customer_id = ? ORDER BY a.start_at DESC",
                              (customer_id,)).fetchall()
    designs = db.execute("SELECT * FROM designs WHERE customer_id = ? ORDER BY date DESC, id DESC",
                         (customer_id,)).fetchall()
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    upcoming = [a for a in reversed(appointments) if a["status"] == "planned" and a["start_at"] >= now[:10]]

    return render_template(
        "customers/detail.html",
        customer=customer,
        appointments=appointments,
        designs=designs,
        upcoming=upcoming,
        stats=calculate_stats(appointments),
        tab=request.args.get("tab", "designs"),
    )


def calculate_stats(appointments):
    """Müşterinin istatistikleri: kaç kez geldi, ne kadar harcadı, ne sıklıkla geliyor."""
    completed = sorted((a for a in appointments if a["status"] == "completed"), key=lambda a: a["start_at"])

    average_interval = None
    if len(completed) > 1:
        first = datetime.fromisoformat(completed[0]["start_at"])
        last = datetime.fromisoformat(completed[-1]["start_at"])
        average_interval = round((last - first).days / (len(completed) - 1))

    # En sık alınan hizmetler
    service_counts = {}
    for a in completed:
        for name in (a["service_names"] or "").split(", "):
            if name:
                service_counts[name] = service_counts.get(name, 0) + 1
    favorites = sorted(service_counts.items(), key=lambda item: item[1], reverse=True)[:3]

    total = sum(a["price"] for a in completed)
    return {
        "visits": len(completed),
        "total_spent": total,
        "average_spent": total / len(completed) if completed else 0,
        "last_visit": completed[-1]["start_at"] if completed else None,
        "average_interval": average_interval,
        "no_shows": sum(1 for a in appointments if a["status"] == "no_show"),
        "cancellations": sum(1 for a in appointments if a["status"] == "cancelled"),
        "favorite_services": favorites,
    }


@bp.route("/new", methods=["GET", "POST"])
def new():
    form = dict(request.form) if request.method == "POST" else {}
    if request.method == "POST":
        error = validate(form)
        if not error:
            db = get_db()
            cursor = db.execute(
                f"INSERT INTO customers ({', '.join(FIELDS)}) VALUES ({', '.join('?' * len(FIELDS))})",
                [clean(form.get(f)) for f in FIELDS])
            db.commit()
            flash("Müşteri kaydedildi.", "success")
            return redirect(url_for("customers.detail", customer_id=cursor.lastrowid))
        return render_template("customers/form.html", form=form, customer_id=None, error=error)
    return render_template("customers/form.html", form=form, customer_id=None, error=None)


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
def edit(customer_id):
    customer = get_customer(customer_id)
    if request.method == "POST":
        form = dict(request.form)
        error = validate(form)
        if not error:
            db = get_db()
            db.execute(f"UPDATE customers SET {', '.join(f + ' = ?' for f in FIELDS)} WHERE id = ?",
                       [clean(form.get(f)) for f in FIELDS] + [customer_id])
            db.commit()
            flash("Müşteri bilgileri güncellendi.", "success")
            return redirect(url_for("customers.detail", customer_id=customer_id))
        return render_template("customers/form.html", form=form, customer_id=customer_id, error=error)
    return render_template("customers/form.html", form=dict(customer), customer_id=customer_id, error=None)


@bp.post("/<int:customer_id>/delete")
def delete(customer_id):
    """Müşteriyi siliyor. Randevularını ve tasarımlarını veritabanı kendisi siliyor (ON DELETE CASCADE)."""
    db = get_db()
    photos = [r["photo"] for r in db.execute("SELECT photo FROM designs WHERE customer_id = ?", (customer_id,))]
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    db.commit()
    for photo in photos:
        delete_photo(photo)
    flash("Müşteri ve tüm geçmişi silindi.", "success")
    return redirect(url_for("customers.index"))


def get_customer(customer_id):
    row = get_db().execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def validate(form):
    if not (form.get("name") or "").strip():
        return "Müşteri adı zorunlu."
    return None
