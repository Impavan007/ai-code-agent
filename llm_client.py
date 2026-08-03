import os
from typing import List, Dict, Any, Optional
from ollama import Client

class OllamaLLMClient:
    """
    Wrapper around the Ollama client to support tool-calling schemas
    and standard interactions with Ollama Cloud models.
    """
    def __init__(self, model: str = "qwen3-coder:480b-cloud", temperature: float = 0.2, api_key: Optional[str] = None):
        if model == "qwen3-coder:480b-cloud":
            model = "gemma4:31b"
        self.model = model
        self.temperature = temperature
        
        # If API key is provided, set it in the environment
        host = None
        if api_key:
            os.environ["OLLAMA_API_KEY"] = api_key
            host = "https://ollama.com"
        elif os.environ.get("OLLAMA_API_KEY"):
            host = "https://ollama.com"
            
        self.client = Client(host=host)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns OpenAI-compatible tool definitions for agent tool-use."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "Recursively list all files in the target repository. Excludes typical build/dependency dirs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "Folder relative to the repo root to list from. Default is '.'."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file in the repo. Supports optional start and end line ranges.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "File path relative to the repo root."
                            },
                            "start_line": {
                                "type": "integer",
                                "description": "1-indexed line number to start reading from."
                            },
                            "end_line": {
                                "type": "integer",
                                "description": "1-indexed line number to stop reading at (inclusive)."
                            }
                        },
                        "required": ["relative_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write complete contents to a file. Overwrites the file if it exists, or creates it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "File path relative to the repo root."
                            },
                            "content": {
                                "type": "string",
                                "description": "Complete new content to write to the file."
                            }
                        },
                        "required": ["relative_path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Perform search-and-replace on a block of code. Target content must match exactly one occurrence.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "relative_path": {
                                "type": "string",
                                "description": "File path relative to the repo root."
                            },
                            "target": {
                                "type": "string",
                                "description": "The exact block of code to find and replace."
                            },
                            "replacement": {
                                "type": "string",
                                "description": "The new block of code to replace the target block with."
                            }
                        },
                        "required": ["relative_path", "target", "replacement"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for code occurrences matching the query in the repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The text string to search for in files (case-insensitive)."
                            },
                            "relative_path": {
                                "type": "string",
                                "description": "Repository subdirectory to narrow the search scope. Default is '.'."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell/terminal command inside the repository root directory. Output is returned.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The exact shell command to execute."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "finish",
                    "description": "Signal that the task is completed. Provide your final Phase 6 summary.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "The detailed Phase 6 summary describing what was changed, why, and how to verify."
                            }
                        },
                        "required": ["summary"]
                    }
                }
            }
        ]

    def chat(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sends the messages history (including system prompt) to Ollama.
        Forces tool-calling if the model chooses to call a tool.
        """
        tools = self.get_tool_definitions()
        response = self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            options={
                "temperature": self.temperature,
            }
        )
        return response
