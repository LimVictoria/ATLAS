"""
ATLAS EDA Agent Tools
Heavy imports are lazy-loaded to reduce startup memory usage.
"""

import json
import traceback
from typing import Any
from db.duckdb_session import DuckDBSession


def _df_to_plotly_json(fig) -> str:
    import plotly.utils
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def _safe_sample(df, n: int = 5) -> list[dict]:
    return df.head(n).replace({float("nan"): None}).to_dict(orient="records")


def _cardinality_label(unique: int, total: int, dtype: str) -> str:
    """Classify a column based on cardinality and dtype."""
    if "datetime" in dtype:
        return "date"
    if "float" in dtype or "int" in dtype:
        return "numeric"
    pct = unique / max(total, 1)
    if pct > 0.95:
        return "id"
    if pct > 0.5:
        return "freetext"
    return "categorical"


# ── Tool 1: Schema Loader ─────────────────────────────────────────────────────

def get_all_schemas(session: DuckDBSession) -> dict:
    result = {}
    for table in session.list_tables():
        df = session.tables[table]
        result[table] = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": {
                col: {
                    "dtype": str(df[col].dtype),
                    "null_pct": round(df[col].isnull().mean() * 100, 2),
                    "unique_count": int(df[col].nunique()),
                    "sample_values": df[col].dropna().head(3).tolist(),
                }
                for col in df.columns
            },
        }
    return result


# ── Tool 2: Rich Profile ──────────────────────────────────────────────────────

def profile_table(session: DuckDBSession, table_name: str) -> dict:
    import pandas as pd
    import numpy as np
    from scipy import stats

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
        "charts": {},
    }

    numeric_cols = []
    has_nulls = False

    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        unique_count = int(series.nunique())
        null_pct = round(series.isnull().mean() * 100, 2)
        if null_pct > 0:
            has_nulls = True

        cardinality = _cardinality_label(unique_count, total_rows, dtype_str)

        col_profile: dict[str, Any] = {
            "dtype": dtype_str,
            "null_count": int(series.isnull().sum()),
            "null_pct": null_pct,
            "unique_count": unique_count,
            "cardinality": cardinality,
        }

        # Numeric
        if cardinality == "numeric":
            numeric_cols.append(col)
            clean = series.dropna()
            if len(clean) > 0:
                z_scores = np.abs(stats.zscore(clean))
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

        # Categorical — frequency bars
        elif cardinality == "categorical":
            counts = series.value_counts(normalize=True).head(8)
            col_profile["frequencies"] = [
                {"value": str(k), "pct": round(float(v) * 100, 1)}
                for k, v in counts.items()
            ]

        # Date
        elif cardinality == "date":
            clean = series.dropna()
            if len(clean) > 0:
                col_profile.update({
                    "min_date": str(clean.min()),
                    "max_date": str(clean.max()),
                    "date_range_days": (clean.max() - clean.min()).days,
                })

        profile["columns"][col] = col_profile

    # ── Auto chart — pick most interesting numeric column ─────────────────────
    import plotly.express as px
    import plotly.graph_objects as go

    chart_layout = dict(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font=dict(color="#0f172a", family="IBM Plex Sans, sans-serif", size=11),
        margin=dict(t=36, r=16, b=48, l=52),
        height=220,
    )

    if numeric_cols:
        # Pick column with highest std (most interesting distribution)
        best_col = max(
            numeric_cols,
            key=lambda c: df[c].std() if not pd.isna(df[c].std()) else 0
        )
        fig = px.histogram(
            df, x=best_col,
            title=f"Distribution — {best_col}",
            color_discrete_sequence=["#0284c7"],
            nbins=30,
        )
        fig.update_layout(**chart_layout)
        fig.update_traces(marker_line_width=0)
        profile["charts"]["auto"] = json.dumps(fig, cls=__import__("plotly.utils", fromlist=["PlotlyJSONEncoder"]).PlotlyJSONEncoder)

    # ── Correlation heatmap ───────────────────────────────────────────────────
    if len(numeric_cols) >= 2:
        corr = df[numeric_cols].corr().round(2)
        fig_corr = go.Figure(data=go.Heatmap(
            z=corr.values.tolist(),
            x=list(corr.columns),
            y=list(corr.index),
            colorscale="RdBu",
            zmid=0, zmin=-1, zmax=1,
            text=corr.values.round(2).tolist(),
            texttemplate="%{text}",
            textfont={"size": 10},
            showscale=True,
        ))
        fig_corr.update_layout(
            title="Correlation Matrix",
            **chart_layout,
            height=max(220, len(numeric_cols) * 40 + 80),
        )
        profile["charts"]["correlation"] = json.dumps(fig_corr, cls=__import__("plotly.utils", fromlist=["PlotlyJSONEncoder"]).PlotlyJSONEncoder)

    # ── Null heatmap ──────────────────────────────────────────────────────────
    if has_nulls:
        # Sample up to 200 rows for visual
        sample = df.isnull().astype(int)
        if len(sample) > 200:
            sample = sample.sample(200, random_state=42).reset_index(drop=True)

        fig_null = go.Figure(data=go.Heatmap(
            z=sample.values.tolist(),
            x=list(sample.columns),
            colorscale=[[0, "#f0fdf4"], [1, "#dc2626"]],
            showscale=False,
            zmin=0, zmax=1,
        ))
        fig_null.update_layout(
            title="Missing Value Map  (red = null)",
            **chart_layout,
            height=240,
            xaxis=dict(tickangle=-30),
        )
        profile["charts"]["nullmap"] = json.dumps(fig_null, cls=__import__("plotly.utils", fromlist=["PlotlyJSONEncoder"]).PlotlyJSONEncoder)

    return profile


