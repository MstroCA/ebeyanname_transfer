# Değişiklik Günlüğü

Bu projedeki önemli değişiklikler bu dosyada tutulur.
Format [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) temellidir
ve proje [Semantic Versioning](https://semver.org/lang/tr/) kullanır.

## [2.0.0] - 2025

### Eklenenler
- Masaüstü arayüz (PySide6) — V1 CLI aracının yerini alır.
- Veritabanı tanımlama menüsü; ortam bazlı (Prod / Test / Local) bağlantılar.
- Bağlantı şifrelerinin makineye özel anahtarla şifreli saklanması.
- Ortamlar arası **yön güvenliği**: veri yalnızca üst ortamdan alt ortama akar.
  - İzinli: Prod→Test, Prod→Local, Test→Local
  - Yasak: Local→Prod, Test→Prod, Local→Test, aynı→aynı
- Ortam bazlı renk kodlu veritabanı ikonları.
- Canlı log konsolu ve ilerleme göstergesi.
- İzleme paneli: çalıştırma geçmişi, durum rozetleri, log dosyalarına erişim.
- Bağlantı testi butonu.
- Windows / macOS / Linux için otomatik paketleme (GitHub Actions).

### Teknik
- Yön kuralları hem arayüzde hem motorda iki kez zorlanır (defense-in-depth).
- Çekirdek mantık (yön kuralları, saklama, motor) arayüzden bağımsız ve test kapsamında.

## [1.0.0]
### Eklenenler
- İlk sürüm: komut satırı (CLI) beyanname transfer aracı.
