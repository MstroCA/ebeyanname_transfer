# -*- coding: utf-8 -*-
"""
Run logging and transfer history.

- Per-run log file: ~/.recordrelay/logs/
- History (JSONL): ~/.recordrelay/history.jsonl
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".recordrelay"
LOG_DIR = APP_DIR / "logs"
HISTORY_FILE = APP_DIR / "history.jsonl"


def new_run_logger(record_id: str) -> tuple[logging.Logger, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = str(record_id).replace("/", "_").replace("\\", "_")
    path = LOG_DIR / f"transfer_{safe_id}_{ts}.log"

    logger = logging.getLogger(f"transfer.{ts}.{safe_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(fh)
    logger.propagate = False
    return logger, path


@dataclass
class RunRecord:
    timestamp: str
    record_id: str
    root_table: str
    fk_column: str
    source_name: str
    source_env: str
    target_name: str
    target_env: str
    status: str           # "success" | "warning" | "error" | "blocked" | "cancelled"
    total_rows: int
    total_errors: int
    skipped_tables: int
    duration_sec: float
    log_file: str
    dry_run: bool = False
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
                data = json.loads(line)
                # backward compat: old records used beyanname_id
                if "beyanname_id" in data and "record_id" not in data:
                    data["record_id"] = str(data.pop("beyanname_id"))
                data.setdefault("root_table", "beyanname")
                data.setdefault("fk_column", "beyanname_id")
                data.setdefault("dry_run", False)
                records.append(RunRecord(**data))
            except (json.JSONDecodeError, TypeError):
                continue
    records.reverse()
    return records[:limit]
