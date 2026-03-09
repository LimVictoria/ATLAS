"""
ATLAS EDA — Chat API
Receives user prompts and runs them through the LangGraph EDA agent.
Returns narrative + charts + raw results.
"""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.eda_graph import run_eda_agent
from db.duckdb_session import get_session

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str
    prompt: str


class ChartRequest(BaseModel):
    session_id: str
    table_name: str
    chart_type: str
    x_col: str
    y_col: str | None = None
    color_col: str | None = None


@router.post("/")
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Runs the LangGraph EDA agent and returns full response bundle.
    """
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please re-upload your files.")

    try:
        final_state = await run_eda_agent(
            session_id=request.session_id,
            user_prompt=request.prompt,
        )

        # Build clean response bundle
        response = {
            "narrative": final_state.get("narrative", ""),
            "intent": final_state.get("intent", "general"),
            "plan": final_state.get("plan", {}),
            "charts": final_state.get("charts", []),
            "generated_sql": final_state.get("generated_sql"),
            "sql_result": final_state.get("sql_result"),
            "anomalies": final_state.get("anomaly_results"),
            "relationships": final_state.get("relationships"),
            "metric_suggestions": final_state.get("metric_suggestions"),
            "compare_result": final_state.get("compare_result"),
            "error": final_state.get("error"),
        }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/chart")
async def generate_chart_endpoint(request: ChartRequest):
    """
    Direct chart generation endpoint.
    Used by the per-visual prompt box — no full agent run needed.
    """
    from agent.tools import generate_chart
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    chart_json = generate_chart(
        session=session,
        table_name=request.table_name,
        chart_type=request.chart_type,
        x_col=request.x_col,
        y_col=request.y_col,
        color_col=request.color_col,
    )

    return {"chart": chart_json}


@router.get("/schema/{session_id}")
async def get_schema(session_id: str):
    """Returns full schema for all tables in session."""
    from agent.tools import get_all_schemas
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return get_all_schemas(session)
