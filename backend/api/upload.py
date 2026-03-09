"""
ATLAS EDA — File Upload API
Handles single file or folder (multiple files) upload.
Registers all files into a DuckDB session.
Returns immediate schema profile.
"""

import uuid
import io
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List

from db.duckdb_session import create_session, delete_session, get_session
from agent.tools import get_all_schemas, detect_relationships, profile_table

router = APIRouter(prefix="/upload", tags=["upload"])


def _read_file(file: UploadFile) -> pd.DataFrame:
    """Read uploaded file into DataFrame regardless of format."""
    filename = file.filename.lower()
    content = file.file.read()

    if filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    elif filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    elif filename.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(content))
    elif filename.endswith(".json"):
        return pd.read_json(io.BytesIO(content))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {filename}")


def _infer_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Try to parse columns that look like dates."""
    for col in df.columns:
        if df[col].dtype == object:
            if any(k in col.lower() for k in ["date", "time", "created", "updated", "timestamp"]):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
    return df


@router.post("/")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload one or more files.
    Creates a new DuckDB session and registers all files as tables.
    Returns session_id + immediate schema profile for all tables.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    session_id = str(uuid.uuid4())
    session = create_session(session_id)

    registered_tables = []
    errors = []

    for file in files:
        try:
            df = _read_file(file)
            df = _infer_datetime_columns(df)
            table_name = session.register_table(file.filename, df)
            registered_tables.append({
                "original_filename": file.filename,
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    if not registered_tables:
        delete_session(session_id)
        raise HTTPException(status_code=400, detail=f"No files could be processed: {errors}")

    # Generate immediate profile for all tables
    schemas = get_all_schemas(session)

    # Detect relationships if multiple tables
    relationships = None
    if len(registered_tables) > 1:
        relationships = detect_relationships(session)

    # Generate per-table quality profile
    profiles = {}
    for item in registered_tables:
        profiles[item["table_name"]] = profile_table(session, item["table_name"])

    return {
        "session_id": session_id,
        "tables": registered_tables,
        "errors": errors,
        "schemas": schemas,
        "profiles": profiles,
        "relationships": relationships,
        "message": f"Successfully loaded {len(registered_tables)} table(s)",
    }


@router.delete("/{session_id}")
async def close_session(session_id: str):
    """Clean up a DuckDB session when user is done."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"message": "Session closed"}


@router.get("/{session_id}/tables")
async def list_tables(session_id: str):
    """List all tables in a session."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"tables": session.list_tables()}
