import os
import shutil
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional

# Ensure .env exists by copying .env.example if missing
if not os.path.exists(".env") and os.path.exists(".env.example"):
    try:
        shutil.copy(".env.example", ".env")
        print("Note: Copied '.env.example' to '.env' because '.env' was missing.")
    except Exception as e:
        print(f"Warning: Failed to copy '.env.example' to '.env': {e}")

load_dotenv()

class AgentConfig(BaseModel):
    """
    Configuration settings for the AI Coding Agent Harness.
    Loads settings from environment variables (including .env file) or CLI.
    """
    model: str = Field(
        default=os.getenv("AGENT_MODEL", "qwen3-coder:480b-cloud"),
        description="The Ollama cloud/local model to target."
    )
    temperature: float = Field(
        default=float(os.getenv("AGENT_TEMPERATURE", "0.2")),
        description="Sampling temperature for code generation."
    )
    target_repo_path: str = Field(
        default=os.getenv("TARGET_REPO_PATH", ""),
        description="Absolute path to the target repository the agent is authorized to modify."
    )
    log_dir: str = Field(
        default=os.getenv("AGENT_LOG_DIR", "logs"),
        description="Directory where agent execution logs and phase summaries are saved."
    )
    ollama_api_key: Optional[str] = Field(
        default=os.getenv("OLLAMA_API_KEY"),
        description="Optional API key for Ollama Cloud (if not using ollama signin locally)."
    )

    def validate_paths(self):
        """Validates that the target repository path exists and is a directory."""
        if not self.target_repo_path:
            raise ValueError(
                "Target repository path is required. "
                "Specify it via the --repo option, or set TARGET_REPO_PATH in your .env file."
            )
            
        if not os.path.exists(self.target_repo_path):
            raise FileNotFoundError(f"Target repository path does not exist: {self.target_repo_path}")
        if not os.path.isdir(self.target_repo_path):
            raise NotADirectoryError(f"Target repository path is not a directory: {self.target_repo_path}")
        
        # Resolve target repo path to its real absolute path
        self.target_repo_path = os.path.abspath(self.target_repo_path)
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
