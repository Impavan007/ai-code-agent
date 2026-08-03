# Antigravity AI Agent VS Code Extension

This is a premium, built-in VS Code Extension sidebar interface for the **Antigravity Autonomous Coding Agent**. It brings the terminal-based autonomous loop into a clean, modern graphical chat interface right inside your IDE.

---

## Features

- **Sleek Sidebar UI:** Glassmorphism bubbles, curated dark theme matching VS Code styles, and responsive sizing.
- **Autonomous Log Streaming:** Real-time stdout/stderr console feedback shown collapsible in the chat sidebar.
- **Flexible Models:** Select from active, live Ollama models directly via a dropdown (`qwen3-coder:480b-cloud`, `nemotron-3-super`, `gemma4:31b`, `gpt-oss:20b`).
- **Secure Ollama Login:** Links directly to the Ollama authentication page and securely stores your token using VS Code's native Secret Storage (Keychain).
- **Workspace-Aware:** Automatically targets the open workspace directory as the repo root without having to configure it manually.

---

## How to Install and Run Locally

To run and debug the extension locally in VS Code:

1. **Open the Extension folder:**
   Open a new VS Code window, select **File > Open Folder...**, and select the `vscode-extension/` directory.

2. **Run the Extension Host:**
   - Press **F5** (or go to the **Run and Debug** view in the sidebar and click the **Start Debugging** play icon).
   - This opens a new window called **[Extension Development Host]**.

3. **Configure & Authenticate:**
   - In the Extension Development Host window, open a project you'd like the agent to work on (e.g. `backend_blog`).
   - Click on the new **Antigravity AI** rocket icon on the left Activity Bar.
   - Click the **Sign In** button or run the command `Antigravity: Set Ollama API Key` from the VS Code command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) to enter your Ollama API key.
   - Select your desired model from the dropdown.

4. **Run a Task:**
   - Type a task in the input text area (e.g. `describe me complete project create a description.md in same project directory`) and press **Enter** (or click the Send arrow).
   - Watch the agent run, perform its multi-turn thoughts, execute tools, and stream logs live in the sidebar container!

---

## Troubleshooting

- **Python Executable not found:** If the execution fails to start, verify that Python is in your PATH. If you have a custom path or are using a virtual environment, configure it via VS Code Settings under `Antigravity: Python Path`.
- **Authentication:** If you change your API key, run `Antigravity: Set Ollama API Key` again to overwrite the secure value.
