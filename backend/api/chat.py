"""
ATLAS EDA — Chat API
Handles chat with history persistence via Supabase.
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.eda_graph import run_eda_agent
from db.duckdb_session import get_session
from db.supabase import get_supabase_admin

router = APIRouter(prefix="/chat", tags=["chat"])


# ── Supabase history helpers ──────────────────────────────────────────────────

def _save_message(session_id: str, role: str, content: dict):
    """Save a message to Supabase. Silently fails if Supabase not configured."""
    try:
        sb = get_supabase_admin()
        sb.table("eda_chat_history").insert({
            "session_id": session_id,
            "role": role,
            "content": json.dumps(content),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass  # History saving is non-critical — don't break the chat


def _load_history(session_id: str) -> list:
    """Load chat history for a session from Supabase."""
    try:
        sb = get_supabase_admin()
        result = (
            sb.table("eda_chat_history")
            .select("role, content, created_at")
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
        )
        return [
            {
                "role": row["role"],
                **json.loads(row["content"]),
                "created_at": row["created_at"],
            }
            for row in result.data
        ]
    except Exception:
        return []


def _delete_history(session_id: str):
    """Delete all chat history for a session."""
    try:
        sb = get_supabase_admin()
        sb.table("eda_chat_history").delete().eq("session_id", session_id).execute()
    except Exception:
        pass


# ── Request models ────────────────────────────────────────────────────────────

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/")
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Saves messages to Supabase for history persistence.
    """
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found. Please re-upload your files.")

    # Save user message
    _save_message(request.session_id, "user", {"content": request.prompt})

    try:
        final_state = await run_eda_agent(
            session_id=request.session_id,
            user_prompt=request.prompt,
        )

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

        # Save assistant response
        _save_message(request.session_id, "assistant", response)

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """Load full chat history for a session."""
    history = _load_history(session_id)
    return {"session_id": session_id, "messages": history, "count": len(history)}


@router.delete("/history/{session_id}")
async def clear_history(session_id: str):
    """Clear chat history for a session."""
    _delete_history(session_id)
    return {"message": "Chat history cleared"}


@router.post("/chart")
async def generate_chart_endpoint(request: ChartRequest):
    """Direct chart generation — no full agent run needed."""
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
    from agent.tools import get_all_schemas
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return get_all_schemas(session)
