import os

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

workspace = os.environ.get("SUPER_PROJECTS_WORKDIR", "/workspaces")
chrome_devtools = os.path.join(
    workspace, ".devcontainer", "scripts", "shell", "chrome-devtools-mcp"
)
model_name = os.environ.get("GEMMA_MODEL", "gemma4:e2b")

# LiteLLM reads this for every Ollama call. Compose sets OLLAMA_HOST.
ollama_host = os.environ.get("OLLAMA_HOST", "").rstrip("/")
if ollama_host and not os.environ.get("OLLAMA_API_BASE"):
    os.environ["OLLAMA_API_BASE"] = ollama_host

# The MCP client only inherits HOME, PATH, and a few other names. Without this,
# the launcher falls back to port 9223 while this container's Chrome may not.
chrome_port = os.environ.get("CHROME_REMOTE_DEBUGGING_PORT", "9223")

# Page navigation and inspection. Performance, memory, and CSS tools stay off
# so the model is not given every action the server exposes.
chrome_devtools_tools = [
    "list_pages",
    "new_page",
    "navigate_page",
    "select_page",
    "close_page",
    "take_snapshot",
    "take_screenshot",
    "evaluate_script",
    "click",
    "fill",
    "fill_form",
    "hover",
    "press_key",
    "type_text",
    "wait_for",
    "handle_dialog",
    "resize_page",
    "list_console_messages",
    "get_console_message",
]

root_agent = LlmAgent(
    name="lllm",
    model=LiteLlm(model=f"ollama_chat/{model_name}"),
    description="Local model with Chrome DevTools in the devcontainer.",
    instruction=(
        "You are the local model in the super_projects devcontainer. "
        "Use the Chrome DevTools tools to open and inspect pages when the user "
        "asks about a web page or the browser. Answer directly when a page is "
        "not needed."
    ),
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=chrome_devtools,
                    args=["browsing"],
                    env={"CHROME_REMOTE_DEBUGGING_PORT": chrome_port},
                ),
                timeout=120,
            ),
            tool_filter=chrome_devtools_tools,
        )
    ],
)

app = App(name="lllm", root_agent=root_agent)
