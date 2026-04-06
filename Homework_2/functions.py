# functions.py
# Function Calling Helper Functions (aligned with dsai/08_function_calling/functions.py)
# Used by word_agent_workflow.py for multi-agent orchestration with Ollama tool calling.

import json
import os
import sys
import time

import pandas as pd
import requests

# Default model: match course examples or override with OLLAMA_MODEL
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "smollm2:1.7b")
PORT = 11434
OLLAMA_HOST = f"http://localhost:{PORT}"
CHAT_URL = f"{OLLAMA_HOST}/api/chat"
REQUEST_TIMEOUT = 300
OLLAMA_TAGS_URL = f"{OLLAMA_HOST}/api/tags"


def ensure_ollama_available(max_wait_seconds: int = 15, poll_interval_seconds: float = 0.5) -> None:
    """Fail fast with a helpful message if Ollama isn't reachable."""
    deadline = time.time() + max_wait_seconds
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(OLLAMA_TAGS_URL, timeout=5)
            if r.ok:
                return
        except Exception as e:
            last_err = e
        time.sleep(poll_interval_seconds)

    raise RuntimeError(
        "Ollama is not reachable at localhost:11434. Start it with: ollama serve\n"
        f"Last error: {last_err}"
    )


def agent(messages, model=DEFAULT_MODEL, output="text", tools=None, all=False):
    """
    Agent wrapper: single Ollama chat, with or without tools.

    Parameters
    ----------
    messages : list
        [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    model : str
    output : str
        "text" or "tools"
    tools : list, optional
        Tool metadata dicts for function calling
    all : bool
        If True, return full result dict; else last response / tool output
    """
    if tools is None:
        ensure_ollama_available()
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": 500},
        }
        response = requests.post(CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        result = response.json()
        return result["message"]["content"]

    ensure_ollama_available()
    body = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "options": {"num_predict": 500},
    }
    response = requests.post(CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    result = response.json()

    if "tool_calls" in result.get("message", {}):
        tool_calls = result["message"]["tool_calls"]
        for tool_call in tool_calls:
            func_name = tool_call["function"]["name"]
            raw_args = tool_call["function"].get("arguments", {})
            func_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            func = globals().get(func_name)
            if func is None:
                for depth in range(1, 6):
                    try:
                        frame = sys._getframe(depth)
                        func = frame.f_globals.get(func_name)
                        if func is not None:
                            break
                    except ValueError:
                        break
            if func:
                tool_output = func(**func_args)
                tool_call["output"] = tool_output

    if all:
        return result
    if "tool_calls" in result.get("message", {}):
        tool_calls = result["message"]["tool_calls"]
        if output == "tools":
            return tool_calls
        return tool_calls[-1].get("output", result["message"]["content"])
    return result["message"]["content"]


def agent_run(role, task, tools=None, output="text", model=DEFAULT_MODEL):
    """
    Run an agent with a system role and user task. Optionally pass tools for function calling.

    Parameters
    ----------
    role : str
        System prompt (agent identity / instructions)
    task : str
        User message
    tools : list, optional
        Tool metadata for Ollama function calling
    output : str
    model : str

    Returns
    -------
    str or list
        Agent response or tool output (see agent())
    """
    messages = [
        {"role": "system", "content": role},
        {"role": "user", "content": task},
    ]
    return agent(messages=messages, model=model, output=output, tools=tools)


def df_as_text(df):
    """Convert a pandas DataFrame to a markdown table string."""
    return df.to_markdown(index=False)
