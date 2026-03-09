import duckdb
import pandas as pd
from typing import Optional


class DuckDBSession:
    """
    In-memory DuckDB session for EDA.
    Each upload session gets its own isolated DuckDB instance.
    Tables are registered from uploaded DataFrames.
    """

    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self.tables: dict[str, pd.DataFrame] = {}

    def register_table(self, name: str, df: pd.DataFrame):
        """Register a DataFrame as a queryable DuckDB table."""
        clean_name = name.replace(".csv", "").replace(".xlsx", "").replace(".parquet", "").replace("-", "_").replace(" ", "_")
        self.tables[clean_name] = df
        self.conn.register(clean_name, df)
        return clean_name

    def query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return DataFrame."""
        return self.conn.execute(sql).df()

    def list_tables(self) -> list[str]:
        return list(self.tables.keys())

    def get_schema(self, table_name: str) -> dict:
        """Return schema info for a table."""
        df = self.tables.get(table_name)
        if df is None:
            return {}
        return {
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "row_count": len(df),
            "sample": df.head(3).to_dict(orient="records"),
        }

    def close(self):
        self.conn.close()


# Session store — keyed by session_id
# In production, replace with Redis
_sessions: dict[str, DuckDBSession] = {}


def get_session(session_id: str) -> Optional[DuckDBSession]:
    return _sessions.get(session_id)


def create_session(session_id: str) -> DuckDBSession:
    session = DuckDBSession()
    _sessions[session_id] = session
    return session


def delete_session(session_id: str):
    session = _sessions.pop(session_id, None)
    if session:
        session.close()
