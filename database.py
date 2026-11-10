"""Veritabanı bağlantısı ve tablolar.

Bütün veriler tek bir SQLite dosyasında duruyor (data/nailart.db). SQLite Python'la
birlikte geliyor, ayrıca bir veritabanı kurmaya gerek yok.
"""
import os
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).resolve().parent
# Sunucuda veriler kodun yanında değil, ayrı bir klasörde duruyor (NAILART_DATA_DIR=/opt/nailart/data)
DATA_DIR = Path(os.environ.get("NAILART_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"      # tasarım fotoğrafları
DB_PATH = DATA_DIR / "nailart.db"

# Tablolar. "IF NOT EXISTS" yazdığım için uygulama her açıldığında bunu çalıştırmak sorun olmuyor.
SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    instagram   TEXT,
    birthday    TEXT,             -- YYYY-MM-DD
    nail_notes  TEXT,             -- alerji, tırnak sağlığı, hassasiyetler
    preferences TEXT,             -- sevdiği renkler, şekil, uzunluk
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT,
    duration_min INTEGER NOT NULL DEFAULT 60,
    price        REAL NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS appointments (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    start_at     TEXT NOT NULL,   -- YYYY-MM-DDTHH:MM (yerel saat)
    duration_min INTEGER NOT NULL DEFAULT 60,
    status       TEXT NOT NULL DEFAULT 'planned'
                 CHECK (status IN ('planned', 'completed', 'cancelled', 'no_show')),
    price        REAL NOT NULL DEFAULT 0,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(start_at);
CREATE INDEX IF NOT EXISTS idx_appointments_customer ON appointments(customer_id);

-- Bir randevuda birden çok hizmet olabilir (çoka-çok ilişki)
CREATE TABLE IF NOT EXISTS appointment_services (
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    service_id     INTEGER NOT NULL REFERENCES services(id),
    PRIMARY KEY (appointment_id, service_id)
);

CREATE TABLE IF NOT EXISTS designs (
    id             INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    appointment_id INTEGER REFERENCES appointments(id) ON DELETE SET NULL,
    date           TEXT NOT NULL,  -- YYYY-MM-DD
    title          TEXT,
    shape          TEXT,
    length         TEXT,
    colors         TEXT,
    technique      TEXT,
    products       TEXT,           -- kullanılan ürünler / renk kodları
    photo          TEXT,           -- data/uploads altındaki dosya adı
    notes          TEXT,
    favorite       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_designs_customer ON designs(customer_id);

-- Uygulama ayarları: şifre özeti, oturum anahtarı vb.
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

DEFAULT_SERVICES = [
    ("Kalıcı oje", "Oje", 60, 600),
    ("Protez tırnak (jel)", "Protez", 120, 1400),
    ("Protez dolgu", "Protez", 90, 1000),
    ("Nail art (tırnak başı)", "Tasarım", 10, 75),
    ("Klasik manikür", "Bakım", 45, 400),
    ("Pedikür", "Bakım", 60, 550),
    ("Söküm", "Bakım", 30, 250),
]

# Randevuları müşteri adı ve hizmet adlarıyla birlikte getiren sorgu.
# Birçok sayfada sonuna WHERE / ORDER BY ekleyip kullanıyorum.
APPOINTMENT_SELECT = """
    SELECT a.*, c.name AS customer_name, c.phone AS customer_phone,
        (SELECT group_concat(s.name, ', ')
           FROM appointment_services x JOIN services s ON s.id = x.service_id
          WHERE x.appointment_id = a.id) AS service_names
    FROM appointments a
    JOIN customers c ON c.id = a.customer_id
"""


def connect():
    """Veritabanına yeni bir bağlantı açıyor."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # satırlara row["name"] diye erişebilmek için
    conn.execute("PRAGMA foreign_keys = ON")  # yabancı anahtar kontrollerini açıyor
    return conn


def get_db():
    """Bir istek boyunca hep aynı bağlantıyı kullanıyor (bağlantı Flask'ın g nesnesinde duruyor)."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(exception=None):
    """İstek bitince bağlantıyı kapatıyor."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Tabloları oluşturuyor. İlk çalıştırmada hazır hizmet listesini de ekliyor."""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO services (name, category, duration_min, price) VALUES (?, ?, ?, ?)",
                DEFAULT_SERVICES,
            )
        conn.commit()
    finally:
        conn.close()
    # Sunucuda uygulama ve bakım kullanıcısı aynı grupta, ikisi de veritabanına yazabilsin
    try:
        DB_PATH.chmod(0o660)
    except OSError:
        pass   # dosya başka kullanıcınınsa izinleri zaten o ayarlamış oluyor


def get_setting(key):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()
