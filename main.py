# -*- coding: utf-8 -*-
"""
Beyanname Transfer Tool — Masaüstü Uygulaması
=============================================
Ortamlar arası güvenli beyanname veri aktarım aracı.

Çalıştırma:
    python main.py

Paketleme (exe/app/binary):
    pyinstaller --noconfirm build.spec
"""

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app import __app_name__, __app_id__, __version__
from app.ui.main_window import MainWindow, app_icon


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(__app_id__)
    app.setWindowIcon(app_icon())

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
