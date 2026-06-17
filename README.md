<div align="center">

<img src="assets/logo.png" width="96" alt="RecordRelay"/>

# RecordRelay

**Universal database record transfer across environments**

Transfer any record — with all its related rows — between PostgreSQL or MySQL databases safely. Environment direction rules prevent accidental upstream writes. Works as a desktop app (EXE), IntelliJ plugin, or CLI.

[![CI](https://github.com/MstroCA/recordrelay/actions/workflows/ci.yml/badge.svg)](https://github.com/MstroCA/recordrelay/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MstroCA/recordrelay?color=3D63DD)](https://github.com/MstroCA/recordrelay/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-3D63DD)]()
[![IntelliJ Plugin](https://img.shields.io/badge/JetBrains-Plugin-3D63DD?logo=intellijidea&logoColor=white)]()

</div>

---

## Why?

You have a bug in staging. You need the exact production record — with all 20 related tables — in your local database. Right now. Without writing 200 SQL lines or breaking foreign key order.

RecordRelay does that in three clicks: pick source, pick target, enter the record ID.

---

## Features

- **Generic transfer** — configure any root table + FK column. Works with `beyanname_id`, `order_id`, `user_id`, or any schema.
- **Multi-database** — PostgreSQL and MySQL/MariaDB supported.
- **Environment direction rules** — data only flows downstream (PROD → TEST → LOCAL). Upstream writes are blocked at both the UI and engine level.
- **Dry-run mode** — preview exactly what would be transferred before writing anything.
- **Transfer Profiles** — save named configs (root table + FK column) for quick reuse.
- **Field overrides** — override specific column values (e.g. `created_by`, tenant IDs) via JSON.
- **CLI** — automate transfers in CI/CD pipelines or support scripts.
- **IntelliJ Plugin** — built-in tool window for all JetBrains IDEs. No Python needed.
- **Encrypted connection store** — passwords encrypted with a machine-specific key (Fernet + PBKDF2). Never stored in plain text.
- **Transfer history** — every run logged with status, row counts, duration, and a detailed log file. Shared between desktop app and plugin.

---

## Direction Rules

| Direction | Status | | Direction | Status |
|---|---|---|---|---|
| PROD → TEST | ✅ | | LOCAL → PROD | ⛔ |
| PROD → LOCAL | ✅ | | TEST → PROD | ⛔ |
| TEST → LOCAL | ✅ | | LOCAL → TEST | ⛔ |
| PROD → STAGING | ✅ | | STAGING → PROD | ⛔ |

Custom environments (STAGING, QA, DEV, etc.) are supported — direction is determined by rank, not hardcoded names.

---

## Installation

### Desktop App (recommended)

Download the binary for your OS from [Releases](../../releases), extract, and run. No installation required.

| OS | File |
|---|---|
| 🪟 Windows | `RecordRelay-windows.zip` |
| 🍎 macOS | `RecordRelay-macos.zip` |
| 🐧 Linux | `RecordRelay-linux.tar.gz` |

> **Note:** On first launch, Windows SmartScreen or macOS Gatekeeper may warn about an unsigned app. Click "Run anyway" / "Open anyway" to proceed.

### IntelliJ Plugin

Install **RecordRelay** from the [JetBrains Marketplace](https://plugins.jetbrains.com/) or install from disk:

1. `Settings → Plugins → ⚙ → Install Plugin from Disk`
2. Select `recordrelay-plugin-3.0.0.zip` from the [Releases](../../releases) page.

Works in IntelliJ IDEA, PyCharm, WebStorm, DataGrip, and all JetBrains IDEs (2024.1+).

### CLI

```bash
pip install -r requirements.txt
python cli.py transfer \
  --source-id <uuid> --target-id <uuid> \
  --record-id 42 --root-table orders --fk-column order_id
```

```bash
python cli.py connections list
python cli.py history --limit 20
```

### Run from source

```bash
pip install -r requirements.txt
python main.py
```

Python 3.9+ required.

---

## Quick Start

1. **Connections** tab → add your databases (host, port, DB name, user, password, environment).
2. **Profiles** tab → create a transfer profile (root table + FK column), or use a built-in.
3. **Transfer** tab → select source and target, pick a profile, enter the record ID.
4. Optionally enable **Dry Run** to preview without writing.
5. Click **Start Transfer**. Watch the live log.
6. **History** tab → review past runs, open detailed log files.

---

## Architecture

```
app/
  core/
    environments.py   # configurable env registry + direction rules
    adapters.py       # PostgreSQL + MySQL DB adapters
    store.py          # encrypted connection store (Fernet + PBKDF2)
    profiles.py       # transfer profile CRUD
    engine.py         # generic transfer engine (root_table / fk_column / record_id)
    monitoring.py     # run history + per-transfer log files
  ui/
    main_window.py    connections_view.py  transfer_view.py
    transfer_worker.py  monitoring_view.py  profiles_view.py
    theme.py  icons.py  widgets.py

plugin/               # IntelliJ Platform Plugin (Kotlin + JDBC)
  src/main/kotlin/io/recordrelay/
    core/             # Environment, Connection, TransferEngine, TransferProfile
    store/            # ConnectionStore (PasswordSafe), ProfileStore
    ui/panels/        # TransferPanel, ConnectionsPanel, ProfilesPanel, HistoryPanel
    ui/dialogs/       # ConnectionDialog, ProfileDialog

cli.py                # typer CLI
tests/                # direction rules + encrypted store tests
.github/workflows/    # CI + Release automation
```

## Data Location

```
~/.recordrelay/
  connections.enc     # encrypted connection definitions
  profiles.enc        # encrypted transfer profiles
  environments.json   # custom environment definitions
  .salt / .machine    # machine-specific key derivation
  history.jsonl       # run history (shared between desktop app and plugin)
  logs/               # per-transfer detailed logs
```

---

## Development

```bash
# Run tests
pytest tests/ -v

# Build desktop app
./scripts/build.sh           # macOS / Linux
.\scripts\build.ps1          # Windows

# Build IntelliJ plugin
cd plugin && ./gradlew buildPlugin
# Output: plugin/build/distributions/recordrelay-plugin-3.0.0.zip
```

Release a new version by pushing a version tag:

```bash
git tag v3.0.0
git push origin v3.0.0
```

GitHub Actions builds all three OS packages and the IntelliJ plugin ZIP, then publishes a Release automatically.

---

<div align="center">
<sub>RecordRelay — Platform Engineering</sub>
</div>
