"""Randevular: haftalık takvim, randevu ekleme, düzenleme ve durum değiştirme."""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import APPOINTMENT_SELECT, get_db
from helpers import (STATUS_LABELS, FormError, clean, to_float, to_int, turkish_sort_key,
                     safe_next, week_start)

bp = Blueprint("appointments", __name__, url_prefix="/appointments")


@bp.route("/")
def week():
    """Seçilen haftanın günlerini ve o günlerdeki randevuları gösteriyor."""
    try:
        start = week_start(date.fromisoformat(request.args["week"]))
    except (KeyError, ValueError):
        start = week_start(date.today())
    end = start + timedelta(days=6)

    rows = get_db().execute(
        f"{APPOINTMENT_SELECT} WHERE date(a.start_at) BETWEEN ? AND ? ORDER BY a.start_at",
        (start.isoformat(), end.isoformat()),
    ).fetchall()

    days = []
    for i in range(7):
        day = (start + timedelta(days=i)).isoformat()
        days.append({"date": day, "appointments": [a for a in rows if a["start_at"].startswith(day)]})

    return render_template(
        "appointments/week.html",
        days=days,
        start=start.isoformat(),
        end=end.isoformat(),
        previous_week=(start - timedelta(days=7)).isoformat(),
        next_week=(start + timedelta(days=7)).isoformat(),
        count=sum(1 for a in rows if a["status"] != "cancelled"),
        revenue=sum(a["price"] for a in rows if a["status"] == "completed"),
    )


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        return handle_form(None)
    form = {
        "customer_id": request.args.get("customer_id", type=int),
        "date": request.args.get("date") or date.today().isoformat(),
        "time": "10:00",
        "service_ids": [],
        "duration_min": "",
        "price": "",
        "status": "planned",
        "notes": request.args.get("notes", ""),
    }
    return render_form(form)


@bp.route("/<int:appointment_id>/edit", methods=["GET", "POST"])
def edit(appointment_id):
    appointment = get_appointment(appointment_id)
    if request.method == "POST":
        return handle_form(appointment_id)
    form = {
        "customer_id": appointment["customer_id"],
        "date": appointment["start_at"][:10],
        "time": appointment["start_at"][11:16],
        "service_ids": get_service_ids(appointment_id),
        "duration_min": appointment["duration_min"],
        "price": f"{appointment['price']:g}",
        "status": appointment["status"],
        "notes": appointment["notes"] or "",
    }
    return render_form(form, appointment_id=appointment_id)


@bp.post("/<int:appointment_id>/status")
def change_status(appointment_id):
    appointment = get_appointment(appointment_id)
    status = request.form.get("status")
    if status not in STATUS_LABELS:
        abort(400)
    db = get_db()
    db.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
    db.commit()
    back = safe_next(request.form.get("next"), url_for("dashboard.index"))

    if status == "completed":
        # Randevu bitince tasarımı kaydetmek için tasarım formuna gidiyoruz
        flash("Randevu tamamlandı ✓ İstersen bu seferki tasarımı kaydedebilirsin.", "success")
        return redirect(url_for("designs.new", customer_id=appointment["customer_id"],
                                appointment_id=appointment_id, date=appointment["start_at"][:10],
                                next=back))
    flash(f"Randevu durumu: {STATUS_LABELS[status]}", "success")
    return redirect(back)


@bp.post("/<int:appointment_id>/delete")
def delete(appointment_id):
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    db.commit()
    flash("Randevu silindi.", "success")
    return redirect(safe_next(request.form.get("next"), url_for("appointments.week")))


# ---------- yardımcı fonksiyonlar ----------

