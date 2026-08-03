const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('Antigravity AI Agent Extension is now active!');

    const provider = new AntigravityChatProvider(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'antigravity-agent-chat',
            provider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        )
    );

    // Register Set API Key command
    const setApiKeyCmd = vscode.commands.registerCommand('antigravity.setApiKey', async () => {
        const apiKey = await vscode.window.showInputBox({
            prompt: 'Enter your Ollama API Key (from ollama.com)',
            placeHolder: 'e.g. d4be204c...',
            password: true
        });

        if (apiKey) {
            await context.secrets.store('ollama_api_key', apiKey);
            vscode.window.showInformationMessage('Ollama API Key saved securely!');
            provider.updateWebviewSettings();
        }
    });

    // Register Clear Chat command
    const clearChatCmd = vscode.commands.registerCommand('antigravity.clearChat', () => {
        provider.clearChat();
    });

    context.subscriptions.push(setApiKeyCmd, clearChatCmd);
}

class AntigravityChatProvider {
    /**
     * @param {vscode.ExtensionContext} context
     */
    constructor(context) {
        this.context = context;
        this._view = undefined;
    }

    /**
     * @param {vscode.WebviewView} webviewView
     * @param {vscode.WebviewViewResolveContext} context
     * @param {vscode.CancellationToken} token
     */
    async resolveWebviewView(webviewView, context, token) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Send current configuration to Webview once loaded
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'getSettings':
                    await this.updateWebviewSettings();
                    break;
                case 'sendPrompt':
                    await this.handleSendPrompt(message.data);
                    break;
                case 'selectModel':
                    await vscode.workspace.getConfiguration('antigravity').update('model', message.data, vscode.ConfigurationTarget.Global);
                    break;
                case 'openSignIn':
                    vscode.env.openExternal(vscode.Uri.parse('https://ollama.com'));
                    break;
                case 'rejectChanges':
                    await this.handleRejectChanges(message.manifestPath);
                    break;
                case 'acceptChanges':
                    await this.handleAcceptChanges(message.manifestPath);
                    break;
            }
        });
    }

    async updateWebviewSettings() {
        if (!this._view) return;
        const config = vscode.workspace.getConfiguration('antigravity');
        const model = config.get('model') || 'qwen3-coder:480b-cloud';
        const apiKey = await this.context.secrets.get('ollama_api_key');
        
        this._view.webview.postMessage({
            type: 'settings',
            data: {
                model,
                hasApiKey: !!apiKey
            }
        });
    }

    clearChat() {
        if (this._view) {
            this._view.webview.postMessage({ type: 'clearChat' });
        }
    }

    /**
     * @param {string} promptText
     */
    async handleSendPrompt(promptText) {
        if (!this._view) return;
        let logPath = null;

        const config = vscode.workspace.getConfiguration('antigravity');
        const model = config.get('model') || 'qwen3-coder:480b-cloud';
        const temperature = config.get('temperature') || 0.2;
        const apiKey = await this.context.secrets.get('ollama_api_key');

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            this._view.webview.postMessage({
                type: 'error',
                data: 'Please open a project folder in VS Code first to use the agent.'
            });
            return;
        }

        const repoPath = workspaceFolders[0].uri.fsPath;
        // The main.py file is located in the extension root (which is parent of vscode-extension)
        // If loaded locally in development, extensionPath is the root folder.
        const extensionPath = this.context.extensionPath;
        // We look for main.py in the extension folder or its parent to handle both installed and dev cases
        let mainPyPath = path.join(extensionPath, 'main.py');
        let cwd = extensionPath;

        if (!fs.existsSync(mainPyPath)) {
            // Dev setup: main.py might be in the parent directory of vscode-extension
            mainPyPath = path.join(path.dirname(extensionPath), 'main.py');
            cwd = path.dirname(extensionPath);
        }

        const pythonExecutable = vscode.workspace.getConfiguration('antigravity').get('pythonPath') || 'python';
        const env = { ...process.env };
        if (apiKey) {
            env.OLLAMA_API_KEY = apiKey;
        }
        env.AGENT_MODEL = model;
        env.AGENT_TEMPERATURE = String(temperature);
        env.PYTHONUNBUFFERED = '1';

        this._view.webview.postMessage({ type: 'status', data: 'Spawning agent loop...' });

        const args = [mainPyPath, '--repo', repoPath, '--task', promptText];
        const child = spawn(pythonExecutable, args, { env, cwd });

        child.stdout.on('data', (data) => {
            const text = data.toString('utf8');
            this._view.webview.postMessage({ type: 'log', data: text });
            
            const logMatch = text.match(/Structured logs will be saved to:\s*(.*\.jsonl)/i);
            if (logMatch) {
                logPath = logMatch[1].trim();
            }
        });

        child.stderr.on('data', (data) => {
            const text = data.toString('utf8');
            this._view.webview.postMessage({ type: 'log', data: text });
        });

        child.on('error', (err) => {
            this._view.webview.postMessage({
                type: 'error',
                data: `Failed to start Python process: ${err.message}. Please ensure Python is installed and configured in your PATH or configured in settings.`
            });
        });

        child.on('close', (code) => {
            if (code === 0) {
                let summary = 'Task execution completed successfully.';
                let changes = [];
                let changesPath = '';

                if (logPath) {
                    changesPath = logPath.replace("agent_run_", "changes_").replace(".jsonl", ".json");
                    const summaryPath = path.join(path.dirname(logPath), 'summary.md');

                    if (fs.existsSync(summaryPath)) {
                        summary = fs.readFileSync(summaryPath, 'utf8');
                    }
                    if (fs.existsSync(changesPath)) {
                        try {
                            const manifest = JSON.parse(fs.readFileSync(changesPath, 'utf8'));
                            changes = manifest.changes || [];
                        } catch (e) {
                            console.error('Failed to parse changes JSON', e);
                        }
                    }
                }

                this._view.webview.postMessage({ 
                    type: 'runCompleted', 
                    data: { 
                        status: 'Finished successfully!',
                        summary,
                        changes,
                        manifestPath: changesPath
                    } 
                });
            } else {
                this._view.webview.postMessage({ type: 'status', data: `Process exited with code ${code}` });
            }
        });
    }

    /**
     * @param {vscode.Webview} webview
     */
    _getHtmlForWebview(webview) {
        const extensionPath = this.context.extensionPath;
        let htmlPath = path.join(extensionPath, 'webview.html');
        if (!fs.existsSync(htmlPath)) {
            htmlPath = path.join(extensionPath, 'vscode-extension', 'webview.html');
        }

        try {
            let htmlContent = fs.readFileSync(htmlPath, 'utf8');
            return htmlContent;
        } catch (e) {
            return `<html><body>Error loading Webview content: ${e.message}</body></html>`;
        }
    }

    async handleRejectChanges(manifestPath) {
        if (!this._view) return;
        try {
            if (!manifestPath || !fs.existsSync(manifestPath)) {
                this._view.webview.postMessage({ type: 'error', data: 'Changes manifest file not found.' });
                return;
            }
            const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
            const repoPath = manifest.repo_path;
            const logDir = path.dirname(manifestPath);

            for (const change of manifest.changes) {
                const filePath = path.join(repoPath, change.file);
                if (change.type === 'new') {
                    if (fs.existsSync(filePath)) {
                        fs.unlinkSync(filePath);
                        this._view.webview.postMessage({ type: 'log', data: `Deleted created file: ${change.file}` });
                    }
                } else if (change.type === 'modify') {
                    const backupPath = path.join(logDir, change.backup_path);
                    if (fs.existsSync(backupPath)) {
                        fs.copyFileSync(backupPath, filePath);
                        this._view.webview.postMessage({ type: 'log', data: `Restored original state of: ${change.file}` });
                    }
                }
            }
            this._view.webview.postMessage({ type: 'status', data: 'Changes successfully reverted!' });
            this._view.webview.postMessage({ type: 'revertCompleted' });
        } catch (err) {
            this._view.webview.postMessage({ type: 'error', data: `Failed to revert changes: ${err.message}` });
        }
    }

    async handleAcceptChanges(manifestPath) {
        if (!this._view) return;
        this._view.webview.postMessage({ type: 'status', data: 'Changes accepted successfully!' });
    }
}

function deactivate() {}

module.exports = {
    activate,
    deactivate
};
