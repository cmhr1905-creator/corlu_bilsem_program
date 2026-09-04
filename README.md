# Çorlu BİLSEM Ders Programı

Öğrencinin adını yazınca haftalık ders programını veren tek dosyalık web uygulaması.
Akşam programı ile uyum programını tek çizelgede birleştirir. Sunucu yok, kurulum yok:
`index.html` tarayıcıda açılır, hepsi bu.

**Öğrenci verileri şifrelidir.** Sayfa açılınca önce parola sorar; parola girilene kadar
`index.html` içinde okunabilir tek bir öğrenci adı bulunmaz — yalnızca AES-256-GCM ile
şifrelenmiş metin durur. Bu yüzden site herkese açık olsa da arama motorları
öğrenci adlarını indeksleyemez, sayfayı kaydeden veriyi okuyamaz.

- **Öğrenci sekmesi** — ada yazmaya başlayın (Türkçe harf şart değil: `gulce ozsahin` de bulur).
  Haftalık program gün gün, saatiyle, öğretmeniyle çıkar. Bir derse tıklayınca grup listesi açılır.
- **Öğretmen sekmesi** — şifreli. Öğretmenin kişisel programı, grup listeleri ve
  haftalık ders saati / 30 saat doluluk ölçeri.
- **Yazdır / PDF** — iki sekmede de var; baskıda arayüz gizlenir, boş günler düşer.

## İki ayrı parola

| Nerede | Ne için | Varsayılan |
|---|---|---|
| Açılış ekranı | Programı görmek (veli, öğrenci, öğretmen) | `bilsem2018` |
| Öğretmen sekmesi | Öğretmen programları, grup listeleri, Excel yükleme | `1905` |

**Açılış parolasını mutlaka değiştirin** ve yalnız kuruma dağıtın:

```bash
python3 araclar/guncelle.py --parola-degistir
git commit -am "parola değiştirildi" && git push
```

Öğretmen parolası (`1905`) kodun içindedir; açılış parolasını bilen biri onu da okuyabilir.
Yani `1905` gerçek bir güvenlik katmanı değil, yalnızca velinin öğretmen ekranına
yanlışlıkla girmesini engelleyen bir ayrımdır. Asıl koruma açılış parolasıdır.

## Ders saati nasıl hesaplanıyor

| Durum | Saat |
|---|---|
| Bölünmemiş tam blok (16.00–20.00 · 08.40–12.40 · 13.30–17.30) | **5** |
| Grup ikiye bölünmüşse — 1-2-3. ders | **3** |
| Grup ikiye bölünmüşse — 4-5. ders | **2** |

Bir öğretmen aynı saatte birden fazla grup yürütüyorsa (örn. Cuma 16.00–18.20'de
hem PROJE-3 hem PROJE-4) o saatler **bir kez** sayılır; program ekranında hangi
gruplar olduğu not olarak yazar.

Bir öğretmenin haftalık üst sınırı **30 saat**. Ölçer sınıra yaklaşınca renk değiştirir,
aşarsa kırmızıya döner.

---

## Program güncellendiğinde — üç yol

### 1. Sadece kendi bilgisayarımda görmek istiyorum (en hızlı)
Öğretmen sekmesi → en alttaki alana yeni `.xlsx` dosyasını sürükleyip bırakın.
Uygulama dosyanın akşam mı uyum mu olduğunu kendi anlar, yalnız onu değiştirir ve
o tarayıcıda saklar. **Dosya hiçbir yere gönderilmez.**
Bu değişiklik sadece o tarayıcıda geçerlidir; başkaları eski programı görmeye devam eder.
Geri almak için: “Yerleşik programlara dön”.

### Veri kaynakları

Uygulama üç tür kaynağı birleştirir:

| Tür | Biçim | Örnek |
|---|---|---|
| `aksam` | sütun başına bir öğretmen | ana program, PROJE-1 (9/hazırlık) |
| `uyum` | sayfa başına bir öğretmen + SIRALI künyesi | uyum programı |
| `ek` | günler sütun, tek öğretmen | Müzik |

