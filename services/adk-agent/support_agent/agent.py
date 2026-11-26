"""The agent graph.

Phase 2 adds two tools to the flat graph: a read-only asset lookup and a
human-in-the-loop escalation. Sub-agents remain deferred until evaluation shows
that one agent cannot route reliably.
"""
from google.adk.agents import LlmAgent

from support_agent import prompts
from support_agent.config import settings
from support_agent.guardrails import before_model_callback
from support_agent.tools.escalation import escalate
from support_agent.tools.knowledge import search_knowledge
from support_agent.tools.records import lookup_record

root_agent = LlmAgent(
    name="support_agent",
    model=settings.agent_model,
    description=(
        "Answers questions about rail and utility assets using the indexed knowledge "
        "base and the asset register, and escalates requests it cannot resolve."
    ),
    instruction=prompts.ROOT_INSTRUCTION,
    tools=[search_knowledge, lookup_record, escalate],
    before_model_callback=before_model_callback,
)
