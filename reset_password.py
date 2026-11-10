"""Şifre unutulursa diye: şifreyi siliyor ve bütün oturumları kapatıyor. Müşteri verileri silinmiyor.

Kullanım: python reset_password.py
Sonra uygulama açılınca yeni şifre ekranı geliyor.
"""
import secrets

import database

database.init_db()
conn = database.connect()
conn.execute("DELETE FROM settings WHERE key = 'password_hash'")
conn.execute("INSERT INTO settings (key, value) VALUES ('session_version', ?) "
             "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (secrets.token_hex(8),))
conn.commit()
conn.close()
print("Şifre sıfırlandı. http://localhost:3000 adresinden yeni şifre belirleyebilirsin.")
