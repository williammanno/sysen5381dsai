# word_agent_workflow.py
# Task 1–3: Custom tool + 2-agent workflow using agent_run() from functions.py
#
# Run from this directory (needs word.env for API + Ollama running locally):
#   python word_agent_workflow.py
#   python word_agent_workflow.py vocabulary

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Load API keys before importing api_client
_here = Path(__file__).resolve().parent
for parent in [_here, _here.parent]:
    for name in ("word.env", "ollama.env", ".env"):
        p = parent / name
        if p.exists():
            from dotenv import load_dotenv
            load_dotenv(p)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from functions import DEFAULT_MODEL, agent_run

# Import after env so get_word_data sees WORD_PRONOUNCER_API_KEY
from api_client import get_word_data


# -----------------------------------------------------------------------------
# Task 1: Custom tool function + metadata
# -----------------------------------------------------------------------------

def fetch_word_lookup(word: str) -> str:
    """
    Look up a word via the project dictionary API (Merriam-Webster + fallback).
    Returns JSON text for the LLM / next agent.

    Parameters
    ----------
    word : str
        English word to look up.

    Returns
    -------
    str
        JSON string with ok, word, pronunciations, definitions, audio_count.
    """
    w = (word or "").strip()
    if not w:
        return json.dumps({"ok": False, "error": "Empty word."})
    data = get_word_data(w)
    if data.get("ok"):
        payload = {
            "ok": True,
            "word": data.get("word"),
            "pronunciations": data.get("pronunciations", []),
            "definitions": data.get("definitions", []),
            "audio_count": len(data.get("audio", [])),
        }
    else:
        payload = {"ok": False, "error": data.get("error", "Unknown error")}
    return json.dumps(payload, indent=2)


# Tool metadata for Ollama function calling (must match function name above)
FETCH_WORD_TOOL = {
    "type": "function",
    "function": {
        "name": "fetch_word_lookup",
        "description": (
            "Fetches dictionary data for an English word: phonetic pronunciations, "
            "definitions with part of speech, and whether audio is available. "
            "Use this whenever the user asks about a specific word's meaning or pronunciation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "The English word to look up (e.g. hello, pronunciation).",
                }
            },
            "required": ["word"],
        },
    },
}


# -----------------------------------------------------------------------------
# Task 2: Two agents chained with agent_run()
# -----------------------------------------------------------------------------

AGENT1_ROLE = """You are Agent 1: a dictionary assistant.
You MUST use the fetch_word_lookup tool exactly once with the word the user gives you.
Do not invent definitions; only report what the tool returns.
After the tool runs, reply with one short sentence confirming you retrieved the data (the tool output is returned separately)."""


AGENT2_ROLE = """You are Agent 2: a language-learning report writer.
You receive dictionary JSON from Agent 1's workflow (pronunciations, definitions).
Write a concise, friendly report for a learner: how to pronounce the word, what it means, and one usage tip.
Use bullet points or short paragraphs. If the data shows ok=false, explain the error briefly."""


def run_two_agent_workflow(word: str, model: Optional[str] = None) -> dict:
    """
    Agent 1: agent_run with tools → executes fetch_word_lookup via Ollama tool call.
    Agent 2: agent_run without tools → report from tool JSON.
    """
    m = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

    task1 = f'Look up the word "{word}" using the tool.'
    agent1_result = agent_run(
        role=AGENT1_ROLE,
        task=task1,
        tools=[FETCH_WORD_TOOL],
        model=m,
    )

    # agent_run with tools returns the tool output string (last tool call)
    tool_json = agent1_result if isinstance(agent1_result, str) else str(agent1_result)

    task2 = f"Here is the dictionary JSON for your report:\n\n{tool_json}"
    agent2_result = agent_run(
        role=AGENT2_ROLE,
        task=task2,
        tools=None,
        model=m,
    )

    return {
        "word": word,
        "agent1_tool_output": tool_json,
        "agent2_report": agent2_result,
    }


# -----------------------------------------------------------------------------
# Task 3: Test and refine
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    test_word = (sys.argv[1] if len(sys.argv) > 1 else "pronunciation").strip()
    print("=" * 60)
    print("Word Pronunciation Reporter — 2-agent workflow")
    print(f"Model: {os.getenv('OLLAMA_MODEL', DEFAULT_MODEL)}")
    print(f"Test word: {test_word}")
    print("=" * 60)

    # Direct tool test (no LLM) — verifies API + Task 1
    print("\n[Task 1] Tool output sample (fetch_word_lookup):")
    print(fetch_word_lookup(test_word)[:800])
    print()

    try:
        out = run_two_agent_workflow(test_word)
        print("[Agent 1] Tool output (via agent_run + Ollama):")
        print(out["agent1_tool_output"][:1200])
        print("\n[Agent 2] Final report:")
        print(out["agent2_report"])
    except Exception as e:
        print("Workflow error:", e)
        print("\nRefinement tips:")
        print("- Run: ollama serve")
        print("- Pull a model that supports tools, e.g.: ollama pull llama3.2:3b")
        print("- Set OLLAMA_MODEL in .env to match a pulled model")
        raise

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)
