"""
Data import service for DevStat.

Handles importing structured data from multiple file formats (CSV, Excel, SPSS)
into pandas DataFrames with proper encoding detection, delimiter detection, and
metadata extraction (variable labels, value labels, column statistics).
"""

from __future__ import annotations

import io
import os
import csv as csv_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import chardet


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# Common NA value representations across many CSV exports.
_NA_VALUES: set[str] = {
    "",
    "NA",
    "N/A",
    "N.A.",
    "n/a",
    "n.a.",
    "NULL",
    "null",
    "NaN",
    "nan",
    "NaT",
    "None",
    "none",
    "--",
    ".",
    "?",
}


def _detect_encoding(file_path: str) -> str:
    """Detect the encoding of a file using chardet.

    Falls back to ``utf-8`` if detection is inconclusive.
    """
    # Read a sample (up to 1 MiB) for charset detection.
    sample_size = 1024 * 1024
    with open(file_path, "rb") as fh:
        raw = fh.read(sample_size)

    result = chardet.detect(raw)
    encoding: str = result.get("encoding") or "utf-8"

    # Normalise common aliases.
    encoding = encoding.lower().replace("-", "_")

    if encoding in ("ascii", "iso_8859_1", "iso8859_1", "latin1", "latin_1"):
        return "latin-1"
    if encoding.startswith("utf"):
        return "utf-8"
    if encoding in ("windows_1252", "cp1252"):
        return "cp1252"

    return encoding


def _detect_delimiter(file_path: str) -> str:
    """Auto-detect the delimiter of a CSV-like text file.

    Uses Python's ``csv.Sniffer`` on the first few kilobytes.  Falls back
    to comma if detection fails.
    """
    sample_size = 8192
    with open(file_path, "rb") as fh:
        raw = fh.read(sample_size)

    # csv.Sniffer needs text.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            return ","

    try:
        dialect = csv_module.Sniffer().sniff(text, delimiters=",;\t|:")
        return dialect.delimiter
    except csv_module.Error:
        return ","


def _infer_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce string columns that look numeric back to numbers.

    ``pd.read_csv(…, dtype_backend="pyarrow")`` or ``convert_dtypes()``
    sometimes leaves numeric-looking data as strings when there are mixed
    types or NA markers in the column.  This helper tries a safe numeric
    conversion per object column.
    """
    for col in df.columns:
        if df[col].dtype == object:
            # Attempt numeric coercion on a sample (skip all-NA columns).
            sample = df[col].dropna().head(100)
            if len(sample) == 0:
                continue
            try:
                pd.to_numeric(sample)
            except (ValueError, TypeError):
                continue  # keep as object / string
            # Full column coercion — coerce errors → NaN so non-numeric
            # entries become missing rather than raising.
            converted = pd.to_numeric(df[col], errors="coerce")
            # Only apply if a meaningful fraction was convertible (>80%).
            non_null_orig = df[col].notna().sum()
            non_null_new = converted.notna().sum()
            if non_null_orig > 0 and (non_null_new / non_null_orig) >= 0.8:
                df[col] = converted
    return df


def _infer_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Try to parse object columns as datetime.

    For each object column, attempt ``pd.to_datetime`` on a sample.  If the
    sample converts cleanly to datetime, convert the full column with
    ``errors='coerce'`` so unparseable entries become NaT.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        sample = df[col].dropna().head(100)
        if len(sample) == 0:
            continue
        try:
            converted_sample = pd.to_datetime(sample)
        except (ValueError, TypeError):
            continue
        # At least 80% of the sample must be parseable.
        valid_sample = converted_sample.notna().sum()
        if valid_sample / len(sample) < 0.8:
            continue
        # Full column conversion.
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def import_file(file_path: str) -> pd.DataFrame:
    """Detect file format by extension and delegate to the appropriate importer.

    Supported extensions:
        * ``.csv``  — comma/tab/pipe/semicolon separated values
        * ``.tsv``  — tab-separated values (handled as CSV)
        * ``.xlsx``, ``.xls`` — Excel workbooks (first sheet)
        * ``.sav`` — SPSS statistics data file
        * ``.dta`` — Stata data file

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the data file.

    Returns
    -------
    pd.DataFrame
        Data loaded into a DataFrame with optimised dtypes.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    ValueError
        If the file extension is not supported.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    importers = {
        ".csv": import_csv,
        ".tsv": import_csv,
        ".xlsx": import_excel,
        ".xls": import_excel,
        ".sav": import_sav,
        ".dta": import_dta,
    }

    importer = importers.get(suffix)
    if importer is None:
        raise ValueError(
            f"Unsupported file extension '{suffix}'. "
            f"Supported: {', '.join(sorted(importers))}"
        )

    return importer(file_path)


