"""Uygulama buradan başlıyor.

Çalıştırmak için: python app.py (sonra tarayıcıda http://localhost:3000)

Sayfaları konularına göre ayrı dosyalara böldüm (Flask'ta buna Blueprint deniyor):
    dashboard.py     - Panel (ana sayfa)
    appointments.py  - Randevular
    customers.py     - Müşteriler
    designs.py       - Tasarımlar
    services.py      - Hizmetler
    auth.py          - Giriş, çıkış, şifre
"""
import os
from datetime import timedelta

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

import appointments
import auth
import customers
import dashboard
import database
import designs
import helpers
import services

# Giriş yapmadan açılabilen sayfalar. Bunların dışındaki her şey (fotoğraflar da) şifre istiyor.
PUBLIC_PAGES = {"auth.login", "auth.setup", "static"}


def create_app():
    database.init_db()

    app = Flask(__name__)
    app.config.update(
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_HTTPONLY=True,      # tarayıcıdaki kodlar çereze erişemesin
        SESSION_COOKIE_SAMESITE="Lax",     # başka sitelerden gelen formlar oturumu kullanamasın
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # en fazla 10 MB fotoğraf
        # Sunucuda uygulama Caddy'nin arkasında HTTPS ile çalışıyor
        TRUST_PROXY=os.environ.get("TRUST_PROXY") == "1",
    )
    if app.config["TRUST_PROXY"]:
        app.config["SESSION_COOKIE_SECURE"] = True   # çerez sadece HTTPS ile gitsin
    with app.app_context():
        app.secret_key = auth.get_or_create_secret_key()
    app.teardown_appcontext(database.close_db)
    helpers.register_template_helpers(app)

    for module in (auth, dashboard, appointments, customers, designs, services):
        app.register_blueprint(module.bp)

    @app.before_request
    def require_login():
        """Her istekten önce çalışıyor. Giriş yapılmamışsa giriş sayfasına gönderiyor."""
        if request.endpoint not in PUBLIC_PAGES and not auth.is_logged_in():
            return redirect(url_for("auth.login"))
        return None

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(database.UPLOAD_DIR, filename)

    @app.errorhandler(413)
    def file_too_large(error):
        flash("Fotoğraf en fazla 10 MB olabilir.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))

    @app.errorhandler(404)
    def not_found(error):
        return render_template("not_found.html"), 404

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Nail Art CRM çalışıyor: http://localhost:{port}")
    create_app().run(host=host, port=port, debug=os.environ.get("DEBUG") == "1")
