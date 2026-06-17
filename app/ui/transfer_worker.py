# -*- coding: utf-8 -*-
"""Runs the transfer engine on a background thread."""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from ..core.store import Connection
from ..core.engine import TransferEngine, DirectionError
from ..core import monitoring


class TransferWorker(QThread):
    log = Signal(str, str)         # level, message
    percent = Signal(int, int)     # current, total
    finished_run = Signal(object)  # TransferSummary
    blocked = Signal(str)          # direction-blocked message

    def __init__(
        self,
        source: Connection,
        target: Connection,
        record_id: str,
        root_table: str,
        pk_column: str,
        fk_column: str,
        created_by: Optional[str] = None,
        field_overrides: Optional[dict] = None,
        skip_delete: bool = False,
        dry_run: bool = False,
    ):
        super().__init__()
        self.source = source
        self.target = target
        self.record_id = record_id
        self.root_table = root_table
        self.pk_column = pk_column
        self.fk_column = fk_column
        self.created_by = created_by
        self.field_overrides = field_overrides
        self.skip_delete = skip_delete
        self.dry_run = dry_run
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        run_logger, log_path = monitoring.new_run_logger(self.record_id)

        def emit_log(level: str, msg: str):
            self.log.emit(level, msg)
            getattr(run_logger, "error" if level == "error" else "info")(msg)

        t0 = time.time()
        engine = TransferEngine(
            source=self.source,
            target=self.target,
            record_id=self.record_id,
            root_table=self.root_table,
            pk_column=self.pk_column,
            fk_column=self.fk_column,
            created_by=self.created_by,
            field_overrides=self.field_overrides,
            skip_delete=self.skip_delete,
            dry_run=self.dry_run,
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
                message = f"{summary.total_errors} row error(s)"
            else:
                status = "success"
        except DirectionError as e:
            status = "blocked"
            message = str(e)
            emit_log("error", f"DIRECTION BLOCKED: {e}")
            self.blocked.emit(str(e))
        except Exception as e:
            status = "error"
            message = str(e)
            emit_log("error", f"Error: {e}")

        duration = round(time.time() - t0, 2)
        rec = monitoring.RunRecord.now(
            record_id=str(self.record_id),
            root_table=self.root_table,
            fk_column=self.fk_column,
            source_name=self.source.name,
            source_env=self.source.env.label,
            target_name=self.target.name,
            target_env=self.target.env.label,
            status=status,
            total_rows=summary.total_rows if summary else 0,
            total_errors=summary.total_errors if summary else 0,
            skipped_tables=summary.skipped_tables if summary else 0,
            duration_sec=duration,
            log_file=str(log_path),
            dry_run=self.dry_run,
            message=message,
        )
        monitoring.append_history(rec)

        for h in list(run_logger.handlers):
            h.close()
            run_logger.removeHandler(h)

        if status != "blocked":
            self.finished_run.emit(summary)
