"""Wiring checks that need no model call."""
import asyncio

from support_agent.agent import root_agent


def test_root_agent_is_named_and_configured():
    assert root_agent.name == "support_agent"
    assert "gemini" in str(root_agent.model)


def test_retrieval_tool_is_registered():
    tools = asyncio.run(root_agent.canonical_tools())
    names = {tool.name for tool in tools}
    assert {"search_knowledge", "lookup_record", "escalate"} <= names


def test_guardrail_is_wired():
    assert root_agent.before_model_callback is not None
