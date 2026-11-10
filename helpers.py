"""Birçok sayfada kullanılan sabitler ve küçük yardımcı fonksiyonlar.

Biçimlendirme fonksiyonlarını şablonlarda "filtre" olarak kullanıyorum.
Örneğin şablonda {{ randevu.price|money }} yazınca format_money() çalışıyor.
"""
from datetime import date, datetime, timedelta
from urllib.parse import quote

STATUS_LABELS = {
    "planned": "Planlandı",
    "completed": "Tamamlandı",
    "cancelled": "İptal",
    "no_show": "Gelmedi",
}
SHAPES = ["Badem", "Oval", "Kare", "Yuvarlak kare", "Balerin", "Stiletto"]
LENGTHS = ["Kısa", "Orta", "Uzun", "Ekstra uzun"]
TECHNIQUES = ["Düz renk", "French", "Ombre", "Baby boomer", "Krom", "Kedi gözü",
              "Mermer", "Çizim", "Taş / aksesuar", "3D", "Glitter"]

MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
          "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
WEEKDAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
# Takvimdeki kısa gün adları. İlk üç harfi almak olmuyor, çünkü
# "Cuma" da "Cumartesi" de "Cum" oluyor.
WEEKDAYS_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
TURKISH_ALPHABET = "abcçdefgğhıijklmnoöprsştuüvyz"


class FormError(Exception):
    """Formda kullanıcının düzeltmesi gereken bir hata olunca bunu fırlatıyoruz.

    conflict=True ise sorun saat çakışmasıdır. O zaman formda
    "yine de kaydet" kutusu çıkıyor.
    """

    def __init__(self, message, conflict=False):
        super().__init__(message)
        self.conflict = conflict


# ---------- Türkçe metin işlemleri ----------

def tr_lower(text):
    """Türkçeye göre küçük harfe çeviriyor (I -> ı, İ -> i)."""
    return (text or "").replace("I", "ı").replace("İ", "i").lower()


def turkish_sort_key(text):
    """İsimleri Türk alfabesine göre sıralamak için (Ç, Ş, Ü gibi harfler doğru yere gelsin)."""
    return [TURKISH_ALPHABET.index(ch) if ch in TURKISH_ALPHABET else 100 + ord(ch)
            for ch in tr_lower(text)]


def matches_search(query, *fields):
    """Aranan kelime bu alanlardan birinde geçiyor mu? Büyük/küçük harfe bakmıyor."""
    query = tr_lower(query.strip())
    return not query or any(query in tr_lower(f) for f in fields)


def initials(name):
    parts = (name or "?").split()
    return "".join(p[0] for p in parts[:2]).replace("i", "İ").upper()


def first_name(name):
    return (name or "").split(" ")[0]


# ---------- tarih ve para ----------

def to_date(text):
    """'2026-11-02' ya da '2026-11-02T10:00' metnini date nesnesine çeviriyor."""
    return date.fromisoformat(text[:10])


def week_start(day):
    """Verilen günün haftasındaki pazartesiyi buluyor."""
    return day - timedelta(days=day.weekday())


def format_money(amount):
    return "₺" + f"{amount or 0:,.0f}".replace(",", ".")


def format_date(text):
    """Örnek: 2 Kasım 2026"""
    if not text:
        return "—"
    d = to_date(text)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def format_date_short(text):
    """Örnek: 2 Kas 2026"""
    if not text:
        return "—"
    d = to_date(text)
    return f"{d.day} {MONTHS[d.month - 1][:3]} {d.year}"


def format_day_month(text):
    """Örnek: 2 Kasım Pazartesi"""
    d = to_date(text)
    return f"{d.day} {MONTHS[d.month - 1]} {WEEKDAYS[d.weekday()]}"


def format_clock(text):
    """Örnek: '2026-11-02T10:00' -> '10:00'"""
    return text[11:16] if text else ""


def days_ago(text):
    if not text:
        return "—"
    days = (date.today() - to_date(text)).days
    if days == 0:
        return "bugün"
    return f"{days} gün önce" if days > 0 else f"{-days} gün sonra"


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def clean(value):
    """Formdan gelen metnin baştaki ve sondaki boşluklarını siliyor. Boşsa None (veritabanında NULL) döndürüyor."""
    value = (value or "").strip()
    return value or None


# ---------- WhatsApp ----------

def whatsapp_link(phone, message=""):
    """Telefon numarasından wa.me bağlantısı yapıyor. Tıklayınca mesaj WhatsApp'ta hazır geliyor."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "9" + digits          # 0532... -> 90532...
    elif len(digits) == 10:
        digits = "90" + digits         # 532...  -> 90532...
    link = f"https://wa.me/{digits}"
    return f"{link}?text={quote(message)}" if message else link


def reminder_text(appointment):
    return (f"Merhaba {first_name(appointment['customer_name'])}, "
            f"{format_day_month(appointment['start_at'])} saat {format_clock(appointment['start_at'])} "
            "randevunuzu hatırlatmak isteriz 💅")


def placeholder_hue(text):
    """Fotoğrafı olmayan tasarımlara isme göre hep aynı rengi veriyor."""
    return sum(ord(ch) for ch in (text or "x")) % 360


def safe_next(url, default):
    """Kaydettikten sonra dönülecek adres. Sadece sitenin kendi adreslerine izin veriyor."""
    if url and url.startswith("/") and not url.startswith("//"):
        return url
    return default


def register_template_helpers(app):
    """Yukarıdaki fonksiyonları şablonlarda kullanılabilir hale getiriyor."""
    app.jinja_env.filters.update(
        money=format_money,
        date_long=format_date,
        date_short=format_date_short,
        day_month=format_day_month,
        clock=format_clock,
        days_ago=days_ago,
    )
    app.jinja_env.globals.update(
        STATUS_LABELS=STATUS_LABELS,
        SHAPES=SHAPES,
        LENGTHS=LENGTHS,
        TECHNIQUES=TECHNIQUES,
        WEEKDAYS=WEEKDAYS,
        WEEKDAYS_SHORT=WEEKDAYS_SHORT,
        whatsapp_link=whatsapp_link,
        reminder_text=reminder_text,
        first_name=first_name,
        initials=initials,
        placeholder_hue=placeholder_hue,
        today=lambda: date.today().isoformat(),
        now=datetime.now,
    )
