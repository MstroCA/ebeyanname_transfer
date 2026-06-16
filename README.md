<div align="center">

<img src="assets/logo.png" width="96" alt="Beyanname Transfer"/>

# Beyanname Transfer

**Ortamlar arası güvenli beyanname veri aktarım aracı**

Test/Prod ortamındaki beyanname verisini, güvenli yön kurallarıyla
başka bir ortama taşıyan masaüstü uygulaması.

[![CI](https://img.shields.io/badge/CI-passing-30A46C)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-3D63DD)]()
[![Sürüm]([https://img.shields.io/badge/sürüm-1.0.0-3D63DD](https://github.com/MstroCA/ebeyanname_transfer/releases/tag/v1.0.0))]()

</div>

---

## Neden?

Test ortamında bir issue çıkıyor, local'de aynı veriyi ayağa kaldırmak
gerekiyor ama iş hep aynı yere dönüyor: onlarca bağlı tablo, foreign key
sırası, eksik kolonlar, Liquibase farkları, tek tek INSERT üretme derdi.

Bu araç o süreci otomatikleştirir. Bir `beyanname_id` verirsiniz; ilgili tüm
kayıtları kaynak ortamdan çekip hedef veritabanına taşır. V1 komut satırı
aracının yerini alan bu sürüm; arayüz, ortam yönetimi, yön güvenliği ve
izleme ekler.

## Öne Çıkanlar

- **Veritabanı tanımlama menüsü** — Prod / Test / Local ortamlarını arayüzden
  tanımlayın. Şifreler makineye özel anahtarla **şifreli** saklanır.
- **Yön güvenliği** — veri yalnızca üst ortamdan alt ortama akar. Yasak yön
  seçilirse arayüz kırmızıya döner, başlatma engellenir. Hem arayüzde hem
  motorda iki kez zorlanır.
- **Görsel ortam ikonları** — renk kodlu veritabanı ikonları (Prod kırmızı,
  Test amber, Local yeşil).
- **Canlı log + izleme** — aktarım adımları gerçek zamanlı akar; tüm
  çalıştırmalar geçmişte durum/satır/süre ile saklanır.
- **Tek dosya, kurulumsuz** — Windows/macOS/Linux için hazır paket.

## İzin Verilen / Yasak Yönler

| Yön | Durum |  | Yön | Durum |
|---|---|---|---|---|
| Prod → Test | ✅ | | Local → Prod | ⛔ |
| Prod → Local | ✅ | | Test → Prod | ⛔ |
| Test → Local | ✅ | | Local → Test | ⛔ |

> **Kural:** Veri her zaman daha üst (canlı/güvenli) ortamdan daha alt
> (geliştirme) ortama doğru akar; asla yukarı doğru değil.

## Kurulum

### Hazır paket (önerilen)

[Releases](../../releases) sayfasından işletim sisteminize uygun dosyayı
indirin, arşivi açın, çalıştırın. Kurulum gerekmez.

| İşletim Sistemi | Dosya |
|---|---|
| 🪟 Windows | `BeyannameTransfer-windows.zip` |
| 🍎 macOS | `BeyannameTransfer-macos.zip` |
| 🐧 Linux | `BeyannameTransfer-linux.tar.gz` |

### Kaynaktan çalıştırma

```bash
pip install -r requirements.txt
python main.py
```

Python 3.9+ gereklidir.

## Kullanım

1. **Veritabanları** sekmesinden ortamlarınızı tanımlayın. Her tanımı
   "Bağlantıyı Test Et" ile doğrulayabilirsiniz.
2. **Aktarım** sekmesinde kaynak/hedef seçin. Yön uygunsa banner yeşile döner.
3. Beyanname ID'sini girip (isteğe bağlı `created_by` / `mükellef VKN`)
   **Aktarımı Başlat**'a basın.
4. **İzleme** sekmesinden geçmiş çalıştırmaları ve logları görün.

## Paketleme

Sürüm etiketi push edildiğinde GitHub Actions otomatik olarak üç işletim
sistemi için paketler ve Release oluşturur:

```bash
git tag v2.0.1
git push origin v2.0.1
```

Yerel paketleme:

```bash
# macOS / Linux
./scripts/build.sh
# Windows
.\scripts\build.ps1
```

## Mimari

```
app/
  core/                  # arayüzden bağımsız çekirdek (test kapsamında)
    environments.py      # ortam tipleri + yön kuralları
    store.py             # şifreli bağlantı saklama
    engine.py            # transfer motoru
    monitoring.py        # log + çalıştırma geçmişi
  ui/                    # PySide6 arayüz
    theme.py  icons.py  widgets.py
    connections_view.py  transfer_view.py  transfer_worker.py
    monitoring_view.py   main_window.py
tests/                   # yön + saklama testleri
.github/workflows/       # CI + Release otomasyonu
scripts/                 # yerel build betikleri
assets/                  # logo + ikon
```

## Veri Konumu

```
~/.beyanname_transfer/
  connections.enc      # şifreli bağlantı tanımları
  .salt / .machine     # makineye özel anahtar türetme
  history.jsonl        # çalıştırma geçmişi
  logs/                # her aktarımın detaylı logu
```

## Testler

```bash
pytest tests/ -v
```

Yön kuralları ve şifreli saklama kritik kısıtlardır; CI her push'ta çalışır.

---

<div align="center">
<sub>GİB Teknoloji — Platform Engineering</sub>
</div>
