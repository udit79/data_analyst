"""Managed Deep Agent project entry point."""

from typing import TYPE_CHECKING, cast

from langchain.agents.middleware import TodoListMiddleware
from managed_deepagents import define_deep_agent

from scripts.ai_agent import CSVRunContext
from scripts.artifacts import create_artifact_download_tool
from scripts.data_tools import create_data_tools

if TYPE_CHECKING:
    from managed_deepagents.define_deep_agent import DeepAgentMiddleware

agent = define_deep_agent(
    name="data-agent",
    model="groq:openai/gpt-oss-20b",
    context_schema=CSVRunContext,
    tools=[*create_data_tools(), create_artifact_download_tool()],
    middleware=[cast("DeepAgentMiddleware", TodoListMiddleware())],
)
