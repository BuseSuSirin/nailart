"""Tasarım galerisi: müşterilerin eski tırnak tasarımları ve fotoğrafları."""
import uuid
from datetime import date
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import UPLOAD_DIR, get_db
from helpers import FormError, clean, matches_search, safe_next, turkish_sort_key

bp = Blueprint("designs", __name__, url_prefix="/designs")

FIELDS = ["customer_id", "appointment_id", "date", "title", "shape", "length",
          "colors", "technique", "products", "notes", "favorite"]
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}

DESIGN_SELECT = "SELECT d.*, c.name AS customer_name FROM designs d JOIN customers c ON c.id = d.customer_id"


@bp.route("/")
def index():
    query = request.args.get("q", "")
    shape = request.args.get("shape", "")
    only_favorites = request.args.get("favorite") == "1"

    rows = get_db().execute(f"{DESIGN_SELECT} ORDER BY d.date DESC, d.id DESC").fetchall()
    designs = [
        d for d in rows
        if (not shape or d["shape"] == shape)
        and (not only_favorites or d["favorite"])
        and matches_search(query, d["title"], d["colors"], d["technique"], d["products"], d["notes"], d["customer_name"])
    ]
    return render_template("designs/list.html", designs=designs, total=len(rows),
                           query=query, shape=shape, only_favorites=only_favorites)


@bp.route("/<int:design_id>")
def detail(design_id):
    return render_template("designs/detail.html", design=get_design(design_id))


@bp.route("/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        return handle_form(None)
    form = {
        "customer_id": request.args.get("customer_id", type=int),
        "appointment_id": request.args.get("appointment_id", type=int),
        "date": request.args.get("date") or date.today().isoformat(),
    }
    return render_form(form)


@bp.route("/<int:design_id>/edit", methods=["GET", "POST"])
def edit(design_id):
    design = get_design(design_id)
    if request.method == "POST":
        return handle_form(design_id, old_photo=design["photo"])
    return render_form(dict(design), design_id=design_id)


@bp.post("/<int:design_id>/delete")
def delete(design_id):
    design = get_design(design_id)
    db = get_db()
    db.execute("DELETE FROM designs WHERE id = ?", (design_id,))
    db.commit()
    delete_photo(design["photo"])
    flash("Tasarım silindi.", "success")
    return redirect(url_for("customers.detail", customer_id=design["customer_id"]))


# ---------- fotoğraf dosyaları ----------

def save_photo(file):
    """Yüklenen fotoğrafı rastgele bir isimle data/uploads klasörüne kaydediyor."""
    if not file or not file.filename:
        return None
    extension = Path(file.filename).suffix.lower()
    if extension not in PHOTO_EXTENSIONS or not (file.mimetype or "").startswith("image/"):
        raise FormError("Sadece fotoğraf dosyası (jpg, png, webp…) yükleyebilirsiniz.")
    filename = f"{uuid.uuid4().hex}{extension}"
    file.save(UPLOAD_DIR / filename)
    return filename


def delete_photo(filename):
    if filename:
        (UPLOAD_DIR / Path(filename).name).unlink(missing_ok=True)


# ---------- yardımcı fonksiyonlar ----------

def get_design(design_id):
    row = get_db().execute(f"{DESIGN_SELECT} WHERE d.id = ?", (design_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def render_form(form, design_id=None, error=None):
    db = get_db()
    customers = sorted(db.execute("SELECT id, name FROM customers").fetchall(),
                       key=lambda c: turkish_sort_key(c["name"]))
    # Tasarımın bağlanabileceği randevular: müşteri seçildiyse onun randevuları
    appointments = []
    if form.get("customer_id"):
        appointments = db.execute("""
            SELECT a.id, a.start_at,
              (SELECT group_concat(s.name, ', ') FROM appointment_services x
                 JOIN services s ON s.id = x.service_id WHERE x.appointment_id = a.id) AS service_names
            FROM appointments a
            WHERE a.customer_id = ? AND a.status != 'cancelled'
            ORDER BY a.start_at DESC
        """, (form["customer_id"],)).fetchall()
    return render_template("designs/form.html", form=form, design_id=design_id, customers=customers,
                           appointments=appointments, error=error,
                           next_url=safe_next(request.values.get("next"), ""))


def handle_form(design_id, old_photo=None):
    form = dict(request.form)
    form["customer_id"] = request.form.get("customer_id", type=int)
    form["appointment_id"] = request.form.get("appointment_id", type=int)
    form["favorite"] = 1 if request.form.get("favorite") else 0
    form["photo"] = old_photo
    try:
        if not form["customer_id"]:
            raise FormError("Lütfen bir müşteri seçin.")
        check_appointment_belongs(form["appointment_id"], form["customer_id"])
        new_photo = save_photo(request.files.get("photo"))
    except FormError as e:
        return render_form(form, design_id, error=str(e))

    photo = new_photo or (None if request.form.get("remove_photo") else old_photo)
    values = [form["customer_id"], form["appointment_id"], form.get("date") or date.today().isoformat(),
              *[clean(form.get(f)) for f in ["title", "shape", "length", "colors", "technique", "products", "notes"]],
              form["favorite"], photo]

    db = get_db()
    if design_id:
        db.execute(f"UPDATE designs SET {', '.join(f + ' = ?' for f in FIELDS)}, photo = ? WHERE id = ?",
                   values + [design_id])
    else:
        design_id = db.execute(f"INSERT INTO designs ({', '.join(FIELDS)}, photo) "
                               f"VALUES ({', '.join('?' * (len(FIELDS) + 1))})", values).lastrowid
    db.commit()
    if photo != old_photo:
        delete_photo(old_photo)   # eski fotoğraf değişti ya da kaldırıldı

    flash("Tasarım kaydedildi.", "success")
    return redirect(safe_next(request.form.get("next"), url_for("designs.detail", design_id=design_id)))


def check_appointment_belongs(appointment_id, customer_id):
    if not appointment_id:
        return
    row = get_db().execute("SELECT customer_id FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if row is None or row["customer_id"] != customer_id:
        raise FormError("Seçilen randevu bu müşteriye ait değil. Müşteriyi değiştirdiyseniz randevuyu boş bırakın.")
