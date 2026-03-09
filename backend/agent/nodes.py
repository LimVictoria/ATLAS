"""
ATLAS EDA LangGraph Nodes
Each node is a pure function: takes state dict, returns updated state dict.
"""

import json
from typing import Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent.tools import (
    get_all_schemas,
    profile_table,
    detect_relationships,
    detect_anomalies,
    generate_chart,
    run_sql,
    compare_tables,
    suggest_metrics,
)
from db.duckdb_session import get_session

# ── LLM ──────────────────────────────────────────────────────────────────────

def get_llm():
    return ChatGroq(
        model="llama-3.1-70b-versatile",
        temperature=0,
        max_tokens=4096,
    )


# ── Node: Schema Loader ───────────────────────────────────────────────────────

def schema_loader_node(state: dict) -> dict:
    """
    First node always called.
    Loads schema from all tables in the session.
    """
    session_id = state["session_id"]
    session = get_session(session_id)
    if session is None:
        return {**state, "error": "Session not found. Please re-upload your files."}

    schemas = get_all_schemas(session)
    return {
        **state,
        "schemas": schemas,
        "available_tables": list(schemas.keys()),
    }


# ── Node: Intent Planner ──────────────────────────────────────────────────────

def intent_planner_node(state: dict) -> dict:
    """
    LLM reads the user prompt + schemas and decides:
    - What kind of analysis is needed
    - Which tools to call
    - Whether this is simple (single call) or complex (agent loop)
    """
    llm = get_llm()
    schemas_summary = json.dumps(state.get("schemas", {}), indent=2)[:3000]

    system_prompt = """You are ATLAS, an expert data analyst AI for a logistics company.
You help users explore and understand their data through EDA.

Given the user's question and the available table schemas, decide what analysis to perform.
Respond ONLY with valid JSON in this exact format:

{
  "intent": "one of: profile|anomaly|relationship|chart|sql|compare|suggest_metrics|general",
  "complexity": "one of: simple|complex",
  "tables_needed": ["list", "of", "table", "names"],
  "analysis_plan": "brief description of what you will do",
  "requires_join": true or false,
  "chart_type": "one of: histogram|bar|line|scatter|box|heatmap|timeseries|none"
}"""

    user_msg = f"""Available tables and schemas:
{schemas_summary}

User question: {state['user_prompt']}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ])

    try:
        plan = json.loads(response.content)
    except json.JSONDecodeError:
        plan = {
            "intent": "general",
            "complexity": "simple",
            "tables_needed": state.get("available_tables", []),
            "analysis_plan": "General analysis",
            "requires_join": False,
            "chart_type": "none",
        }

    return {**state, "plan": plan, "intent": plan.get("intent", "general")}


# ── Node: Profile Node ────────────────────────────────────────────────────────

def profile_node(state: dict) -> dict:
    """Profiles all tables in the plan."""
    session = get_session(state["session_id"])
    tables = state["plan"].get("tables_needed", state.get("available_tables", []))
    profiles = {}
    for table in tables:
        profiles[table] = profile_table(session, table)
    return {**state, "profiles": profiles}


# ── Node: Anomaly Node ────────────────────────────────────────────────────────

def anomaly_node(state: dict) -> dict:
    """Runs anomaly detection on relevant tables."""
    session = get_session(state["session_id"])
    tables = state["plan"].get("tables_needed", state.get("available_tables", []))
    anomaly_results = {}
    for table in tables:
        anomaly_results[table] = detect_anomalies(session, table)
    return {**state, "anomaly_results": anomaly_results}


# ── Node: Relationship Node ───────────────────────────────────────────────────

def relationship_node(state: dict) -> dict:
    """Detects relationships across all tables."""
    session = get_session(state["session_id"])
    relationships = detect_relationships(session)
    return {**state, "relationships": relationships}


# ── Node: Chart Node ──────────────────────────────────────────────────────────

def chart_node(state: dict) -> dict:
    """
    Generates a chart based on the plan.
    LLM first decides which columns to use, then generates the chart.
    """
    session = get_session(state["session_id"])
    llm = get_llm()
    plan = state["plan"]
    tables = plan.get("tables_needed", [])

    if not tables:
        return {**state, "charts": []}

    table = tables[0]
    schema = state["schemas"].get(table, {})

    # Ask LLM to pick appropriate columns
    col_prompt = f"""Given this table schema:
{json.dumps(schema, indent=2)}

User wants: {state['user_prompt']}
Chart type decided: {plan.get('chart_type', 'bar')}