def import_csv(file_path: str) -> pd.DataFrame:
    """Import a CSV (or similarly delimited) file into a DataFrame.

    Automatically detects:
        * File encoding (via ``chardet``, falling back to ``utf-8``\ / ``latin-1``)
        * Delimiter (via ``csv.Sniffer``)
        * Standard NA value representations

    Parameters
    ----------
    file_path : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Loaded data.
    """
    encoding = _detect_encoding(file_path)
    delimiter = _detect_delimiter(file_path)

    try:
        df = pd.read_csv(
            file_path,
            delimiter=delimiter,
            encoding=encoding,
            na_values=_NA_VALUES,
            keep_default_na=True,
            low_memory=False,
            dtype_backend="numpy_nullable",
            engine="c",
        )
    except (UnicodeDecodeError, UnicodeError):
        # Fall back to latin-1 if the detected encoding was wrong.
        df = pd.read_csv(
            file_path,
            delimiter=delimiter,
            encoding="latin-1",
            na_values=_NA_VALUES,
            keep_default_na=True,
            low_memory=False,
            dtype_backend="numpy_nullable",
            engine="c",
        )

    # Strip whitespace from string columns and column names.
    df.columns = [str(c).strip() for c in df.columns]
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip().replace({"": None, "nan": None})

    df = _infer_dtypes(df)
    df = _infer_dates(df)
    return df


def import_excel(file_path: str) -> pd.DataFrame:
    """Import the first sheet of an Excel workbook into a DataFrame.

    Parameters
    ----------
    file_path : str
        Path to the ``.xlsx`` or ``.xls`` file.

    Returns
    -------
    pd.DataFrame
        Loaded data.
    """
    # ``engine`` is auto-selected based on file extension:
    #   ``.xlsx`` → ``openpyxl``, ``.xls`` → ``xlrd``
    df = pd.read_excel(
        file_path,
        sheet_name=0,                     # first sheet
        engine=None,                      # auto
        na_values=_NA_VALUES,
        keep_default_na=True,
        dtype_backend="numpy_nullable",
    )

    df.columns = [str(c).strip() for c in df.columns]
    df = _infer_dtypes(df)
    df = _infer_dates(df)
    return df


def import_sav(file_path: str) -> pd.DataFrame:
    """Import an SPSS ``.sav`` file into a DataFrame.

    Requires the ``pyreadstat`` package.  Variable labels and value labels
    are extracted and stored as attributes on the returned DataFrame so they
    can be surfaced later by :func:`get_column_info` and the API layer.

    Parameters
    ----------
    file_path : str
        Path to the ``.sav`` file.

    Returns
    -------
    pd.DataFrame
        Loaded data with optional metadata attributes:
        * ``df.attrs["variable_labels"]`` — ``dict[str, str]``
        * ``df.attrs["value_labels"]``   — ``dict[str, dict[Any, str]]``

    Raises
    ------
    ImportError
        If ``pyreadstat`` is not installed.
    """
    try:
        import pyreadstat
    except ImportError as exc:
        raise ImportError(
            "pyreadstat is required to import SPSS .sav files. "
            "Install it with: pip install pyreadstat"
        ) from exc

    df, meta = pyreadstat.read_sav(file_path, encoding="utf-8")

    # Store metadata on the DataFrame for downstream consumers.
    if meta.column_names_to_labels:
        df.attrs["variable_labels"] = meta.column_names_to_labels
    if meta.variable_value_labels:
        df.attrs["value_labels"] = meta.variable_value_labels

    df.columns = [str(c).strip() for c in df.columns]
    df = _infer_dtypes(df)
    df = _infer_dates(df)
    return df


