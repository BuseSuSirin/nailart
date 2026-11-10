"""Hizmetler: salonun fiyat listesi ve işlem süreleri."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import get_db
from helpers import clean, to_float, to_int

bp = Blueprint("services", __name__, url_prefix="/services")


@bp.route("/")
def index():
    rows = get_db().execute("""
        SELECT s.*, (SELECT COUNT(*) FROM appointment_services x WHERE x.service_id = s.id) AS usage
        FROM services s ORDER BY s.category, s.name
    """).fetchall()
    # Kategoriye göre grupla: {"Bakım": [...], "Protez": [...]}
    groups = {}
    for service in rows:
        groups.setdefault(service["category"] or "Diğer", []).append(service)
    return render_template("services/list.html", groups=groups)


@bp.route("/new", methods=["GET", "POST"])
def new():
    return handle_form(None, {"duration_min": 60, "price": 0, "active": 1})


@bp.route("/<int:service_id>/edit", methods=["GET", "POST"])
def edit(service_id):
    service = get_db().execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if service is None:
        abort(404)
    return handle_form(service_id, dict(service))


@bp.post("/<int:service_id>/delete")
def delete(service_id):
    """Eski randevularda kullanılan hizmet silinmiyor, pasif yapılıyor (yoksa eski kayıtlar bozulur)."""
    db = get_db()
    used = db.execute("SELECT COUNT(*) FROM appointment_services WHERE service_id = ?", (service_id,)).fetchone()[0]
    if used:
        db.execute("UPDATE services SET active = 0 WHERE id = ?", (service_id,))
        flash("Bu hizmet geçmiş randevularda kullanıldığı için silinmedi, pasife alındı.", "success")
    else:
        db.execute("DELETE FROM services WHERE id = ?", (service_id,))
        flash("Hizmet silindi.", "success")
    db.commit()
    return redirect(url_for("services.index"))


def handle_form(service_id, form):
    db = get_db()
    error = None
    if request.method == "POST":
        form = {
            "name": request.form.get("name", ""),
            "category": request.form.get("category", ""),
            "duration_min": request.form.get("duration_min", ""),
            "price": request.form.get("price", ""),
            "active": 1 if request.form.get("active") else 0,
        }
        duration = to_int(form["duration_min"])
        price = to_float(form["price"])
        if not form["name"].strip():
            error = "Hizmet adı zorunlu."
        elif not duration or duration < 5:
            error = "Süre en az 5 dakika olmalı."
        elif price is None or price < 0:
            error = "Geçerli bir fiyat girin."
        else:
            values = (form["name"].strip(), clean(form["category"]), duration, price, form["active"])
            if service_id:
                db.execute("UPDATE services SET name = ?, category = ?, duration_min = ?, price = ?, active = ? "
                           "WHERE id = ?", (*values, service_id))
            else:
                db.execute("INSERT INTO services (name, category, duration_min, price, active) "
                           "VALUES (?, ?, ?, ?, ?)", values)
            db.commit()
            flash("Hizmet kaydedildi.", "success")
            return redirect(url_for("services.index"))

    categories = [r[0] for r in db.execute("SELECT DISTINCT category FROM services WHERE category IS NOT NULL")]
    return render_template("services/form.html", form=form, service_id=service_id,
                           categories=categories, error=error)
