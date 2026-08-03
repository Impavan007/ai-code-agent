import re
from typing import List, Dict, Any
from config import AgentConfig
from llm_client import OllamaLLMClient
from tools import SafeToolExecutor, ToolError
from logger import AgentLogger

class CodingAgent:
    """
    Main orchestrator for the AI coding agent loop.
    Manages chat history, executes tool calls, parses execution phases, and applies safety checks.
    """
    def __init__(self, config: AgentConfig, system_prompt: str, initial_task: str):
        self.config = config
        self.system_prompt = system_prompt
        self.initial_task = initial_task
        
        self.logger = AgentLogger(config.log_dir)
        self.llm_client = OllamaLLMClient(
            model=config.model,
            temperature=config.temperature,
            api_key=config.ollama_api_key
        )
        self.executor = SafeToolExecutor(config.target_repo_path)
        
        # Configure backups directory matching the unique run timestamp
        import os
        log_basename = os.path.basename(self.logger.log_file)
        timestamp = log_basename.replace("agent_run_", "").replace(".jsonl", "")
        self.backup_dir = os.path.join(self.config.log_dir, f"backups_{timestamp}")
        self.executor.set_backup_dir(self.backup_dir)
        
        # Initialize conversation messages
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Please implement the following task:\n\n{self.initial_task}"}
        ]
        
        self.is_finished = False
        self.plan_saved = False

    def run(self, max_turns: int = 40):
        """Runs the main autonomous loop up to max_turns."""
        self.logger.log_system("Starting autonomous coding agent loop...")
        self.logger.log_system(f"Target repository: {self.config.target_repo_path}")
        self.logger.log_system(f"Model: {self.config.model}")
        self.logger.log_system(f"Structured logs will be saved to: {self.logger.log_file}")

        for turn in range(1, max_turns + 1):
            if self.is_finished:
                break
                
            self.logger.log_system(f"=== Starting Turn {turn}/{max_turns} ===")
            
            # Prune old context if messages list is getting extremely long to avoid context bloat
            self._prune_context()

            try:
                # LLM turn
                response = self.llm_client.chat(self.messages)
                
                # Extract response text reasoning/thought
                content = response.get("message", {}).get("content", "")
                if content:
                    self.logger.log_agent_thought(content)
                    
                    # Detect and save Phase 3 Plan if generated and not already saved
                    if "PHASE 3" in content.upper() and not self.plan_saved:
                        self._extract_and_save_plan(content)

                # Add assistant message to history
                self.messages.append(response.get("message"))

                # Check for tool calls
                tool_calls = response.get("message", {}).get("tool_calls", [])
                if not tool_calls:
                    if not content:
                        self.logger.log_system("Model returned empty response and no tool calls. Retrying...")
                        continue
                    else:
                        # If the model returned text but no tool calls, check if it is concluding.
                        content_lower = content.lower()
                        is_concluding = (
                            turn > 1 and (
                                "what was implemented" in content_lower or
                                "files changed" in content_lower or
                                "how to verify" in content_lower or
                                "accomplished tasks" in content_lower or
                                "final summary" in content_lower
                            )
                        )
                        if is_concluding:
                            self.is_finished = True
                            self.logger.save_phase_artifact("Summary", content)
                            self.logger.log_system("Model returned final summary text without tool calls. Auto-finishing.")
                            break
                        else:
                            continue

                # Process tool calls
                for tool_call in tool_calls:
                    function_info = tool_call.get("function", {})
                    name = function_info.get("name")
                    arguments = function_info.get("arguments", {})
                    
                    self.logger.log_tool_call(name, arguments)
                    
                    # Execute tool
                    try:
                        result = self._execute_tool(name, arguments)
                        self.logger.log_tool_result(name, result, success=True)
                        
                        # Add tool response to message history
                        self.messages.append({
                            "role": "tool",
                            "name": name,
                            "content": str(result)
                        })
                    except ToolError as te:
                        self.logger.log_error(str(te))
                        self.logger.log_tool_result(name, str(te), success=False)
                        self.messages.append({
                            "role": "tool",
                            "name": name,
                            "content": f"Error executing tool {name}: {str(te)}"
                        })
                        
            except Exception as e:
                self.logger.log_error(f"Execution error on turn {turn}: {str(e)}")
                self.logger.log_system(f"Please check the full logs at: {self.logger.log_file}")
                break

        # Save the manifest of changed files at the end of the run
        self.save_changes_manifest()

        if not self.is_finished:
            self.logger.log_system("Agent loop finished without explicit finish signal.")

    def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Dispatches a tool call to the safe tool executor."""
        if name == "list_files":
            return self.executor.list_files(
                relative_path=arguments.get("relative_path", ".")
            )
        elif name == "read_file":
            return self.executor.read_file(
                relative_path=arguments.get("relative_path"),
                start_line=arguments.get("start_line"),
                end_line=arguments.get("end_line")
            )
        elif name == "write_file":
            return self.executor.write_file(
                relative_path=arguments.get("relative_path"),
                content=arguments.get("content")
            )
        elif name == "edit_file":
            return self.executor.edit_file(
                relative_path=arguments.get("relative_path"),
                target=arguments.get("target"),
                replacement=arguments.get("replacement")
            )
        elif name == "search_code":
            return self.executor.search_code(
                query=arguments.get("query"),
                relative_path=arguments.get("relative_path", ".")
            )
        elif name == "run_command":
            return self.executor.run_command(
                command=arguments.get("command")
            )
        elif name == "finish":
            summary = arguments.get("summary", "")
            self.is_finished = True
            self.logger.save_phase_artifact("Summary", summary)
            return "Task execution marked as finished."
        else:
            raise ToolError(f"Unknown tool name: {name}")

    def _extract_and_save_plan(self, content: str):
        """Attempts to parse Phase 3 (Plan) out of agent reasoning and save it."""
        # Find any text block starting from PHASE 3 till the end or next Phase
        match = re.search(r'(PHASE\s+3.*)', content, re.IGNORECASE | re.DOTALL)
        if match:
            plan_content = match.group(1).strip()
            self.logger.save_phase_artifact("Plan", plan_content)
            self.plan_saved = True

    def _prune_context(self):
        """
        Keeps the context size manageable by replacing the content of old read_file
        tool responses with a summary/truncated representation if they are old.
        """
        # If we have a lot of messages, let's prune the contents of older read_file tool results
        read_file_count = 0
        max_read_file_history = 3  # Keep only the last 3 read_file responses fully in memory
        
        for idx in reversed(range(len(self.messages))):
            msg = self.messages[idx]
            if msg.get("role") == "tool" and msg.get("name") == "read_file":
                read_file_count += 1
                if read_file_count > max_read_file_history:
                    # Prune/truncate this message content
                    content = msg.get("content", "")
                    if len(content) > 200:
                        msg["content"] = f"[Older file read content of {len(content)} chars truncated by harness config to optimize context]"

    def save_changes_manifest(self):
        """Saves a JSON manifest of all files modified/created during this run."""
        import json
        manifest_path = self.logger.log_file.replace("agent_run_", "changes_").replace(".jsonl", ".json")
        manifest_data = {
            "repo_path": self.config.target_repo_path,
            "changes": self.executor.changes_manifest if hasattr(self.executor, "changes_manifest") else []
        }
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)
            self.logger.log_system(f"Saved changes manifest to {manifest_path}")
        except Exception as e:
            self.logger.log_error(f"Failed to save changes manifest: {str(e)}")
