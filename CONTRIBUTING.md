# Katkı Rehberi

## Geliştirme Ortamı

```bash
git clone <repo>
cd beyanname-transfer
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[dev]"
python main.py
```

## Testler

```bash
pytest tests/ -v
```

Yön kuralları (`tests/test_directions.py`) ve şifreli saklama
(`tests/test_store.py`) kritik kısıtlardır; bunlara dokunan her değişiklik
test ile doğrulanmalıdır.

## Sürüm Çıkarma

1. `app/__init__.py` ve `CHANGELOG.md` içinde sürümü güncelleyin.
2. Etiket atın: `git tag v2.0.1 && git push origin v2.0.1`
3. GitHub Actions otomatik olarak üç işletim sistemi için paketleyip
   Release oluşturur.

## Kod Stili

- `ruff check app tests` temiz geçmeli.
- Çekirdek mantık (`app/core`) arayüzden bağımsız kalmalı; UI importu içermez.