Respond ONLY with JSON:
{{"x_col": "column_name", "y_col": "column_name_or_null", "color_col": "column_name_or_null"}}"""

    col_response = llm.invoke([HumanMessage(content=col_prompt)])
    try:
        col_choice = json.loads(col_response.content)
    except Exception:
        cols = list(schema.get("columns", {}).keys())
        col_choice = {"x_col": cols[0] if cols else "", "y_col": cols[1] if len(cols) > 1 else None, "color_col": None}

    chart_json = generate_chart(
        session,
        table,
        chart_type=plan.get("chart_type", "bar"),
        x_col=col_choice.get("x_col", ""),
        y_col=col_choice.get("y_col"),
        color_col=col_choice.get("color_col"),
    )

    return {**state, "charts": [chart_json]}


# ── Node: SQL Node ────────────────────────────────────────────────────────────

def sql_node(state: dict) -> dict:
    """
    LLM generates SQL from user prompt, executes it.
    Includes self-correction loop up to 3 retries.
    """
    session = get_session(state["session_id"])
    llm = get_llm()
    schemas_str = json.dumps(state.get("schemas", {}), indent=2)[:3000]

    sql_prompt = f"""You are a SQL expert. Generate DuckDB SQL for this request.

Available tables and schemas:
{schemas_str}

User request: {state['user_prompt']}

Rules:
- Use only the tables and columns listed above
- DuckDB SQL syntax
- Respond ONLY with the raw SQL query, no markdown, no explanation"""

    attempts = 0
    last_error = None
    generated_sql = ""

    while attempts < 3:
        sql_response = llm.invoke([HumanMessage(content=sql_prompt)])
        generated_sql = sql_response.content.strip().replace("```sql", "").replace("```", "").strip()
        result = run_sql(session, generated_sql)

        if result["success"]:
            return {**state, "sql_result": result, "generated_sql": generated_sql, "sql_attempts": attempts + 1}

        last_error = result["error"]
        sql_prompt = f"""Previous SQL failed with error: {last_error}
Original SQL: {generated_sql}

Fix the SQL. Respond ONLY with the corrected raw SQL query."""
        attempts += 1

    return {
        **state,
        "sql_result": {"success": False, "error": last_error},
        "generated_sql": generated_sql,
        "sql_attempts": attempts,
    }


# ── Node: Compare Node ────────────────────────────────────────────────────────

def compare_node(state: dict) -> dict:
    """Compares two tables for reconciliation."""
    session = get_session(state["session_id"])
    tables = state["plan"].get("tables_needed", [])
    if len(tables) < 2:
        return {**state, "compare_result": {"error": "Need at least 2 tables to compare"}}
    result = compare_tables(session, tables[0], tables[1])
    return {**state, "compare_result": result}


# ── Node: Suggest Metrics Node ────────────────────────────────────────────────

def suggest_metrics_node(state: dict) -> dict:
    """Suggests BI metrics based on schema analysis."""
    session = get_session(state["session_id"])
    suggestions = suggest_metrics(session)
    return {**state, "metric_suggestions": suggestions}


# ── Node: Synthesiser ─────────────────────────────────────────────────────────

def synthesiser_node(state: dict) -> dict:
    """
    Final node — LLM combines all findings into a human-readable response.
    Generates narrative + any additional chart specs needed.
    """
    llm = get_llm()

    # Build context from all collected results
    context_parts = []

    if state.get("profiles"):
        context_parts.append(f"DATA PROFILES:\n{json.dumps(state['profiles'], indent=2)[:2000]}")

    if state.get("anomaly_results"):
        context_parts.append(f"ANOMALIES FOUND:\n{json.dumps(state['anomaly_results'], indent=2)[:2000]}")

    if state.get("relationships"):
        context_parts.append(f"RELATIONSHIPS:\n{json.dumps(state['relationships'], indent=2)[:1000]}")

    if state.get("sql_result"):
        context_parts.append(f"SQL RESULT:\n{json.dumps(state['sql_result'], indent=2)[:1000]}")

    if state.get("compare_result"):
        context_parts.append(f"COMPARISON:\n{json.dumps(state['compare_result'], indent=2)[:2000]}")

    if state.get("metric_suggestions"):
        context_parts.append(f"METRIC SUGGESTIONS:\n{json.dumps(state['metric_suggestions'], indent=2)[:2000]}")

    context = "\n\n".join(context_parts) if context_parts else "No analysis results available."

    system_prompt = """You are ATLAS, an expert data analyst for a logistics company.
Synthesise the analysis results into a clear, concise response for a data professional.

Structure your response as:
1. Key findings (bullet points)
2. Issues to address (if any)
3. Recommendations

Be specific with numbers. Flag anything that needs attention before data can be trusted."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"User asked: {state['user_prompt']}\n\nAnalysis results:\n{context}"),
    ])

    return {**state, "narrative": response.content}
