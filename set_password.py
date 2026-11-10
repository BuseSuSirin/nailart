"""Şifreyi komut satırından belirlemek ya da değiştirmek için (sunucuda ilk kurulumda lazım).

Kullanım: python set_password.py
Şifreyi yazarken ekranda görünmüyor. Şifre değişince açık oturumlar kapanıyor. Müşteri verileri silinmiyor.
"""
import getpass
import os
import secrets
import sys

from werkzeug.security import generate_password_hash

import database
from auth import MIN_PASSWORD_LENGTH

# Sunucuda veritabanına hem bu kullanıcı hem de uygulamanın kullanıcısı yazabilsin (aynı gruptalar)
os.umask(0o007)

password = getpass.getpass("Yeni şifre: ")
if len(password) < MIN_PASSWORD_LENGTH:
    sys.exit(f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalı.")
if getpass.getpass("Yeni şifre (tekrar): ") != password:
    sys.exit("Şifreler eşleşmiyor.")

database.init_db()
conn = database.connect()
for key, value in (("password_hash", generate_password_hash(password)),
                   ("session_version", secrets.token_hex(8))):
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
conn.commit()
conn.close()
print("Şifre kaydedildi.")
