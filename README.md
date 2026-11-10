# Nail Art CRM

Nail art salonları için yaptığım bir müşteri takip (CRM) uygulaması. Salonlarda müşteri bilgileri, randevular ve yapılan tasarımlar genelde deftere yazılıyor ya da telefonda fotoğraf olarak duruyor. Ben bunları tek bir yerde toplamak istedim.

Python ve Flask ile yazdım. Veritabanı SQLite. Sayfalar Jinja şablonlarıyla sunucuda hazırlanıyor, tasarım için de düz CSS kullandım.

## Neler var

- Müşteri ekleme: telefon, Instagram, doğum günü, tercihler ve alerji gibi sağlık notları. Sağlık notu varsa profilde sarı bir uyarı çıkıyor.
- Haftalık takvim. Bir randevuya birkaç hizmet seçilebiliyor. Süre ve ücret boş bırakılırsa seçilen hizmetlere göre kendisi hesaplıyor.
- Aynı saate iki randevu girilirse uyarı veriyor. İstersen yine de kaydedebiliyorsun.
- Randevuyu "tamamlandı" yapınca tasarım formu açılıyor, fotoğraf, şekil ve renkleri oradan kaydediyorsun.
- Tasarım galerisi: arama yapılabiliyor, şekle göre filtrelenebiliyor. Eski bir tasarımda "Aynısını yap" deyince yeni randevu açılıyor.
- Müşteri profilinde kaç kez geldiği, toplam ne kadar harcadığı, kaç günde bir geldiği ve en çok hangi hizmeti aldığı görünüyor.
- Panelde bugünün randevuları ve bu ayın cirosu var. 21 günden uzun süredir gelmeyenler (dolgu zamanı gelenler) ve yaklaşan doğum günleri de burada listeleniyor.
- WhatsApp'tan hatırlatma mesajı atmak için bağlantı var.

## Nasıl çalıştırılır

Bilgisayarda Python 3 olmalı. Windows'ta:

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py
python app.py
```

`seed_demo.py` birkaç örnek müşteri, randevu ve tasarım ekliyor. Şart değil ama denemek için iyi oluyor. Sonra tarayıcıda `http://localhost:3000` adresine giriliyor. İlk açılışta şifre belirlemek gerekiyor.

Şifre unutulursa `python reset_password.py` ile sıfırlanıyor, veriler silinmiyor.

## Dosyalar

| Dosya | Ne işe yarıyor |
|---|---|
| `app.py` | Uygulamayı başlatıyor ve her istekte giriş yapılmış mı diye bakıyor. |
| `database.py` | Tablolar ve veritabanı bağlantısı. |
| `auth.py` | Giriş, çıkış ve şifre işleri. |
| `dashboard.py` | Ana panel. |
| `appointments.py` | Takvim, randevu ekleme/düzenleme ve çakışma kontrolü. |
| `customers.py` | Müşteri listesi ve profil sayfası. |
| `designs.py` | Tasarım galerisi ve fotoğraf yükleme. |
| `services.py` | Hizmetler ve fiyatlar. |
| `helpers.py` | Tarih ve para yazdırma, Türkçe arama ve sıralama gibi küçük fonksiyonlar. |
| `templates/` | HTML şablonları. `base.html` bütün sayfalardaki ortak menü. |
| `static/styles.css` | CSS dosyası. |
| `seed_demo.py` | Örnek veri ekliyor. |
| `reset_password.py`, `set_password.py` | Şifreyi sıfırlamak ve sunucuda şifre koymak için. |

Bütün sayfalar aynı mantıkla çalışıyor: her adres Flask'ta bir fonksiyona bağlı, fonksiyon SQL ile veriyi çekiyor ve `render_template` ile şablona veriyor. Mesela `/customers/1` açılınca `customers.py` içindeki `detail()` çalışıyor.

## Veritabanı

Altı tablo var:

- `customers`: müşteriler
- `appointments`: randevular (tarih, süre, ücret, durum)
- `services`: hizmetler ve fiyatları
- `appointment_services`: hangi randevuda hangi hizmetler var. Bir randevuda birden fazla hizmet olabildiği için bunu ayrı bir tabloda tuttum.
- `designs`: tasarımlar. İstenirse bir randevuya bağlanabiliyor.
- `settings`: şifre hash'i gibi ayarlar

Bir müşteri silinince randevuları ve tasarımları da siliniyor (`ON DELETE CASCADE`). Randevunun durumu sadece `planned`, `completed`, `cancelled` ya da `no_show` olabiliyor, bunu `CHECK` ile kontrol ettim.

ORM kullanmadım, sorguları kendim SQL olarak yazdım. Kullanıcının girdiği değerleri SQL'in içine yazmıyorum, hepsini `?` ile ayrı gönderiyorum.

Veriler `data/` klasöründe duruyor (`nailart.db` ve fotoğraflar). Bu klasörü GitHub'a koymadım.

## Güvenlik

- Şifre veritabanında açık halde değil, hash olarak duruyor.
- 5 kez yanlış şifre girilirse giriş 5 dakika kilitleniyor.
- Şifre değişince diğer cihazlardaki oturumlar kapanıyor.
- Giriş yapmadan hiçbir sayfa ya da fotoğraf açılmıyor.
- Yüklenen dosyanın gerçekten fotoğraf olup olmadığına bakılıyor ve dosya rastgele bir isimle kaydediliyor.

## Sonra eklemek istediklerim

- Birden fazla çalışan, her birine ayrı takvim
- Kapora takibi
- Aylık ciro grafiği
- Otomatik testler
