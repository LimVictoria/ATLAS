"""
ATLAS EDA — File Upload API
Processes files one at a time to avoid memory/timeout issues on free tier.
"""

import uuid
import io
import traceback
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List

from db.duckdb_session import create_session, delete_session, get_session
from agent.tools import get_all_schemas, detect_relationships, profile_table

router = APIRouter(prefix="/upload", tags=["upload"])


def _read_file(content: bytes, filename: str) -> pd.DataFrame:
    fname = filename.lower()
    if fname.endswith(".csv"):
        # Try common encodings
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                return pd.read_csv(io.BytesIO(content), encoding=enc, low_memory=False)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode {filename} with any supported encoding")
    elif fname.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content))
    elif fname.endswith(".parquet"):
        return pd.read_parquet(io.BytesIO(content))
    elif fname.endswith(".json"):
        return pd.read_json(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def _infer_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == object:
            if any(k in col.lower() for k in ["date", "time", "created", "updated", "timestamp"]):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
    return df


def _safe_profile(session, table_name: str) -> dict:
    """Profile a table, return error dict instead of crashing if it fails."""
    try:
        return profile_table(session, table_name)
    except Exception as e:
        return {"table": table_name, "error": str(e), "columns": {}, "charts": {}}


@router.post("/")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload multiple CSV files. Processes one at a time to stay within memory limits.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    session_id = str(uuid.uuid4())
    session = create_session(session_id)

    registered = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            if len(content) == 0:
                errors.append({"filename": file.filename, "error": "File is empty"})
                continue

            df = _read_file(content, file.filename)
            df = _infer_datetime_columns(df)

            # Trim very large files to first 50k rows to stay within memory
            if len(df) > 50000:
                df = df.head(50000)

            table_name = session.register_table(file.filename, df)
            registered.append({
                "original_filename": file.filename,
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
            })
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e),
                "detail": traceback.format_exc()
            })

    if not registered:
        delete_session(session_id)
        raise HTTPException(
            status_code=400,
            detail=f"No files could be processed. Errors: {[e['error'] for e in errors]}"
        )

    # Profile each table individually (lazy — less memory spike)
    schemas = get_all_schemas(session)
    profiles = {item["table_name"]: _safe_profile(session, item["table_name"]) for item in registered}
    relationships = detect_relationships(session) if len(registered) > 1 else None

    return {
        "session_id": session_id,
        "tables": registered,
        "errors": errors,
        "schemas": schemas,
        "profiles": profiles,
        "relationships": relationships,
        "message": f"Successfully loaded {len(registered)} of {len(files)} file(s)",
    }


@router.post("/{session_id}/add")
async def add_files(session_id: str, files: List[UploadFile] = File(...)):
    """Add more files to an existing session."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    registered = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            if len(content) == 0:
                errors.append({"filename": file.filename, "error": "File is empty"})
                continue

            df = _read_file(content, file.filename)
            df = _infer_datetime_columns(df)

            if len(df) > 50000:
                df = df.head(50000)

            table_name = session.register_table(file.filename, df)
            registered.append({
                "original_filename": file.filename,
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    if not registered:
        raise HTTPException(
            status_code=400,
            detail=f"No files could be processed: {[e['error'] for e in errors]}"
        )

    schemas = get_all_schemas(session)
    relationships = detect_relationships(session) if len(session.list_tables()) > 1 else None
    new_profiles = {item["table_name"]: _safe_profile(session, item["table_name"]) for item in registered}

    return {
        "session_id": session_id,
        "new_tables": registered,
        "all_tables": session.list_tables(),
        "errors": errors,
        "schemas": schemas,
        "new_profiles": new_profiles,
        "relationships": relationships,
        "message": f"Added {len(registered)} new table(s) to session",
    }


@router.delete("/{session_id}")
async def close_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"message": "Session closed"}


@router.get("/{session_id}/tables")
async def list_tables(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"tables": session.list_tables()}
