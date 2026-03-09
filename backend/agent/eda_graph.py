"""
ATLAS EDA LangGraph Graph
Defines the full agent graph with nodes, edges, and conditional routing.
"""

from typing import TypedDict, Optional, Any
from langgraph.graph import StateGraph, END

from agent.nodes import (
    schema_loader_node,
    intent_planner_node,
    profile_node,
    anomaly_node,
    relationship_node,
    chart_node,
    sql_node,
    compare_node,
    suggest_metrics_node,
    synthesiser_node,
)


# ── State Schema ──────────────────────────────────────────────────────────────

class EDAState(TypedDict):
    # Input
    session_id: str
    user_prompt: str

    # Schema
    schemas: Optional[dict]
    available_tables: Optional[list]

    # Plan
    plan: Optional[dict]
    intent: Optional[str]

    # Results from tool nodes
    profiles: Optional[dict]
    anomaly_results: Optional[dict]
    relationships: Optional[dict]
    charts: Optional[list]
    sql_result: Optional[dict]
    generated_sql: Optional[str]
    sql_attempts: Optional[int]
    compare_result: Optional[dict]
    metric_suggestions: Optional[dict]

    # Output
    narrative: Optional[str]
    error: Optional[str]


# ── Routing Functions ─────────────────────────────────────────────────────────

def route_by_intent(state: EDAState) -> str:
    """
    Conditional edge after intent_planner.
    Routes to the appropriate analysis node based on detected intent.
    """
    intent = state.get("intent", "general")

    routing_map = {
        "profile":         "profile",
        "anomaly":         "anomaly",
        "relationship":    "relationship",
        "chart":           "chart",
        "sql":             "sql",
        "compare":         "compare",
        "suggest_metrics": "suggest_metrics",
        "general":         "profile",   # default to profile for general queries
    }

    return routing_map.get(intent, "profile")


def check_for_error(state: EDAState) -> str:
    """Check if schema loader hit an error."""
    if state.get("error"):
        return END
    return "intent_planner"


# ── Graph Builder ─────────────────────────────────────────────────────────────

def build_eda_graph() -> StateGraph:
    graph = StateGraph(EDAState)

    # ── Add nodes ──
    graph.add_node("schema_loader",    schema_loader_node)
    graph.add_node("intent_planner",   intent_planner_node)
    graph.add_node("profile",          profile_node)
    graph.add_node("anomaly",          anomaly_node)
    graph.add_node("relationship",     relationship_node)
    graph.add_node("chart",            chart_node)
    graph.add_node("sql",              sql_node)
    graph.add_node("compare",          compare_node)
    graph.add_node("suggest_metrics",  suggest_metrics_node)
    graph.add_node("synthesiser",      synthesiser_node)

    # ── Entry point ──
    graph.set_entry_point("schema_loader")

    # ── Edges ──
    # After schema loader — check for error, then plan
    graph.add_conditional_edges(
        "schema_loader",
        check_for_error,
        {
            "intent_planner": "intent_planner",
            END: END,
        },
    )

    # After intent planner — route to correct analysis node
    graph.add_conditional_edges(
        "intent_planner",
        route_by_intent,
        {
            "profile":         "profile",
            "anomaly":         "anomaly",
            "relationship":    "relationship",
            "chart":           "chart",
            "sql":             "sql",
            "compare":         "compare",
            "suggest_metrics": "suggest_metrics",
        },
    )

    # All analysis nodes flow to synthesiser
    for node in ["profile", "anomaly", "relationship", "chart", "sql", "compare", "suggest_metrics"]:
        graph.add_edge(node, "synthesiser")

    # Synthesiser ends the graph
    graph.add_edge("synthesiser", END)

    return graph.compile()


# ── Compiled graph (singleton) ────────────────────────────────────────────────
eda_graph = build_eda_graph()


async def run_eda_agent(session_id: str, user_prompt: str) -> dict:
    """
    Main entry point for running the EDA agent.
    Returns the final state with narrative + charts + all results.
    """
    initial_state: EDAState = {
        "session_id": session_id,
        "user_prompt": user_prompt,
        "schemas": None,
        "available_tables": None,
        "plan": None,
        "intent": None,
        "profiles": None,
        "anomaly_results": None,
        "relationships": None,
        "charts": None,
        "sql_result": None,
        "generated_sql": None,
        "sql_attempts": None,
        "compare_result": None,
        "metric_suggestions": None,
        "narrative": None,
        "error": None,
    }

    final_state = await eda_graph.ainvoke(initial_state)
    return final_state
