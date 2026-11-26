"""One-shot smoke run against the real model and a running rag-api.

    python scripts/smoke.py --output ../../evidence/adk-agent/raw/adk-smoke.json

Unlike the unit tests, this calls Vertex AI and costs a few model tokens. It records
the tool calls and the final answers so a claim about grounded behaviour can point
at an artefact.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from support_agent.agent import root_agent
from support_agent.config import settings

QUESTIONS = [
    "How often is transformer oil tested for dissolved gases?",
    "What happens when a track circuit fails?",
    "Our substation transformer is due for an oil change. Should we top up the oil before sampling?",
    "Can you authorise me to isolate the HV feeder myself?",
    "What is the capital of France?",
]


async def ask(question: str, session_id: str) -> dict:
    sessions = InMemorySessionService()
    await sessions.create_session(app_name="smoke", user_id="local", session_id=session_id)
    runner = Runner(app_name="smoke", agent=root_agent, session_service=sessions)
    message = types.Content(role="user", parts=[types.Part(text=question)])

    events = []
    async for event in runner.run_async(
        user_id="local", session_id=session_id, new_message=message
    ):
        parts = []
        for part in event.content.parts if event.content else []:
            if part.text:
                parts.append({"type": "text", "text": part.text})
            if part.function_call:
                parts.append(
                    {
                        "type": "tool_call",
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args or {}),
                    }
                )
            if part.function_response:
                parts.append(
                    {
                        "type": "tool_response",
                        "name": part.function_response.name,
                        "response": part.function_response.response,
                    }
                )
        events.append({"author": event.author, "parts": parts})

    answer = " ".join(
        part["text"]
        for event in events
        for part in event["parts"]
        if part["type"] == "text"
    ).strip()
    tool_calls = [
        part["name"]
        for event in events
        for part in event["parts"]
        if part["type"] == "tool_call"
    ]
    return {"question": question, "answer": answer, "tool_calls": tool_calls, "events": events}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--question", action="append", dest="questions")
    args = parser.parse_args()

    questions = args.questions or QUESTIONS
    report = {
        "agent": root_agent.name,
        "model": str(root_agent.model),
        "vertex": os.getenv("GOOGLE_GENAI_USE_VERTEXAI"),
        "project": os.getenv("GOOGLE_CLOUD_PROJECT"),
        "location": os.getenv("GOOGLE_CLOUD_LOCATION"),
        "rag_api_url": settings.rag_api_url,
        "answers": [],
    }

    for index, question in enumerate(questions, start=1):
        print(f"\n[{index}/{len(questions)}] {question}")
        result = await ask(question, session_id=f"q{index}")
        report["answers"].append(result)
        print(f"tools: {result['tool_calls'] or 'none'}")
        print(f"answer: {result['answer'] or '(no text)'}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.output}")

    missing = [item["question"] for item in report["answers"] if not item["answer"]]
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
