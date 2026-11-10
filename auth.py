"""Giriş, çıkış, ilk şifre ve şifre değiştirme.

- Şifreyi düz metin olarak değil, hash'leyerek saklıyoruz. Hash'ten şifre geri bulunamıyor.
- Oturum bilgisi Flask'ın imzaladığı çerezde duruyor. Çerezle oynanırsa geçersiz oluyor.
- Şifre değişince "oturum sürümü" de değişiyor, böylece diğer cihazlardaki oturumlar kapanıyor.
"""
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_setting, set_setting

bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 5

# Hatalı denemeleri bellekte tutuyoruz. Örnek: {ip_adresi: {"count": 3, "locked_until": datetime}}
failed_attempts = {}


def get_or_create_secret_key():
    """Oturum çerezlerini imzalamak için gizli anahtar. İlk çalıştırmada rastgele oluşturuluyor."""
    key = get_setting("secret_key")
    if not key:
        key = secrets.token_hex(32)
        set_setting("secret_key", key)
    return key


def is_logged_in():
    return bool(session.get("logged_in")) and session.get("version") == get_setting("session_version")


def start_session():
    session.clear()
    session.permanent = True                       # 30 gün açık kalsın (süre app.py'de)
    session["logged_in"] = True
    session["version"] = get_setting("session_version")


def save_new_password(password):
    set_setting("password_hash", generate_password_hash(password))
    set_setting("session_version", secrets.token_hex(8))   # eski oturumlar artık geçmesin


def client_ip():
    """Ziyaretçinin IP adresi. Sunucuda bütün istekler Caddy'den geldiği için
    gerçek IP'yi Caddy'nin eklediği X-Real-IP başlığından alıyoruz."""
    if current_app.config["TRUST_PROXY"]:
        return request.headers.get("X-Real-IP", request.remote_addr)
    return request.remote_addr


def is_local_request():
    """İstek, uygulamanın çalıştığı bilgisayardan mı geliyor?

    Sunucuda (TRUST_PROXY açıkken) bütün istekler Caddy üzerinden geldiği için hepsi
    yerelmiş gibi görünüyor. Bu yüzden orada web'den şifre belirlemeyi kapattım,
    şifre set_password.py ile belirleniyor.
    """
    if current_app.config["TRUST_PROXY"]:
        return False
    return request.remote_addr in ("127.0.0.1", "::1")


def check_lock():
    """Bu IP çok fazla yanlış şifre girdiyse kaç dakika daha beklemesi gerektiğini döndürüyor."""
    entry = failed_attempts.get(client_ip())
    if entry and entry["locked_until"] and entry["locked_until"] > datetime.now():
        remaining = entry["locked_until"] - datetime.now()
        return int(remaining.total_seconds() // 60) + 1
    return None


def record_failure():
    entry = failed_attempts.setdefault(client_ip(), {"count": 0, "locked_until": None})
    entry["count"] += 1
    if entry["count"] >= MAX_FAILED_ATTEMPTS:
        entry["count"] = 0
        entry["locked_until"] = datetime.now() + timedelta(minutes=LOCK_MINUTES)


def validate_new_password(password, confirm):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalı."
    if password != confirm:
        return "Şifreler eşleşmiyor."
    return None


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """İlk açılışta şifre belirleme. Güvenlik için sadece uygulamanın çalıştığı bilgisayardan yapılabiliyor."""
    if get_setting("password_hash"):
        return redirect(url_for("auth.login"))
    allowed = is_local_request()
    error = None
    if request.method == "POST" and allowed:
        password = request.form.get("password", "")
        error = validate_new_password(password, request.form.get("confirm", ""))
        if not error:
            save_new_password(password)
            start_session()
            flash("Şifren kaydedildi. Hoş geldin! 💅", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("auth/setup.html", allowed=allowed, error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    password_hash = get_setting("password_hash")
    if not password_hash:
        return redirect(url_for("auth.setup"))
    if is_logged_in():
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        locked_minutes = check_lock()
        if locked_minutes:
            error = f"Çok fazla hatalı deneme. {locked_minutes} dakika sonra tekrar deneyin."
        elif check_password_hash(password_hash, request.form.get("password", "")):
            failed_attempts.pop(client_ip(), None)
            start_session()
            return redirect(url_for("dashboard.index"))
        else:
            record_failure()
            error = "Şifre hatalı."
    return render_template("auth/login.html", error=error)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=["GET", "POST"])
def change_password():
    error = None
    if request.method == "POST":
        locked_minutes = check_lock()
        if locked_minutes:
            error = f"Çok fazla hatalı deneme. {locked_minutes} dakika sonra tekrar deneyin."
        elif not check_password_hash(get_setting("password_hash"), request.form.get("current", "")):
            record_failure()
            error = "Mevcut şifre hatalı."
        else:
            new_password = request.form.get("new", "")
            error = validate_new_password(new_password, request.form.get("confirm", ""))
            if not error:
                save_new_password(new_password)
                start_session()   # bu cihaz açık kalsın, diğerleri kapansın
                flash("Şifre değiştirildi. Diğer cihazlardaki oturumlar kapatıldı.", "success")
                return redirect(url_for("dashboard.index"))
    return render_template("auth/password.html", error=error)