def get_appointment(appointment_id):
    row = get_db().execute(f"{APPOINTMENT_SELECT} WHERE a.id = ?", (appointment_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def get_service_ids(appointment_id):
    rows = get_db().execute(
        "SELECT service_id FROM appointment_services WHERE appointment_id = ?", (appointment_id,))
    return [r["service_id"] for r in rows]


def render_form(form, appointment_id=None, error=None, conflict=False):
    db = get_db()
    customers = sorted(db.execute("SELECT id, name, phone FROM customers").fetchall(),
                       key=lambda c: turkish_sort_key(c["name"]))
    # Pasif hizmetleri sadece bu randevuda zaten seçiliyse gösteriyoruz
    services = [s for s in db.execute("SELECT * FROM services ORDER BY category, name")
                if s["active"] or s["id"] in form["service_ids"]]
    return render_template(
        "appointments/form.html",
        form=form,
        appointment_id=appointment_id,
        customers=customers,
        services=services,
        error=error,
        conflict=conflict,
        next_url=safe_next(request.values.get("next"), ""),
    )


def handle_form(appointment_id):
    """Formu kaydediyor. Bir sorun varsa form hata mesajıyla tekrar açılıyor."""
    form = {
        "customer_id": request.form.get("customer_id", type=int),
        "date": request.form.get("date", ""),
        "time": request.form.get("time", ""),
        "service_ids": [int(x) for x in request.form.getlist("service_ids")],
        "duration_min": request.form.get("duration_min", "").strip(),
        "price": request.form.get("price", "").strip(),
        "status": request.form.get("status", "planned"),
        "notes": request.form.get("notes", ""),
    }
    try:
        save_appointment(appointment_id, form, force=bool(request.form.get("force")))
    except FormError as e:
        return render_form(form, appointment_id, error=str(e), conflict=e.conflict)

    flash("Randevu kaydedildi.", "success")
    # Hangi sayfadan gelindiyse oraya dönüyoruz, yoksa randevunun olduğu haftaya
    week_of_appointment = week_start(date.fromisoformat(form["date"])).isoformat()
    return redirect(safe_next(request.form.get("next"), url_for("appointments.week", week=week_of_appointment)))


def save_appointment(appointment_id, form, force=False):
    db = get_db()
    start_at = f"{form['date']}T{form['time']}"

    if not form["customer_id"]:
        raise FormError("Lütfen bir müşteri seçin.")
    try:
        datetime.strptime(start_at, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise FormError("Geçerli bir tarih ve saat girin.")
    if form["status"] not in STATUS_LABELS:
        raise FormError("Geçersiz durum.")

    # Süre ya da ücret boşsa seçilen hizmetlerin toplamını alıyoruz
    selected = []
    if form["service_ids"]:
        placeholders = ",".join("?" * len(form["service_ids"]))
        selected = db.execute(f"SELECT duration_min, price FROM services WHERE id IN ({placeholders})",
                              form["service_ids"]).fetchall()
    duration = to_int(form["duration_min"]) or sum(s["duration_min"] for s in selected) or 60
    price = to_float(form["price"])
    if price is None:
        price = sum(s["price"] for s in selected)

    if form["status"] in ("planned", "completed") and not force:
        other = find_conflict(appointment_id, start_at, duration)
        if other:
            raise FormError(f"Bu saat {other['name']} müşterisinin {other['start_at'][11:16]} "
                            "randevusuyla çakışıyor.", conflict=True)

    values = (form["customer_id"], start_at, duration, form["status"], price, clean(form["notes"]))
    if appointment_id:
        db.execute("UPDATE appointments SET customer_id = ?, start_at = ?, duration_min = ?, "
                   "status = ?, price = ?, notes = ? WHERE id = ?", (*values, appointment_id))
        db.execute("DELETE FROM appointment_services WHERE appointment_id = ?", (appointment_id,))
    else:
        cursor = db.execute("INSERT INTO appointments (customer_id, start_at, duration_min, status, price, notes) "
                            "VALUES (?, ?, ?, ?, ?, ?)", values)
        appointment_id = cursor.lastrowid
    db.executemany("INSERT INTO appointment_services (appointment_id, service_id) VALUES (?, ?)",
                   [(appointment_id, sid) for sid in set(form["service_ids"])])
    db.commit()
    return appointment_id


def find_conflict(appointment_id, start_at, duration):
    """Aynı saatte başka randevu var mı diye bakıyor. Salonda tek kişi çalıştığını düşündüm."""
    return get_db().execute("""
        SELECT a.start_at, c.name
        FROM appointments a JOIN customers c ON c.id = a.customer_id
        WHERE a.status IN ('planned', 'completed') AND a.id != ?
          AND datetime(a.start_at) < datetime(?, '+' || ? || ' minutes')
          AND datetime(a.start_at, '+' || a.duration_min || ' minutes') > datetime(?)
        LIMIT 1
    """, (appointment_id or 0, start_at, duration, start_at)).fetchone()