`ek` biçimindeki dosyalarda öğretmen adı, program adı ve ders saatleri **bulunmaz**;
bunlar yükleme sırasında elle verilir:

```bash
python3 araclar/guncelle.py --ek "Müzik" --ogretmen "Dr. Mustafa Cem Kaynar" \
        --brans MÜZİK --program MÜZİK ~/Downloads/muzik.xlsx
```

Bir dosyadan belirli bir sayfayı almak için `--sayfa "PROJE-1"`.
Aynı `kaynak` (dosya adı) ile yapılan yükleme o dosyanın önceki kaydını değiştirir,
diğer kaynaklara dokunmaz.

### 2. Herkesin gördüğü sürümü güncellemek (kalıcı)

```bash
cd ~/Projeler/bilsem_ders_programi
python3 araclar/guncelle.py ~/Downloads/yeni_aksam.xlsx
# ya da ikisini birden:
python3 araclar/guncelle.py ~/Downloads/aksam.xlsx ~/Downloads/uyum.xlsx
# parolayı sorar; sormasın derseniz:  --parola "..."

open index.html            # gözden geçirin
git commit -am "ders programı güncellendi"
git push                   # 1-2 dakika içinde site yenilenir
```

Araç hangi dosyanın hangi program olduğunu kendi bulur, yalnız onun verisini değiştirir,
ötekine dokunmaz. Şifreyi çözer, veriyi tazeler, yeniden şifreler.
Gerekenler: **Python 3** ve **Node.js** (`brew install node`).

### 3. Excel'in yapısı tamamen değişirse
Çözümleyici biçimi tanıyamazsa araç hata verip ne beklediğini yazar. O durumda
`index.html` içindeki `parseAksam` / `parseTeacherSheet` fonksiyonları elden geçmelidir.

---

## Yeni ders, atölye veya kulüp eklendiğinde

- **Var olan bir ders saati başlığı satırına yeni sütun eklediyseniz** (örn. Cuma
  1-2-3. ders satırına `LEGO ROBOTİK ATÖLYESİ`) — hiçbir şey yapmanıza gerek yok,
  uygulama o satırdaki her hücreyi başlık sayar, kendiliğinden tanır.
- **Sütunun ortasında yeni bir grup başlatıyorsanız** (mevcut grubun altına yeni bir
  program adı yazmak) — adın `index.html` içindeki şu listede geçen bir sözcükle
  başlaması gerekir:

  ```js
  var PROGRAM_ANAHTARLARI = ["DESTEK","ÖYG","OYG","PROJE","BYF","UYUM",
                             "ATÖLYE","ATOLYE","KULÜP","KULUP"];
  ```

  Yeni bir tür geliyorsa (örn. `SANAT`, `ROBOTİK`) sadece bu listeye ekleyin.
  Rozet rengi için `--f-<ad>` / `--f-<ad>-bg` tokenlerini de tanımlayabilirsiniz;
  tanımlamazsanız nötr gri görünür.

## Elle bakılması gereken tek yer: ders saatleri

Akşam programının **ders saatleri ana Excel sayfasında yok** — gizli öğretmen
sayfalarından okunup koda sabitlendi. Saatler değişirse `index.html` içindeki
`aksamTimes()` fonksiyonu elle güncellenmelidir:

```
hafta içi akşam    16.00–18.20 / 18.30–20.00
Cumartesi sabah    08.40–11.00 / 11.10–12.40
Cumartesi öğleden sonra  13.30–15.50 / 16.00–17.30
```

Uyum programının saatleri dosyadaki gün başlığından okunur, elle bakım gerektirmez.

---

## Dosyalar

```
index.html              uygulamanın tamamı (kod + şifreli veri + logo, tek dosya)
araclar/guncelle.py     Excel'i index.html'in içine şifreli gömen araç
araclar/sifrele.js      AES-256-GCM şifreleme/çözme (guncelle.py bunu çağırır)
logo.jpg                kurum logosu (index.html'in içine de gömülüdür)
```

