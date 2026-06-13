"""
DevStat SQLite persistence module.

Replaces JSON-based persistence with a thread-safe SQLite backend.
Uses WAL mode for concurrent read/write performance.
All tables are created automatically on first import.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Schema DDL — all tables created in one go
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    version     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS datasets (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    name        TEXT NOT NULL,
    source      TEXT DEFAULT '',
    rows        INTEGER DEFAULT 0,
    cols        INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variables (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id      TEXT NOT NULL REFERENCES datasets(id),
    name            TEXT NOT NULL,
    index           INTEGER NOT NULL,
    type            TEXT DEFAULT '',
    width           INTEGER DEFAULT 0,
    decimals        INTEGER DEFAULT 0,
    label           TEXT DEFAULT '',
    align           TEXT DEFAULT '',
    measure         TEXT DEFAULT '',
    role            TEXT DEFAULT '',
    missing_values  TEXT DEFAULT '',
    UNIQUE(dataset_id, name)
);

CREATE TABLE IF NOT EXISTS value_labels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    variable_id INTEGER NOT NULL REFERENCES variables(id),
    key         TEXT NOT NULL,
    label       TEXT DEFAULT '',
    UNIQUE(variable_id, key)
);

CREATE TABLE IF NOT EXISTS data_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id  TEXT NOT NULL REFERENCES datasets(id),
    path        TEXT DEFAULT '',
    format      TEXT DEFAULT '',
    rows        INTEGER DEFAULT 0,
    file_size   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    dataset_id  TEXT NOT NULL REFERENCES datasets(id),
    module      TEXT DEFAULT '',
    label       TEXT DEFAULT '',
    params      TEXT DEFAULT '',
    r_code      TEXT DEFAULT '',
    result_hash TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS results (
    id          TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(id),
    type        TEXT DEFAULT '',
    format      TEXT DEFAULT '',
    content     TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS output_catalog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    analysis_id TEXT NOT NULL REFERENCES analyses(id),
    section     TEXT DEFAULT '',
    sort_order  INTEGER DEFAULT 0,
    visible     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS config (
    key        TEXT PRIMARY KEY,
    value      TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    """SQLite persistence layer for DevStat.

    Usage
    -----
    >>> db = Database()
    >>> proj = db.create_project('My Project')
    >>> db.close()
    """

    def __init__(self, db_path: Optional[str] = None):
        """Connect to the SQLite database, enabling WAL mode.

        Parameters
        ----------
        db_path : str, optional
            Full path to the SQLite file. Defaults to
            ``C:\\DevStat\\data\\devstat.db``.
        """
        if db_path is None:
            # Resolve relative to project root — portable across machines
            _db_dir = Path(__file__).resolve().parent.parent.parent / "data"
            _db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(_db_dir / "devstat.db")

        self._db_path = Path(db_path)

        # Ensure the parent directory exists
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"[database] Failed to create directory "
                  f"'{self._db_path.parent}': {exc}")
            raise

        # Connect and enable WAL mode + foreign keys
        try:
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            print(f"[database] Failed to connect to '{self._db_path}': {exc}")
            raise

        # Create all tables
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Execute the full schema DDL."""
        try:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()
        except sqlite3.Error as exc:
            print(f"[database] Schema creation failed: {exc}")
            self._conn.rollback()
            raise

    @staticmethod
    def _new_id() -> str:
        """Return a fresh UUID4 string."""
        return str(uuid.uuid4())

    @staticmethod
    def _now() -> str:
        """Return an ISO-8601 UTC timestamp string."""
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[dict]:
        """Convert an :class:`sqlite3.Row` to a plain dictionary."""
        if row is None:
            return None
        return dict(row)

    def _rows_to_list(self, rows: list[sqlite3.Row]) -> list[dict]:
        """Convert a list of :class:`sqlite3.Row` to a list of dicts."""
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(self, name: str, description: str = "") -> dict:
        """Insert a new project and return its row as a dict."""
        project_id = self._new_id()
        now = self._now()
        try:
            self._conn.execute(
                """INSERT INTO projects
                   (id, name, description, created_at, updated_at, version)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (project_id, name, description, now, now),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            print(f"[database] create_project failed: {exc}")
            self._conn.rollback()
            raise
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> Optional[dict]:
        """Return a single project dict, or None."""
        try:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return self._row_to_dict(row)
        except sqlite3.Error as exc:
            print(f"[database] get_project failed: {exc}")
            return None

    def list_projects(self) -> list[dict]:
        """Return all projects."""
        try:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            return self._rows_to_list(rows)
        except sqlite3.Error as exc:
            print(f"[database] list_projects failed: {exc}")
            return []

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    def save_dataset(
        self,
        project_id: str,
        name: str,
        source: str = "",
        rows: int = 0,
        cols: int = 0,
    ) -> str:
        """Insert a dataset row and return the new dataset ID."""
        ds_id = self._new_id()
        now = self._now()
        try:
            self._conn.execute(
                """INSERT INTO datasets
                   (id, project_id, name, source, rows, cols, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ds_id, project_id, name, source, rows, cols, now),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            print(f"[database] save_dataset failed: {exc}")
            self._conn.rollback()
            raise
        return ds_id

    # ------------------------------------------------------------------
    # Variables & value labels
    # ------------------------------------------------------------------

    def save_variable(
        self, dataset_id: str, name: str, index: int, **kwargs: Any
    ) -> dict:
        """Insert or ignore a variable row and return its row as a dict.

        Accepts any of the following keyword arguments: type, width,
        decimals, label, align, measure, role, missing_values.
        """
        fields = {
            "type": kwargs.get("type", ""),
            "width": kwargs.get("width", 0),
            "decimals": kwargs.get("decimals", 0),
            "label": kwargs.get("label", ""),
            "align": kwargs.get("align", ""),
            "measure": kwargs.get("measure", ""),
            "role": kwargs.get("role", ""),
            "missing_values": kwargs.get("missing_values", ""),
        }
        try:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO variables
                   (dataset_id, name, index, type, width, decimals,
                    label, align, measure, role, missing_values)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    dataset_id,
                    name,
                    index,
                    fields["type"],
                    fields["width"],
                    fields["decimals"],
                    fields["label"],
                    fields["align"],
                    fields["measure"],
                    fields["role"],
                    fields["missing_values"],
                ),
            )
            self._conn.commit()

            # Fetch the row we just inserted (or the existing one)
            row = self._conn.execute(
                "SELECT * FROM variables WHERE dataset_id = ? AND name = ?",
                (dataset_id, name),
            ).fetchone()
            return self._row_to_dict(row)
        except sqlite3.Error as exc:
            print(f"[database] save_variable failed: {exc}")
            self._conn.rollback()
            raise

    def save_value_label(self, variable_id: int, key: str, label: str) -> dict:
        """Insert or ignore a value-label pair and return its row as dict."""
        try:
            self._conn.execute(
                """INSERT OR IGNORE INTO value_labels
                   (variable_id, key, label)
                   VALUES (?, ?, ?)""",
                (variable_id, key, label),
            )
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM value_labels WHERE variable_id = ? AND key = ?",
                (variable_id, key),
            ).fetchone()
            return self._row_to_dict(row)
        except sqlite3.Error as exc:
            print(f"[database] save_value_label failed: {exc}")
            self._conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Analyses & results
    # ------------------------------------------------------------------

    def save_analysis(
        self,
        project_id: str,
        dataset_id: str,
        module: str = "",
        label: str = "",
        params: str = "",
        r_code: str = "",
    ) -> str:
        """Insert an analysis row and return its ID."""
        analysis_id = self._new_id()
        now = self._now()
        try:
            self._conn.execute(
                """INSERT INTO analyses
                   (id, project_id, dataset_id, module, label,
                    params, r_code, created_at, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (analysis_id, project_id, dataset_id, module,
                 label, params, r_code, now),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            print(f"[database] save_analysis failed: {exc}")
            self._conn.rollback()
            raise
        return analysis_id

    def save_result(
        self,
        analysis_id: str,
        type_: str,
        format_: str,
        content: str,
    ) -> dict:
        """Insert a result row and return its dict."""
        result_id = self._new_id()
        now = self._now()
        try:
            self._conn.execute(
                """INSERT INTO results
                   (id, analysis_id, type, format, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (result_id, analysis_id, type_, format_, content, now),
            )
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM results WHERE id = ?", (result_id,)
            ).fetchone()
            return self._row_to_dict(row)
        except sqlite3.Error as exc:
            print(f"[database] save_result failed: {exc}")
            self._conn.rollback()
            raise

    def get_analysis_history(self, dataset_id: str) -> list[dict]:
        """Return all analyses for a dataset, newest first."""
        try:
            rows = self._conn.execute(
                """SELECT * FROM analyses
                   WHERE dataset_id = ?
                   ORDER BY created_at DESC""",
                (dataset_id,),
            ).fetchall()
            return self._rows_to_list(rows)
        except sqlite3.Error as exc:
            print(f"[database] get_analysis_history failed: {exc}")
            return []

    def get_analysis(self, analysis_id: str) -> Optional[dict]:
        """Return an analysis dict with its results nested under 'results'.

        Returns None if the analysis does not exist.
        """
        try:
            row = self._conn.execute(
                "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
            ).fetchone()
            if row is None:
                return None
            analysis = dict(row)

            # Attach results
            result_rows = self._conn.execute(
                "SELECT * FROM results WHERE analysis_id = ? ORDER BY created_at",
                (analysis_id,),
            ).fetchall()
            analysis["results"] = self._rows_to_list(result_rows)
            return analysis
        except sqlite3.Error as exc:
            print(f"[database] get_analysis failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def get_config(self, key: str) -> Optional[str]:
        """Return the value for *key*, or None."""
        try:
            row = self._conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None
        except sqlite3.Error as exc:
            print(f"[database] get_config failed: {exc}")
            return None

    def set_config(self, key: str, value: str) -> None:
        """Upsert a config key/value pair."""
        now = self._now()
        try:
            self._conn.execute(
                """INSERT INTO config (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value      = excluded.value,
                       updated_at = excluded.updated_at""",
                (key, value, now),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            print(f"[database] set_config failed: {exc}")
            self._conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        try:
            self._conn.close()
        except sqlite3.Error as exc:
            print(f"[database] close failed: {exc}")

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc_args) -> None:
        self.close()
