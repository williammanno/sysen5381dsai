# word_multiagent_rag.py
# Multi-agent + RAG + function-calling workflow for Word Pronunciation Reporter.
# Inspired by dsai/06_agents/07_starwars_agents.R and dsai/07_rag/03_csv_lego_cloud.py
#
# Run:
#   python word_multiagent_rag.py
#   python word_multiagent_rag.py pronunciation

import json
import os
import re
import sys
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Load environment variables before imports that need them
HERE = Path(__file__).resolve().parent
for parent in [HERE, HERE.parent, HERE.parent.parent]:
    for name in ("word.env", "ollama.env", ".env"):
        env_file = parent / name
        if env_file.exists():
            from dotenv import load_dotenv

            load_dotenv(env_file)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from api_client import get_word_data
from functions import DEFAULT_MODEL, agent_run
from word_list import get_all_words

RAG_DOCUMENT = HERE / "rag_learning_notes.csv"


# -----------------------------------------------------------------------------
# Tool 1: Dictionary function call (existing software capability)
# -----------------------------------------------------------------------------
def fetch_word_lookup(word: str) -> str:
    """Fetch dictionary data and normalize to compact JSON string."""
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


# -----------------------------------------------------------------------------
# Tool 2: RAG retrieval from local CSV (lesson notes)
# -----------------------------------------------------------------------------
def search_pronunciation_notes(query: str, top_k: int = 5) -> str:
    """
    Retrieve pronunciation-learning notes from local CSV by keyword overlap.
    Returns JSON list of notes with simple relevance scores.
    """
    q = (query or "").strip().lower()
    if not q:
        return json.dumps([])

    df = pd.read_csv(RAG_DOCUMENT)
    terms = [t for t in re.split(r"[^a-z0-9]+", q) if t]

    def score_row(row: pd.Series) -> int:
        hay = " ".join(
            str(row.get(col, "")).lower()
            for col in ["pattern", "keywords", "when_to_use", "memory_tip", "example_words"]
        )
        score = 0
        for term in terms:
            if term in hay:
                score += 2
        if q in hay:
            score += 3
        return score

    df["score"] = df.apply(score_row, axis=1)
    df = df[df["score"] > 0].sort_values("score", ascending=False)
    if df.empty:
        # Return empty evidence rather than unrelated generic notes.
        return json.dumps([], indent=2)
    df = df.head(max(1, top_k))

    records = df[["pattern", "when_to_use", "memory_tip", "example_words", "score"]].to_dict(
        orient="records"
    )
    return json.dumps(records, indent=2)