def import_dta(file_path: str) -> pd.DataFrame:
    """Import a Stata ``.dta`` file into a DataFrame.

    Requires the ``pyreadstat`` package.  Variable labels and value labels
    are extracted and stored as attributes on the returned DataFrame.

    Parameters
    ----------
    file_path : str
        Path to the ``.dta`` file.

    Returns
    -------
    pd.DataFrame
        Loaded data with optional metadata attributes:
        * ``df.attrs["variable_labels"]`` — ``dict[str, str]``
        * ``df.attrs["value_labels"]``   — ``dict[str, dict[Any, str]]``

    Raises
    ------
    ImportError
        If ``pyreadstat`` is not installed.
    """
    try:
        import pyreadstat
    except ImportError as exc:
        raise ImportError(
            "pyreadstat is required to import Stata .dta files. "
            "Install it with: pip install pyreadstat"
        ) from exc

    df, meta = pyreadstat.read_dta(file_path, encoding="utf-8")

    # Store metadata on the DataFrame for downstream consumers.
    if meta.column_names_to_labels:
        df.attrs["variable_labels"] = meta.column_names_to_labels
    if meta.variable_value_labels:
        df.attrs["value_labels"] = meta.variable_value_labels

    df.columns = [str(c).strip() for c in df.columns]
    df = _infer_dtypes(df)
    df = _infer_dates(df)
    return df


# ---------------------------------------------------------------------------
# Column metadata
# ---------------------------------------------------------------------------


def get_column_info(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return per-column metadata for a DataFrame.

    Each element contains:

    .. code-block:: python

        {
            "name": str,           # column name
            "dtype": str,          # pandas dtype string
            "unique_count": int,   # number of unique non-null values
            "missing_count": int,  # number of null / NaN entries
            "missing_pct": float,  # percentage of values that are missing
            "is_numeric": bool,    # True for int/float/complex dtypes
            "is_categorical": bool,# True for categorical, object, or bool
                                   # with few unique values (<5% cardinality)
            "labels": dict | None, # SPSS value labels if available
        }

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to analyse.

    Returns
    -------
    list[dict]
        Column metadata list.
    """
    nrows = len(df)
    if nrows == 0:
        nrows = 1  # avoid division by zero for empty DataFrames

    # Pre-resolve numpy dtype families for speed.
    _ints = ("int", "uint")
    _floats = ("float", "complex")

    variable_labels: Optional[Dict[str, str]] = df.attrs.get("variable_labels")
    value_labels: Optional[Dict[str, Dict[Any, str]]] = df.attrs.get("value_labels")

    info: List[Dict[str, Any]] = []
    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        dtype_lower = dtype_str.lower()

        missing_count = int(series.isna().sum())
        missing_pct = round(missing_count / nrows * 100, 2)
        unique_count = int(series.nunique(dropna=True))

        # Numeric check: int, uint, float, complex families (including
        # nullable pandas types like Int64, Float64).
        is_numeric = (
            any(dtype_lower.startswith(p) for p in _ints)
            or any(dtype_lower.startswith(p) for p in _floats)
            or dtype_lower == "boolean"  # bool can be numeric-ish
        )

        # Categorical: explicit category dtype, bool, or object/string
        # columns with low cardinality (<5% unique values, capped at 50).
        is_categorical = False
        if dtype_lower == "category":
            is_categorical = True
        elif dtype_lower == "bool" or dtype_lower == "boolean":
            is_categorical = True
        elif dtype_lower == "object":
            # Heuristic: string columns with few unique values.
            if nrows > 0 and unique_count <= min(50, max(2, nrows // 20)):
                is_categorical = True

        # Look up SPSS value labels for this column.
        labels: Optional[Dict[str, str]] = None
        if value_labels is not None and col in value_labels:
            raw_labels = value_labels[col]
            # Ensure keys are strings for JSON serialisation.
            labels = {str(k): str(v) for k, v in raw_labels.items()}

        entry: Dict[str, Any] = {
            "name": col,
            "dtype": dtype_str,
            "unique_count": unique_count,
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "is_numeric": is_numeric,
            "is_categorical": is_categorical,
            "labels": labels,
        }

        # Include SPSS variable label as a display name hint.
        if variable_labels is not None and col in variable_labels:
            entry["variable_label"] = variable_labels[col]

        info.append(entry)

    return info
