import os
import json
import time
from typing import Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# Custom theme for beautiful terminal output
theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "success": "bold green",
    "agent": "bold blue",
    "tool": "bold yellow",
    "system": "bold white",
})

class AgentLogger:
    """
    Handles structured logging to JSONLines file and beautiful,
    rich terminal formatting for user observation.
    """
    def __init__(self, log_dir: str):
        self.console = Console(theme=theme)
        self.log_dir = os.path.abspath(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Unique log file for this run
        self.log_file = os.path.join(self.log_dir, f"agent_run_{int(time.time())}.jsonl")

    def _write_log(self, entry: Dict[str, Any]):
        """Append a JSON entry to the run log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_system(self, message: str):
        self.console.print(f"[system]System:[/system] {message}")
        self._write_log({"timestamp": time.time(), "type": "system", "message": message})

    def log_agent_thought(self, thought: str):
        if not thought.strip():
            return
        panel = Panel(
            Text(thought, style="agent"),
            title="[agent]Agent Thought / Reasoning[/agent]",
            border_style="blue",
            expand=False
        )
        self.console.print(panel)
        self._write_log({"timestamp": time.time(), "type": "thought", "content": thought})

    def log_tool_call(self, tool_name: str, arguments: Dict[str, Any]):
        self.console.print(f"[tool]Tool Call -> {tool_name}[/tool] with arguments: {json.dumps(arguments, indent=2)}")
        self._write_log({"timestamp": time.time(), "type": "tool_call", "name": tool_name, "arguments": arguments})

    def log_tool_result(self, tool_name: str, result: Any, success: bool = True):
        style = "success" if success else "error"
        status_text = "Success" if success else "Failed"
        
        # Truncate large results for screen display
        result_str = str(result)
        display_str = result_str
        if len(result_str) > 1000:
            display_str = result_str[:1000] + "\n... [TRUNCATED FOR SCREEN] ..."
            
        panel = Panel(
            Text(display_str, style="white"),
            title=f"[{style}]Tool Result ({status_text}) <- {tool_name}[/{style}]",
            border_style="green" if success else "red",
            expand=False
        )
        self.console.print(panel)
        self._write_log({"timestamp": time.time(), "type": "tool_result", "name": tool_name, "success": success, "result": result_str})

    def log_error(self, message: str):
        self.console.print(f"[error]ERROR:[/error] {message}")
        self._write_log({"timestamp": time.time(), "type": "error", "message": message})

    def save_phase_artifact(self, phase_name: str, content: str):
        """Saves a milestone document (e.g. Plan, Summary) to its own markdown file."""
        filename = f"{phase_name.lower().replace(' ', '_')}.md"
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self.console.print(f"[info]Saved {phase_name} artifact to [bold]{filepath}[/bold][/info]")
        self._write_log({"timestamp": time.time(), "type": "artifact", "phase": phase_name, "path": filepath})
