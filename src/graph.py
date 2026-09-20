from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from src.nodes.classify_conversation import classify_conversation
from src.nodes.classify_signaling import classify_signaling
from src.nodes.emit import emit_and_persist
from src.nodes.gate import gate
from src.nodes.message import cancel_reminders
from src.nodes.plan_orders import plan_orders
from src.state import OrchestratorState


def build_graph():
    workflow = StateGraph(OrchestratorState)
    workflow.add_node("gate", gate)
    workflow.add_node("classify_signaling", classify_signaling)
    workflow.add_node(
        "classify_conversation",
        classify_conversation,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0),
    )
    workflow.add_node("plan_orders", plan_orders)
    workflow.add_node("cancel_reminders", cancel_reminders)
    workflow.add_node("emit_and_persist", emit_and_persist)
    workflow.add_node("write_skip", emit_and_persist)
    workflow.add_node("write_redelivery", emit_and_persist)

    workflow.add_edge(START, "gate")
    workflow.add_edge("classify_conversation", "plan_orders")
    workflow.add_edge("plan_orders", "emit_and_persist")
    workflow.add_edge("cancel_reminders", "emit_and_persist")
    workflow.add_edge("emit_and_persist", END)
    workflow.add_edge("write_skip", END)
    workflow.add_edge("write_redelivery", END)
    return workflow.compile()


GRAPH = build_graph()
