import os
import sys

# Reconfigure stdout/stderr to UTF-8 to prevent encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import argparse
from config import AgentConfig
from agent import CodingAgent

def extract_system_prompt(prompt_filepath: str) -> str:
    """Reads prompt.md and extracts the verbatim system prompt between the first code block."""
    if not os.path.exists(prompt_filepath):
        raise FileNotFoundError(f"Could not find system prompt file at: {prompt_filepath}")
        
    with open(prompt_filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Search for the block under ## SYSTEM PROMPT
    # We look for the first code block ``` after the header
    marker = "## SYSTEM PROMPT"
    if marker not in content:
        raise ValueError(f"Could not find marker '{marker}' in prompt file.")
        
    header_idx = content.find(marker)
    remaining = content[header_idx:]
    
    # Extract the block within the triple backticks
    block_start = remaining.find("```")
    if block_start == -1:
        raise ValueError("Could not find start of the system prompt code block (```).")
        
    # Skip the opening backticks and any optional language identifier (e.g. ```text)
    newline_idx = remaining.find("\n", block_start)
    if newline_idx == -1:
         raise ValueError("Malformed prompt file structure.")
         
    block_end = remaining.find("```", newline_idx)
    if block_end == -1:
        raise ValueError("Could not find end of the system prompt code block (```).")
        
    system_prompt = remaining[newline_idx + 1:block_end].strip()
    return system_prompt

def run_interactive_loop(prompt_file: str):
    """Runs a continuous interactive CLI shell prompt loop."""
    from rich.prompt import Prompt
    from rich.console import Console
    from dotenv import load_dotenv
    
    load_dotenv()
    console = Console()
    
    console.print("\n[bold blue]=== Welcome to the Autonomous Coding Agent Interactive Shell ===[/bold blue]\n")
    
    current_repo = os.getenv("TARGET_REPO_PATH", "")
    current_model = os.getenv("AGENT_MODEL", "qwen3-coder:480b-cloud")
    current_temp = float(os.getenv("AGENT_TEMPERATURE", "0.2"))
    current_log_dir = os.getenv("AGENT_LOG_DIR", "logs")
    
    while True:
        console.print("[bold cyan]--- New Task Session ---[/bold cyan]")
        
        # Get target repo path
        while True:
            repo_path = Prompt.ask("Enter target repository path", default=current_repo)
            if not repo_path:
                console.print("[bold red]Error: Repository path cannot be empty.[/bold red]")
                continue
            if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
                console.print(f"[bold red]Error: Path '{repo_path}' does not exist or is not a directory.[/bold red]")
                continue
            current_repo = os.path.abspath(repo_path)
            break
            
        # Get task description
        task = Prompt.ask("Enter task instruction")
        if not task.strip():
            console.print("[bold red]Error: Task instruction cannot be empty.[/bold red]")
            continue
            
        # Optional settings prompt
        configure_settings = Prompt.ask("Configure advanced settings (model, temperature, log_dir)?", choices=["y", "n"], default="n")
        if configure_settings == "y":
            current_model = Prompt.ask("Model to use", default=current_model)
            temp_str = Prompt.ask("Sampling temperature (0.0 to 1.0)", default=str(current_temp))
            try:
                current_temp = float(temp_str)
            except ValueError:
                console.print(f"[warning]Invalid float. Keeping temperature at {current_temp}[/warning]")
            current_log_dir = Prompt.ask("Log directory", default=current_log_dir)
            
        # Run the agent
        console.print(f"\n[bold green]Starting Agent run against repository: {current_repo}[/bold green]\n")
        try:
            config = AgentConfig(
                model=current_model,
                temperature=current_temp,
                target_repo_path=current_repo,
                log_dir=current_log_dir
            )
            config.validate_paths()
            
            system_prompt = extract_system_prompt(prompt_file)
            
            agent = CodingAgent(
                config=config,
                system_prompt=system_prompt,
                initial_task=task
            )
            agent.run()
            
            console.print("\n[bold success]✔ Agent completed task run![/bold success]")
            
        except Exception as e:
            console.print(f"\n[bold error]✘ Agent run failed with error: {str(e)}[/bold error]")
            
        console.print("\n" + "="*60 + "\n")
        
        # Ask to continue
        run_another = Prompt.ask("Would you like to run another task?", choices=["y", "n"], default="y")
        if run_another == "n":
            console.print("[bold blue]Exiting Interactive Shell. Goodbye![/bold blue]")
            break

def main():
    parser = argparse.ArgumentParser(description="Autonomous Coding Agent Python Harness")
    parser.add_argument(
        "--repo",
        help="Absolute path to the target repository. Defaults to TARGET_REPO_PATH in environment."
    )
    parser.add_argument(
        "--task",
        help="Plain English description of the coding task to accomplish. If omitted, starts interactive shell."
    )
    parser.add_argument(
        "--model",
        help="Model to use. Defaults to AGENT_MODEL in environment."
    )
    parser.add_argument(
        "--temp",
        type=float,
        help="Temperature for model sampling. Defaults to AGENT_TEMPERATURE in environment."
    )
    parser.add_argument(
        "--log-dir",
        help="Directory to save run logs. Defaults to AGENT_LOG_DIR in environment."
    )
    parser.add_argument(
        "--prompt-file",
        default="prompt.md",
        help="Path to the system prompt markdown file (default: prompt.md)."
    )

    args = parser.parse_args()

    # If --task is omitted, trigger interactive prompt loop
    if args.task is None:
        run_interactive_loop(args.prompt_file)
        return

    try:
        # Build config overrides from CLI only for arguments that were explicitly provided
        config_overrides = {}
        if args.repo is not None:
            config_overrides["target_repo_path"] = args.repo
        if args.model is not None:
            config_overrides["model"] = args.model
        if args.temp is not None:
            config_overrides["temperature"] = args.temp
        if args.log_dir is not None:
            config_overrides["log_dir"] = args.log_dir

        config = AgentConfig(**config_overrides)
        config.validate_paths()
        
        # Load system prompt
        system_prompt = extract_system_prompt(args.prompt_file)
        
        # Initialize and run agent
        agent = CodingAgent(
            config=config,
            system_prompt=system_prompt,
            initial_task=args.task
        )
        agent.run()
        
    except Exception as e:
        print(f"Harness startup failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
