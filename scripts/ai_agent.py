from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict, cast

from dotenv import load_dotenv

if TYPE_CHECKING:
    from managed_deepagents.define_deep_agent import DeepAgentMiddleware


class CSVRunContext(TypedDict):
    """Host-provided sample data, available to tools but absent from the prompt."""

    csv_data: str


@dataclass(frozen=True)
class AgentConfig:
    """Explicit Managed Deep Agent and model selection."""

    name: str = "data-agent"
    model_backend: Literal["groq"] = "groq"
    model_name: str = "openai/gpt-oss-20b"

    @property
    def model_spec(self) -> str:
        return f"{self.model_backend}:{self.model_name}"


class AIAgent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        if self.config.model_backend != "groq":
            raise ValueError(f"Unsupported model backend: {self.config.model_backend}")
        load_dotenv()

    def create_graph(self, *, define_agent=None, todo_middleware=None, artifact_tool=None, data_tools=None):
        """Declare the managed agent; Managed Deep Agents provides its backend."""
        if define_agent is None:
            from managed_deepagents import define_deep_agent

            define_agent = define_deep_agent
        if todo_middleware is None:
            from langchain.agents.middleware import TodoListMiddleware

            todo_middleware = TodoListMiddleware
        if artifact_tool is None:
            from scripts.artifacts import create_artifact_download_tool

            artifact_tool = create_artifact_download_tool()
        if data_tools is None:
            from scripts.data_tools import create_data_tools

            data_tools = create_data_tools()

        return define_agent(
            name=self.config.name,
            model=self.config.model_spec,
            context_schema=CSVRunContext,
            tools=[*data_tools, artifact_tool],
            # TodoListMiddleware adds planning state, but MDA aliases LangChain's
            # narrower base AgentMiddleware type; the runtime supports this middleware.
            middleware=[cast("DeepAgentMiddleware", todo_middleware())],
        )

    def process_data(self,df,batch_size=20):
        cleaned_responses=[]
        return cleaned_responses
