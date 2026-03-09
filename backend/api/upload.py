"""
ATLAS EDA — File Upload API
Handles single file or folder (multiple files) upload.
Supports adding more files to an existing session.
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
    for col in df.columns:
        if df[col].dtype == object:
            if any(k in col.lower() for k in ["date", "time", "created", "updated", "timestamp"]):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass
    return df


def _process_files(files: List[UploadFile], session):
    """Register files into a session, return results."""
    registered = []
    errors = []
    for file in files:
        try:
            df = _read_file(file)
            df = _infer_datetime_columns(df)
            table_name = session.register_table(file.filename, df)
            registered.append({
                "original_filename": file.filename,
                "table_name": table_name,
                "row_count": len(df),
                "column_count": len(df.columns),
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    return registered, errors


@router.post("/")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Initial upload — creates a new session and registers all files.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    session_id = str(uuid.uuid4())
    session = create_session(session_id)

    registered, errors = _process_files(files, session)

    if not registered:
        delete_session(session_id)
        raise HTTPException(status_code=400, detail=f"No files could be processed: {errors}")

    schemas = get_all_schemas(session)
    relationships = detect_relationships(session) if len(registered) > 1 else None
    profiles = {item["table_name"]: profile_table(session, item["table_name"]) for item in registered}

    return {
        "session_id": session_id,
        "tables": registered,
        "errors": errors,
        "schemas": schemas,
        "profiles": profiles,
        "relationships": relationships,
        "message": f"Successfully loaded {len(registered)} table(s)",
    }


@router.post("/{session_id}/add")
async def add_files(session_id: str, files: List[UploadFile] = File(...)):
    """
    Add more files to an existing session without losing current tables or chat history.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new session.")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    registered, errors = _process_files(files, session)

    if not registered:
        raise HTTPException(status_code=400, detail=f"No files could be processed: {errors}")

    # Re-profile all tables including new ones
    schemas = get_all_schemas(session)
    relationships = detect_relationships(session) if len(session.list_tables()) > 1 else None
    new_profiles = {item["table_name"]: profile_table(session, item["table_name"]) for item in registered}

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
