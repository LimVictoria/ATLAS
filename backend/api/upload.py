"""
ATLAS EDA — File Upload API
Fast upload: skip per-table charts on initial load, fetch on demand.
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
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                return pd.read_csv(io.BytesIO(content), encoding=enc, low_memory=False)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode {filename}")
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


def _fast_profile(session, table_name: str) -> dict:
    """
    Fast profile — no charts, just column stats.
    Charts are fetched on demand via /upload/{session_id}/charts/{table_name}
    """
    try:
        import numpy as np
        from scipy import stats as scipy_stats

        df = session.tables.get(table_name)
        if df is None:
            return {"error": f"Table {table_name} not found"}

        total_rows = len(df)
        profile = {
            "table": table_name,
            "row_count": total_rows,
            "column_count": len(df.columns),
            "duplicate_rows": int(df.duplicated().sum()),
            "columns": {},
            "charts": {},  # empty — loaded on demand
        }

        for col in df.columns:
            series = df[col]
            dtype_str = str(series.dtype)
            unique_count = int(series.nunique())
            null_pct = round(series.isnull().mean() * 100, 2)

            # Cardinality
            if "datetime" in dtype_str:
                cardinality = "date"
            elif "float" in dtype_str or "int" in dtype_str:
                cardinality = "numeric"
            else:
                pct = unique_count / max(total_rows, 1)
                if pct > 0.95:
                    cardinality = "id"
                elif pct > 0.5:
                    cardinality = "freetext"
                else:
                    cardinality = "categorical"

            col_profile = {
                "dtype": dtype_str,
                "null_count": int(series.isnull().sum()),
                "null_pct": null_pct,
                "unique_count": unique_count,
                "cardinality": cardinality,
            }

            if cardinality == "numeric":
                clean = series.dropna()
                if len(clean) > 0:
                    z_scores = np.abs(scipy_stats.zscore(clean))
                    outlier_count = int((z_scores > 3).sum())
                    col_profile.update({
                        "min": float(clean.min()),
                        "max": float(clean.max()),
                        "mean": round(float(clean.mean()), 4),
                        "median": round(float(clean.median()), 4),
                        "std": round(float(clean.std()), 4),
                        "outlier_count": outlier_count,
                        "outlier_pct": round(outlier_count / len(clean) * 100, 2),
                    })
            elif cardinality == "categorical":
                counts = series.value_counts(normalize=True).head(8)
                col_profile["frequencies"] = [
                    {"value": str(k), "pct": round(float(v) * 100, 1)}
                    for k, v in counts.items()
                ]
            elif cardinality == "date":
                clean = series.dropna()
                if len(clean) > 0:
                    col_profile.update({
                        "min_date": str(clean.min()),
                        "max_date": str(clean.max()),
                        "date_range_days": (clean.max() - clean.min()).days,
                    })

            profile["columns"][col] = col_profile

        return profile
    except Exception as e:
        return {"table": table_name, "error": str(e), "columns": {}, "charts": {}}


@router.post("/")
async def upload_files(files: List[UploadFile] = File(...)):
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
        delete_session(session_id)
        raise HTTPException(status_code=400,
            detail=f"No files could be processed: {[e['error'] for e in errors]}")

    schemas = get_all_schemas(session)
    # Fast profile — no charts
    profiles = {item["table_name"]: _fast_profile(session, item["table_name"]) for item in registered}
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


@router.get("/{session_id}/charts/{table_name}")
async def get_table_charts(session_id: str, table_name: str, col: str = None):
    """
    On-demand chart generation. Called when user clicks a column or expands a table.
    col = specific column to chart. If None, picks best numeric column.
    """
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    df = session.tables.get(table_name)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found")

    import json
    import numpy as np
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.utils

    charts = {}
    chart_layout = dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font=dict(color="#0f172a", family="IBM Plex Sans, sans-serif", size=11),
        margin=dict(t=36, r=16, b=48, l=52),
        height=240,
    )

    numeric_cols = [c for c in df.columns
                    if "float" in str(df[c].dtype) or "int" in str(df[c].dtype)]
    categorical_cols = [c for c in df.columns
                        if df[c].dtype == object and df[c].nunique() / len(df) < 0.5]

    # If specific column requested
    if col and col in df.columns:
        dtype = str(df[col].dtype)
        if "float" in dtype or "int" in dtype:
            fig = px.histogram(df, x=col, nbins=30,
                               color_discrete_sequence=["#0284c7"],
                               title=f"Distribution — {col}")
            fig.update_layout(**chart_layout)
            fig.update_traces(marker_line_width=0)
            charts["selected"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        elif df[col].dtype == object:
            counts = df[col].value_counts().head(15).reset_index()
            counts.columns = [col, "count"]
            fig = px.bar(counts, x="count", y=col, orientation="h",
                         color_discrete_sequence=["#059669"],
                         title=f"Top values — {col}")
            fig.update_layout(**{**chart_layout, "height": max(240, len(counts) * 28 + 80)})
            charts["selected"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    else:
        # Auto: pick highest-std numeric
        if numeric_cols:
            best = max(numeric_cols, key=lambda c: df[c].std() if not np.isnan(df[c].std()) else 0)
            fig = px.histogram(df, x=best, nbins=30,
                               color_discrete_sequence=["#0284c7"],
                               title=f"Distribution — {best}")
            fig.update_layout(**chart_layout)
            fig.update_traces(marker_line_width=0)
            charts["auto"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        elif categorical_cols:
            col0 = categorical_cols[0]
            counts = df[col0].value_counts().head(15).reset_index()
            counts.columns = [col0, "count"]
            fig = px.bar(counts, x="count", y=col0, orientation="h",
                         color_discrete_sequence=["#059669"],
                         title=f"Top values — {col0}")
            fig.update_layout(**{**chart_layout, "height": max(240, len(counts) * 28 + 80)})
            charts["auto"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Correlation heatmap
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr().round(2)
        base = {k: v for k, v in chart_layout.items() if k != "height"}
        fig_corr = go.Figure(data=go.Heatmap(
            z=corr.values.tolist(), x=list(corr.columns), y=list(corr.index),
            colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
            text=corr.values.round(2).tolist(),
            texttemplate="%{text}", textfont={"size": 10}, showscale=True,
        ))
        fig_corr.update_layout(title="Correlation Matrix", **base,
                               height=max(240, len(numeric_cols) * 45 + 80))
        charts["correlation"] = json.dumps(fig_corr, cls=plotly.utils.PlotlyJSONEncoder)

    # Null heatmap
    null_cols = [c for c in df.columns if df[c].isnull().any()]
    if null_cols:
        sample = df[null_cols].isnull().astype(int)
        if len(sample) > 200:
            sample = sample.sample(200, random_state=42).reset_index(drop=True)
        base = {k: v for k, v in chart_layout.items() if k != "height"}
        fig_null = go.Figure(data=go.Heatmap(
            z=sample.values.tolist(), x=list(sample.columns),
            colorscale=[[0, "#f0fdf4"], [1, "#dc2626"]],
            showscale=False, zmin=0, zmax=1,
        ))
        fig_null.update_layout(title="Missing Value Map (red = null)", **base,
                               height=260, xaxis=dict(tickangle=-30))
        charts["nullmap"] = json.dumps(fig_null, cls=plotly.utils.PlotlyJSONEncoder)

    return {"table_name": table_name, "charts": charts}


@router.post("/{session_id}/add")
async def add_files(session_id: str, files: List[UploadFile] = File(...)):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

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
        raise HTTPException(status_code=400,
            detail=f"No files could be processed: {[e['error'] for e in errors]}")

    schemas = get_all_schemas(session)
    relationships = detect_relationships(session) if len(session.list_tables()) > 1 else None
    new_profiles = {item["table_name"]: _fast_profile(session, item["table_name"]) for item in registered}

    return {
        "session_id": session_id,
        "new_tables": registered,
        "all_tables": session.list_tables(),
        "errors": errors,
        "schemas": schemas,
        "new_profiles": new_profiles,
        "relationships": relationships,
        "message": f"Added {len(registered)} new table(s)",
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
