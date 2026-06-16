# -*- coding: utf-8 -*-
"""Transfer'i ayrı thread'de çalıştıran worker."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from ..core.store import Connection
from ..core.engine import TransferEngine, DirectionError
from ..core import monitoring


class TransferWorker(QThread):
    log = Signal(str, str)            # level, message
    percent = Signal(int, int)        # current, total
    finished_run = Signal(object)     # TransferSummary
    blocked = Signal(str)             # yön yasağı mesajı

    def __init__(self, source: Connection, target: Connection, beyanname_id: int,
                 created_by: str | None, mukellef_vkn: str | None, skip_delete: bool):
        super().__init__()
        self.source = source
        self.target = target
        self.beyanname_id = beyanname_id
        self.created_by = created_by
        self.mukellef_vkn = mukellef_vkn
        self.skip_delete = skip_delete
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        run_logger, log_path = monitoring.new_run_logger(self.beyanname_id)

        def emit_log(level: str, msg: str):
            self.log.emit(level, msg)
            getattr(run_logger, "error" if level == "error" else "info")(msg)

        t0 = time.time()
        engine = TransferEngine(
            source=self.source, target=self.target, beyanname_id=self.beyanname_id,
            created_by=self.created_by, mukellef_vkn=self.mukellef_vkn,
            skip_delete=self.skip_delete,
            progress=emit_log,
            percent=lambda c, t: self.percent.emit(c, t),
            cancel_check=lambda: self._cancel,
        )

        status = "success"
        message = ""
        summary = None
        try:
            summary = engine.run()
            if summary.fatal_error:
                status = "error"
                message = summary.fatal_error
            elif self._cancel:
                status = "cancelled"
            elif summary.total_errors > 0:
                status = "warning"
                message = f"{summary.total_errors} satır hatası"
            else:
                status = "success"
        except DirectionError as e:
            status = "blocked"
            message = str(e)
            emit_log("error", f"YÖN YASAĞI: {e}")
            self.blocked.emit(str(e))
        except Exception as e:
            status = "error"
            message = str(e)
            emit_log("error", f"Hata: {e}")

        duration = round(time.time() - t0, 2)
        rec = monitoring.RunRecord.now(
            beyanname_id=self.beyanname_id,
            source_name=self.source.name, source_env=self.source.env.label,
            target_name=self.target.name, target_env=self.target.env.label,
            status=status,
            total_rows=summary.total_rows if summary else 0,
            total_errors=summary.total_errors if summary else 0,
            skipped_tables=summary.skipped_tables if summary else 0,
            duration_sec=duration,
            log_file=str(log_path),
            message=message,
        )
        monitoring.append_history(rec)

        for h in list(run_logger.handlers):
            h.close()
            run_logger.removeHandler(h)

        if status != "blocked":
            self.finished_run.emit(summary)