# ── Tool 3: Relationship Detector ─────────────────────────────────────────────

def detect_relationships(session: DuckDBSession) -> dict:
    tables = session.list_tables()
    relationships = []

    for i, t1 in enumerate(tables):
        for t2 in tables[i + 1:]:
            df1 = session.tables[t1]
            df2 = session.tables[t2]
            shared_cols = set(df1.columns) & set(df2.columns)

            for col in shared_cols:
                if col.lower() in ["id", "name", "date", "status"]:
                    continue
                vals1 = set(df1[col].dropna().unique())
                vals2 = set(df2[col].dropna().unique())
                if not vals1 or not vals2:
                    continue
                overlap = vals1 & vals2
                match_pct = len(overlap) / max(len(vals1), len(vals2)) * 100
                if match_pct > 50:
                    relationships.append({
                        "from_table": t1,
                        "to_table": t2,
                        "join_column": col,
                        "match_pct": round(match_pct, 1),
                        "orphaned_in_t1": len(vals1 - vals2),
                        "orphaned_in_t2": len(vals2 - vals1),
                        "suggested_join": f"LEFT JOIN {t2} ON {t1}.{col} = {t2}.{col}",
                    })

    return {
        "relationships_found": len(relationships),
        "relationships": sorted(relationships, key=lambda x: x["match_pct"], reverse=True),
    }


# ── Tool 4: Anomaly Detector ──────────────────────────────────────────────────

def detect_anomalies(session: DuckDBSession, table_name: str) -> dict:
    import pandas as pd
    import numpy as np
    from scipy import stats

    df = session.tables.get(table_name)
    if df is None:
        return {"error": f"Table {table_name} not found"}

    anomalies = []
    for col in df.columns:
        series = df[col].dropna()
        if pd.api.types.is_numeric_dtype(series) and len(series) > 10:
            z = np.abs(stats.zscore(series))
            outlier_idx = df.index[df[col].notna()][z > 3].tolist()
            if outlier_idx:
                anomalies.append({
                    "type": "statistical_outlier",
                    "column": col,
                    "count": len(outlier_idx),
                    "row_indices": outlier_idx[:10],
                    "threshold": "3 standard deviations",
                    "sample_values": df.loc[outlier_idx[:5], col].tolist(),
                })
            if col.lower() in ["cost", "price", "revenue", "amount", "weight", "distance"]:
                neg_count = int((series < 0).sum())
                if neg_count > 0:
                    anomalies.append({
                        "type": "impossible_negative",
                        "column": col,
                        "count": neg_count,
                        "message": f"{col} should not be negative",
                    })

    return {"table": table_name, "anomaly_count": len(anomalies), "anomalies": anomalies}


# ── Tool 5: Chart Generator ───────────────────────────────────────────────────

def generate_chart(session: DuckDBSession, table_name: str, chart_type: str,
                   x_col: str, y_col: str = None, color_col: str = None) -> str:
    import numpy as np
    import plotly.express as px

    df = session.tables.get(table_name)
    if df is None:
        return json.dumps({"error": f"Table {table_name} not found"})

    try:
        if chart_type == "histogram":
            fig = px.histogram(df, x=x_col, color=color_col, title=f"Distribution of {x_col}")
        elif chart_type == "bar":
            if y_col:
                fig = px.bar(df, x=x_col, y=y_col, color=color_col, title=f"{y_col} by {x_col}")
            else:
                counts = df[x_col].value_counts().reset_index()
                counts.columns = [x_col, "count"]
                fig = px.bar(counts, x=x_col, y="count", title=f"Count by {x_col}")
        elif chart_type == "line":
            fig = px.line(df.sort_values(x_col), x=x_col, y=y_col, color=color_col, title=f"{y_col} over {x_col}")
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=f"{x_col} vs {y_col}")
        elif chart_type == "box":
            fig = px.box(df, x=color_col, y=x_col, title=f"Distribution of {x_col}")
        elif chart_type == "heatmap":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            corr = df[numeric_cols].corr()
            fig = px.imshow(corr, title="Correlation Matrix", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
        elif chart_type == "timeseries":
            fig = px.line(df.sort_values(x_col), x=x_col, y=y_col, title=f"{y_col} over time")
        else:
            return json.dumps({"error": f"Unknown chart type: {chart_type}"})

        fig.update_layout(paper_bgcolor="#ffffff", plot_bgcolor="#f8fafc", font_color="#0f172a")
        return _df_to_plotly_json(fig)

    except Exception as e:
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()})


