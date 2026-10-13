"""Local Groq agent orchestration with deterministic Docker-backed EDA tools."""

from __future__ import annotations

import os
from pathlib import Path

from langchain.agents.middleware import TodoListMiddleware

from scripts.ai_agent import AgentConfig, CSVRunContext
from scripts.data_tools import create_local_data_tools


def create_local_agent(backend, config: AgentConfig | None = None):
    """Build the focused local analysis graph with Deep Agents todo planning."""
    from langchain.agents import create_agent
    from langchain_groq import ChatGroq

    selected = config or AgentConfig(
        model_name=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    )
    prompt_path = Path(__file__).parents[1] / "instructions.md"
    instructions = prompt_path.read_text(encoding="utf-8")
    return create_agent(
        model=ChatGroq(
            model=selected.model_name,
            temperature=0,
            max_tokens=1280,
            reasoning_effort="low",
        ),
        tools=create_local_data_tools(backend),
        system_prompt=instructions,
        middleware=[TodoListMiddleware()],
        context_schema=CSVRunContext,
        name=selected.name,
    )
