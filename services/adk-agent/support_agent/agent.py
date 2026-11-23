"""The agent graph.

Phase 1 is a single Gemini agent with one retrieval tool. Sub-agents and the
BigQuery/escalation tools land in later phases; keeping the graph flat until the
retrieval path is measured avoids optimising a design we have not evaluated.
"""
from google.adk.agents import LlmAgent

from support_agent import prompts
from support_agent.config import settings
from support_agent.guardrails import before_model_callback
from support_agent.tools.knowledge import search_knowledge

root_agent = LlmAgent(
    name="support_agent",
    model=settings.agent_model,
    description=(
        "Answers questions about rail and utility assets using the indexed knowledge "
        "base, and says when the knowledge base does not cover the question."
    ),
    instruction=prompts.ROOT_INSTRUCTION,
    tools=[search_knowledge],
    before_model_callback=before_model_callback,
)