# ── Tool 6: SQL Executor ──────────────────────────────────────────────────────

def run_sql(session: DuckDBSession, sql: str) -> dict:
    try:
        df = session.query(sql)
        return {
            "success": True,
            "row_count": len(df),
            "columns": list(df.columns),
            "data": _safe_sample(df, 20),
            "full_df_json": df.to_json(orient="records"),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "sql": sql}


# ── Tool 7: Table Comparator ──────────────────────────────────────────────────

def compare_tables(session: DuckDBSession, table1: str, table2: str) -> dict:
    import pandas as pd

    df1 = session.tables.get(table1)
    df2 = session.tables.get(table2)
    if df1 is None or df2 is None:
        return {"error": "One or both tables not found"}

    shared_cols = list(set(df1.columns) & set(df2.columns))
    report: dict[str, Any] = {
        "table1": table1, "table2": table2,
        "row_count_t1": len(df1), "row_count_t2": len(df2),
        "row_diff": len(df1) - len(df2),
        "shared_columns": shared_cols,
        "columns_only_in_t1": list(set(df1.columns) - set(df2.columns)),
        "columns_only_in_t2": list(set(df2.columns) - set(df1.columns)),
        "column_comparisons": {},
    }

    for col in shared_cols:
        if pd.api.types.is_numeric_dtype(df1[col]) and pd.api.types.is_numeric_dtype(df2[col]):
            report["column_comparisons"][col] = {
                "mean_t1": round(float(df1[col].mean()), 4),
                "mean_t2": round(float(df2[col].mean()), 4),
                "mean_diff_pct": round(abs(df1[col].mean() - df2[col].mean()) / max(abs(df1[col].mean()), 0.001) * 100, 2),
            }
    return report


# ── Tool 8: Metric Suggester ──────────────────────────────────────────────────

def suggest_metrics(session: DuckDBSession) -> dict:
    schemas = get_all_schemas(session)
    suggestions = []

    for table, schema in schemas.items():
        cols = schema["columns"]
        col_names_lower = [c.lower() for c in cols.keys()]

        date_cols   = [c for c in col_names_lower if any(k in c for k in ["date", "time", "created", "updated"])]
        amount_cols = [c for c in col_names_lower if any(k in c for k in ["cost", "revenue", "amount", "price", "value"])]
        status_cols = [c for c in col_names_lower if any(k in c for k in ["status", "type", "category", "tier"])]
        geo_cols    = [c for c in col_names_lower if any(k in c for k in ["route", "region", "zone", "city"])]

        if date_cols and amount_cols:
            dc, ac = date_cols[0], amount_cols[0]
            suggestions.append({
                "metric": f"YoY {ac} Growth", "table": table,
                "description": f"Year-over-year growth rate for {ac}",
                "sql": f"SELECT YEAR({dc}) AS year, SUM({ac}) AS total_{ac} FROM {table} GROUP BY year ORDER BY year",
            })
        if status_cols and amount_cols:
            sc, ac = status_cols[0], amount_cols[0]
            suggestions.append({
                "metric": f"{ac} by {sc}", "table": table,
                "description": f"Total {ac} broken down by {sc}",
                "sql": f"SELECT {sc}, SUM({ac}) AS total_{ac}, COUNT(*) AS count FROM {table} GROUP BY {sc} ORDER BY total_{ac} DESC",
            })
        if geo_cols and amount_cols:
            gc, ac = geo_cols[0], amount_cols[0]
            suggestions.append({
                "metric": f"{ac} by {gc}", "table": table,
                "description": f"Performance breakdown by {gc}",
                "sql": f"SELECT {gc}, SUM({ac}) AS total_{ac}, AVG({ac}) AS avg_{ac} FROM {table} GROUP BY {gc} ORDER BY total_{ac} DESC",
            })

    return {"suggestion_count": len(suggestions), "suggestions": suggestions}
