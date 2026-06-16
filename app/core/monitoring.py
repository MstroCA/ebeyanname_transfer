# -*- coding: utf-8 -*-
"""
Loglama ve çalıştırma geçmişi (monitoring).

- Her transfer için detaylı log dosyası: ~/.beyanname_transfer/logs/
- Çalıştırma geçmişi özeti (JSONL): ~/.beyanname_transfer/history.jsonl
  Monitoring panelinde son çalıştırmalar, satır sayıları, hata/uyarı
  durumları bu dosyadan okunur.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".beyanname_transfer"
LOG_DIR = APP_DIR / "logs"
HISTORY_FILE = APP_DIR / "history.jsonl"


def new_run_logger(beyanname_id: int) -> tuple[logging.Logger, Path]:
    """Tek bir transfer çalıştırması için dosya logger'ı üretir."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"transfer_{beyanname_id}_{ts}.log"

    logger = logging.getLogger(f"transfer.{ts}.{beyanname_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    logger.propagate = False
    return logger, path


@dataclass
class RunRecord:
    timestamp: str
    beyanname_id: int
    source_name: str
    source_env: str
    target_name: str
    target_env: str
    status: str          # "success" | "warning" | "error" | "blocked" | "cancelled"
    total_rows: int
    total_errors: int
    skipped_tables: int
    duration_sec: float
    log_file: str
    message: str = ""

    @staticmethod
    def now(**kw) -> "RunRecord":
        return RunRecord(timestamp=datetime.now().isoformat(timespec="seconds"), **kw)


def append_history(record: RunRecord) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def read_history(limit: int = 100) -> list[RunRecord]:
    if not HISTORY_FILE.exists():
        return []
    records: list[RunRecord] = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(RunRecord(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
    records.reverse()  # en yeni en üstte
    return records[:limit]