## Kaynak dosyadaki bilinen iki hata

Bunlar Excel'den geliyor, uygulamada düzeltilmedi:

1. Akşam sayfası `F1` hücresi **“İNGİLİZVE”** — öğretmen adı yok, branş da yanlış yazılmış.
2. **MASUM TEKİN**'in branşı 1. satırda *COĞRAFYA*, sonraki bloklarda *SOSYAL BİLGİLER*.

Excel'de düzeltip yukarıdaki 2. yolla yükleyin, ikisi de kendiliğinden düzelir.

---

## Site engelliyse (FATİH / MEB ağı) — çevrimdışı kullanım

`index.html` **tek başına çalışan bir dosyadır.** Yazı tipleri, logo, program
verisi ve kodun tamamı dosyanın içinde gömülüdür. İnternet olmadan da,
`github.io` engelliyken de birebir aynı çalışır:

1. `index.html` dosyasını indirin (depoda **Code → Download ZIP**, ya da
   dosyaya tıklayıp **Download raw file**).
2. E-posta, WhatsApp, USB ya da okulun dosya paylaşımıyla dağıtın.
3. Öğretmen dosyayı masaüstüne kaydeder, çift tıklar. Parola ekranı gelir,
   her şey normal çalışır.

Chrome, Safari, Edge ve Firefox'ta `file://` ile açıldığında şifre çözme
(Web Crypto) çalışır — test edildi.

**Çevrimdışıyken çalışmayan tek şey:** öğretmen panelindeki Excel yükleme
(SheetJS kütüphanesi CDN'den geliyor). Programın görüntülenmesi, arama,
öğretmen programları ve yazdırma tam çalışır. Zaten kalıcı güncelleme
`araclar/guncelle.py` ile yapılıyor.

### iPhone / iPad ve Android — telefona kurma

Telefonda `.html` dosyasını açmak zahmetli. Onun yerine uygulamayı telefona kurun:

**iPhone / iPad (Safari):** Siteyi **engelli olmayan bir ağdan** (ev wifi'si ya da
mobil veri) açın → alttaki **Paylaş** düğmesi → **Ana Ekrana Ekle** → Ekle.
Ana ekranda kurum logosuyla bir simge çıkar. Bundan sonra uygulama telefonun
içinden açılır; okulun ağı engelli olsa da, internet hiç olmasa da çalışır.

**Android (Chrome):** Sağ üstteki ⋮ → **Uygulamayı yükle** / **Ana ekrana ekle**.

Kurulumdan sonra program güncellendiğinde, telefon açık bir ağa bağlıyken
uygulamayı bir kez açmanız yeterli — yeni sürüm arka planda inip bir sonraki
açılışta devreye girer.

**Kalıcı çözüm için:** İl Millî Eğitim Müdürlüğü Bilgi İşlem birimine
adresin erişime açılması için başvurulabilir. `github.io` genelde alan adı
kategorisi nedeniyle topluca engellenir, tek tek beyaz listeye alınabilir.

---

## Şifreleme nasıl çalışıyor

- Veri: `{aksam, uyum}` JSON'u → **AES-256-GCM**
- Anahtar: paroladan **PBKDF2-SHA256, 250.000 tur**, 16 baytlık rastgele tuz
- Her güncellemede tuz ve IV yenilenir
- Tarayıcı tarafında Web Crypto ile çözülür (~40 ms), parola sekme kapanana kadar
  `sessionStorage`'da tutulur — kalıcı olarak saklanmaz
- Parola hiçbir yere gönderilmez; sunucu yoktur

Bu, kararlı bir saldırganı değil, **arama motorlarını, toplu veri kazımayı ve
tesadüfen linke düşen kişiyi** engeller. Parola kurum dışına çıkarsa koruma biter —
o durumda parolayı değiştirip yeniden yayınlayın.
