"""Ejecucion segura de consultas SELECT contra data/ventas.db."""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ventas.db"
TABLE_NAME = "ventas"


def run_query(sql: str) -> pd.DataFrame:
    """Abre la base de datos en modo solo-lectura y ejecuta el SELECT ya validado."""
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        return pd.read_sql_query(sql, conn)
