"""Örnek veri: boş veritabanına birkaç müşteri, randevu ve tasarım ekliyor.

Kullanım: python seed_demo.py
"""
from datetime import date, datetime, timedelta

import database

CUSTOMERS = [
    # ad, telefon, instagram, doğum günü (bugünden kaç gün sonra ya da tarih), tercihler, sağlık notu
    ("Elif Yılmaz", "0532 111 22 33", "elifyilmaz", 9, "Nude ve pastel tonlar, badem şekil, orta uzunluk", None),
    ("Zeynep Kaya", "0541 222 33 44", "zeynepk", "1990-03-14", "Koyu bordo, krom efektler, kısa kare",
     "Kütikül bölgesi hassas, freze dikkatli kullanılmalı"),
    ("Ayşe Demir", "0505 333 44 55", None, 22, "French ve minimal çizimler",
     "HEMA alerjisi şüphesi — hipoalerjenik jel kullan"),
    ("Selin Aksoy", "0533 444 55 66", "selin.aksoy", None, "Renkli, eğlenceli tasarımlar, uzun balerin", None),
    ("Merve Şahin", "0544 555 66 77", None, "1997-11-30", "Kedi gözü, taşlı aksesuar", None),
    ("İrem Öztürk", "0530 666 77 88", "iremozturk", None, "Sade, açık pembe", None),
]

# Her müşterinin randevuları: (bugünden kaç gün önce/sonra, saat, durum, hizmetler)
APPOINTMENTS = {
    "Elif Yılmaz": [(-80, "11:00", "completed", ["Protez tırnak (jel)", "Nail art (tırnak başı)"]),
                    (-55, "11:00", "completed", ["Protez dolgu"]),
                    (-30, "14:00", "completed", ["Protez dolgu", "Nail art (tırnak başı)"]),
                    (0, "10:00", "planned", ["Protez dolgu"])],
    "Zeynep Kaya": [(-60, "16:00", "completed", ["Kalıcı oje"]),
                    (-35, "16:00", "completed", ["Kalıcı oje"]),
                    (-12, "13:00", "no_show", ["Kalıcı oje"]),
                    (0, "14:30", "planned", ["Kalıcı oje", "Nail art (tırnak başı)"])],
    "Ayşe Demir": [(-90, "10:00", "completed", ["Klasik manikür", "Kalıcı oje"]),
                   (-40, "10:00", "completed", ["Kalıcı oje"]),
                   (3, "12:00", "planned", ["Kalıcı oje"])],
    "Selin Aksoy": [(-70, "15:00", "completed", ["Protez tırnak (jel)", "Nail art (tırnak başı)"]),
                    (-44, "15:00", "completed", ["Protez dolgu", "Nail art (tırnak başı)"])],
    "Merve Şahin": [(-25, "17:00", "completed", ["Kalıcı oje", "Nail art (tırnak başı)"]),
                    (1, "17:00", "planned", ["Pedikür"])],
    "İrem Öztürk": [(-5, "12:00", "completed", ["Klasik manikür"]),
                    (4, "15:00", "planned", ["Kalıcı oje"])],
}

# (başlık, şekil, uzunluk, renkler, teknik, favori)
DESIGNS = {
    "Elif Yılmaz": [("Nude ombre + altın varak", "Badem", "Orta", "Nude, altın", "Ombre", 1),
                    ("Pastel lila mermer", "Badem", "Orta", "Lila, beyaz", "Mermer", 0)],
    "Zeynep Kaya": [("Bordo krom", "Kare", "Kısa", "Bordo", "Krom", 1)],
    "Ayşe Demir": [("Klasik French", "Oval", "Kısa", "Beyaz, şeffaf pembe", "French", 0)],
    "Selin Aksoy": [("Neon yaz çizimleri", "Balerin", "Uzun", "Neon pembe, turuncu, yeşil", "Çizim", 1)],
    "Merve Şahin": [("Zümrüt kedi gözü", "Badem", "Orta", "Zümrüt yeşili", "Kedi gözü", 0)],
}

NAIL_ART_PER_HAND = 6   # "tırnak başı" fiyatı olan hizmette 6 tırnak sayıyoruz


def day_offset(days):
    return date.today() + timedelta(days=days)


def main():
    database.init_db()
    conn = database.connect()
    if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        print("Veritabanında zaten müşteri var, örnek veri eklenmedi.")
        return

    services = {s["name"]: s for s in conn.execute("SELECT * FROM services")}
    for index, (name, phone, instagram, birthday, preferences, nail_notes) in enumerate(CUSTOMERS):
        if isinstance(birthday, int):   # doğum günü X gün sonra olsun ki panelde görünsün
            birthday = day_offset(birthday).replace(year=1992).isoformat()
        first_visit = min(a[0] for a in APPOINTMENTS[name])
        created_at = datetime.combine(day_offset(first_visit - 1 - index), datetime.min.time()).isoformat(" ")
        customer_id = conn.execute(
            "INSERT INTO customers (name, phone, instagram, birthday, preferences, nail_notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, phone, instagram, birthday, preferences, nail_notes, created_at)).lastrowid

        completed = []
        for offset, time, status, service_names in APPOINTMENTS[name]:
            chosen = [services[n] for n in service_names]
            price = sum(s["price"] * (NAIL_ART_PER_HAND if s["name"].startswith("Nail art") else 1) for s in chosen)
            start_at = f"{day_offset(offset).isoformat()}T{time}"
            appointment_id = conn.execute(
                "INSERT INTO appointments (customer_id, start_at, duration_min, status, price) VALUES (?, ?, ?, ?, ?)",
                (customer_id, start_at, sum(s["duration_min"] for s in chosen), status, price)).lastrowid
            conn.executemany("INSERT INTO appointment_services (appointment_id, service_id) VALUES (?, ?)",
                             [(appointment_id, s["id"]) for s in chosen])
            if status == "completed":
                completed.append((appointment_id, start_at[:10]))

        # Tasarımları son tamamlanan randevulara bağlıyoruz
        for i, (title, shape, length, colors, technique, favorite) in enumerate(DESIGNS.get(name, [])):
            appointment_id, design_date = completed[-1 - i]
            conn.execute(
                "INSERT INTO designs (customer_id, appointment_id, date, title, shape, length, colors, technique, favorite) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (customer_id, appointment_id, design_date, title, shape, length, colors, technique, favorite))

    conn.commit()
    conn.close()
    print(f"{len(CUSTOMERS)} örnek müşteri, randevuları ve tasarımları eklendi.")


if __name__ == "__main__":
    main()
