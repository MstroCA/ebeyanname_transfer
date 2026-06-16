#!/usr/bin/env bash
# Yerel paketleme (macOS / Linux).
set -e
cd "$(dirname "$0")/.."
echo "▸ Bağımlılıklar yükleniyor..."
pip install -r requirements.txt -r build-requirements.txt
echo "▸ Paketleniyor..."
pyinstaller --noconfirm build.spec
echo "✓ Tamam. Çıktı: dist/"
ls -lh dist/