# -----------------------------------------------------------------------------
# Tool 3: RAG retrieval from local word bank (lexical neighbors)
# -----------------------------------------------------------------------------
def search_local_word_bank(query: str, top_k: int = 10) -> str:
    """
    Retrieve related words from local word bank for comparative learning.
    Uses fuzzy matches + same prefix and similar length.
    """
    q = (query or "").strip().lower()
    if not q:
        return json.dumps([])

    words = get_all_words()
    close = get_close_matches(q, words, n=top_k, cutoff=0.6)
    prefix = [w for w in words if w.startswith(q[:2]) and w != q][: max(0, top_k // 2)]
    similar_len = [w for w in words if abs(len(w) - len(q)) <= 1 and w != q][: max(0, top_k // 2)]

    merged: List[str] = []
    for w in close + prefix + similar_len:
        if w not in merged:
            merged.append(w)
        if len(merged) >= top_k:
            break

    out = [
        {
            "word": w,
            "relationship": (
                "spelling-similar" if w in close else "prefix/length-neighbor"
            ),
        }
        for w in merged
    ]
    return json.dumps(out, indent=2)


# -----------------------------------------------------------------------------
# Tool metadata for function-calling
# -----------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_word_lookup",
            "description": (
                "Get dictionary evidence for one English word: pronunciation, definitions, and audio count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "Word to look up, e.g., pronunciation.",
                    }
                },
                "required": ["word"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_pronunciation_notes",
            "description": (
                "RAG search over local pronunciation teaching notes CSV. Returns relevant strategies and memory tips."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search phrase, usually the target word.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum rows to retrieve.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_local_word_bank",
            "description": (
                "Retrieve similar words from local word bank for compare-and-contrast learning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Target word to find related words for.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum related words to return.",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# -----------------------------------------------------------------------------
# Multi-agent roles (orchestration inspired by starwars_agents.R)
# -----------------------------------------------------------------------------
AGENT1_ROLE = """You are Agent 1: Retrieval and Evidence Collector.
You must call these tools to gather evidence for one target word:
1) fetch_word_lookup(word)
2) search_pronunciation_notes(query=word)
3) search_local_word_bank(query=word)
Call each tool once. Do not invent data.
Do not call any tool more than once.
After tools are called, return a single short sentence confirming retrieval is complete."""

AGENT2_ROLE = """You are Agent 2: Learning Analyst.
Input contains JSON evidence from Agent 1 including dictionary facts and retrieved RAG notes.
Produce a concise analysis with these sections:
- Pronunciation Challenges
- Meaning Snapshot
- Related Vocabulary
- Teaching Strategy
Use only provided evidence; if evidence is missing, say so clearly.
Do not invent sounds, definitions, or related words.
Only mention pronunciation cues that appear in dictionary pronunciations or retrieved notes."""

AGENT3_ROLE = """You are Agent 3: AI Reporter.
Convert Agent 2 analysis into a polished markdown report for a learner.
Required sections:
1) Title
2) Quick Summary (2-3 bullets)
3) Pronunciation Coaching (actionable steps)
4) Related Words to Practice (5 words max)
5) Mini Study Plan (today, this week)
Keep tone supportive and practical."""


def _extract_tool_outputs(tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_name: Dict[str, Any] = {}
    for call in tool_calls:
        fn = (call.get("function") or {}).get("name")
        raw = call.get("output")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = raw
        by_name[fn] = parsed
    return by_name


def _dedupe_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep a single call per tool name (last call wins).
    This stabilizes downstream evidence when smaller models repeat calls.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for call in tool_calls:
        name = (call.get("function") or {}).get("name")
        if not name:
            continue
        if name not in seen:
            order.append(name)
        seen[name] = call
    return [seen[name] for name in order]


def run_multiagent_rag_workflow(word: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Run full 3-agent workflow with tools + RAG + analysis/reporting."""
    m = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

    task1 = (
        f"Target word: {word}. Gather evidence with tools. "
        "Call all three tools exactly once."
    )
    tool_calls = agent_run(
        role=AGENT1_ROLE,
        task=task1,
        tools=TOOLS,
        output="tools",
        model=m,
    )

    # Some small models may miss one required call; enforce completeness deterministically.
    if not isinstance(tool_calls, list):
        tool_calls = []
    called_names = [((tc.get("function") or {}).get("name")) for tc in tool_calls]
    if "fetch_word_lookup" not in called_names:
        tool_calls.append(
            {
                "function": {"name": "fetch_word_lookup", "arguments": {"word": word}},
                "output": fetch_word_lookup(word),
            }
        )
    if "search_pronunciation_notes" not in called_names:
        tool_calls.append(
            {
                "function": {"name": "search_pronunciation_notes", "arguments": {"query": word, "top_k": 5}},
                "output": search_pronunciation_notes(word, top_k=5),
            }
        )
    if "search_local_word_bank" not in called_names:
        tool_calls.append(
            {
                "function": {"name": "search_local_word_bank", "arguments": {"query": word, "top_k": 10}},
                "output": search_local_word_bank(word, top_k=10),
            }
        )
    tool_calls = _dedupe_tool_calls(tool_calls)

    evidence = _extract_tool_outputs(tool_calls)
    evidence_packet = {
        "word": word,
        "dictionary": evidence.get("fetch_word_lookup"),
        "rag_pronunciation_notes": evidence.get("search_pronunciation_notes"),
        "rag_related_words": evidence.get("search_local_word_bank"),
    }

    task2 = "Evidence JSON from Agent 1:\n\n" + json.dumps(evidence_packet, indent=2)
    analysis = agent_run(role=AGENT2_ROLE, task=task2, model=m)

    task3 = (
        "Create final learner report from this analysis:\n\n"
        + analysis
        + "\n\nAlso reference this evidence JSON if needed:\n"
        + json.dumps(evidence_packet, indent=2)
    )
    final_report = agent_run(role=AGENT3_ROLE, task=task3, model=m)

    return {
        "word": word,
        "model": m,
        "tool_calls": tool_calls,
        "evidence": evidence_packet,
        "agent2_analysis": analysis,
        "agent3_report": final_report,
    }


if __name__ == "__main__":
    target = (sys.argv[1] if len(sys.argv) > 1 else "pronunciation").strip()

    print("=" * 72)
    print("Word Reporter - Multi-Agent + RAG + Function Calling")
    print(f"Model: {os.getenv('OLLAMA_MODEL', DEFAULT_MODEL)}")
    print(f"Target word: {target}")
    print("=" * 72)

    # Quick local RAG tests (before LLM)
    print("\n[RAG Test] Pronunciation note retrieval preview:")
    print(search_pronunciation_notes(target, top_k=3)[:800])

    print("\n[RAG Test] Local related words preview:")
    print(search_local_word_bank(target, top_k=8)[:800])

    out = run_multiagent_rag_workflow(target)

    print("\n[Agent 1] Tool names called:")
    names = [((tc.get("function") or {}).get("name")) for tc in (out.get("tool_calls") or [])]
    print(names)

    print("\n[Agent 2] Analysis:")
    print(out["agent2_analysis"])

    print("\n[Agent 3] Final Report:")
    print(out["agent3_report"])

    print("\n" + "=" * 72)
    print("Done.")
    print("=" * 72)
