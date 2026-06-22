import * as vscode from "vscode";

const API_BASE = "http://localhost:8000"; // ← BACKEND URL

export class ChatViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private repoPath: string;

  constructor(private readonly context: vscode.ExtensionContext) {
    this.repoPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";
  }

  resolveWebviewView(webviewView: vscode.WebviewView) {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.getHtml();

    // Extension initializes backend with repo path on startup
    // ↓ BACKEND CONNECTION 1: /initialize
    this.initializeBackend();

    // Handle messages from webview
    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "query") {
        const response = await this.sendQuery(msg.text); // ← BACKEND CONNECTION 2
        webviewView.webview.postMessage({ type: "response", text: response });
      }
    });
  }

  // ↓ BACKEND CONNECTION 1: POST /initialize
  private async initializeBackend() {
    try {
      await fetch(`${API_BASE}/initialize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_path: this.repoPath,
          exclude_dirs: [".venv", "node_modules", "__pycache__"],
          exclude_files: ["setup.py"],
        }),
      });
      this._view?.webview.postMessage({ type: "ready" });
    } catch (e) {
      this._view?.webview.postMessage({ type: "init_error" });
      vscode.window.showErrorMessage("Code Mate: Backend not running");
    }
  }

  // ↓ BACKEND CONNECTION 2: POST /query
  async sendQuery(query: string): Promise<string> {
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_path: this.repoPath, query, n: 10 }),
      });
      const data = (await res.json()) as { results: string };
      return data.results ?? "No results found";
    } catch {
      return "Error: Backend not reachable";
    }
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: var(--vscode-font-family); padding: 0; margin: 0; display: flex; flex-direction: column; height: 100vh; }
  #messages { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 8px; }
  .msg { padding: 6px 10px; border-radius: 6px; max-width: 90%; word-wrap: break-word; white-space: pre-wrap; }
  .user { background: var(--vscode-button-background); color: var(--vscode-button-foreground); align-self: flex-end; }
  .bot  { background: var(--vscode-editor-inactiveSelectionBackground); align-self: flex-start; }
  .info { color: var(--vscode-descriptionForeground); font-size: 0.85em; align-self: center; }
  #input-row { display: flex; padding: 8px; gap: 6px; border-top: 1px solid var(--vscode-panel-border); }
  #input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; padding: 6px; resize: none; font-family: inherit; font-size: inherit; }
  #input:disabled, button:disabled { opacity: 0.5; cursor: not-allowed; }
  button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; }
</style>
</head>
<body>
<div id="messages"><div class="msg info">Initializing...</div></div>
<div id="input-row">
  <textarea id="input" rows="2" placeholder="Ask about your code..." disabled></textarea>
  <button id="send-btn" onclick="send()" disabled>Send</button>
</div>
<script>
  const vscode = acquireVsCodeApi();
  const messages = document.getElementById('messages');
  const input = document.getElementById('input');
  const sendBtn = document.getElementById('send-btn');

  function addMsg(text, role) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function setReady(msg) {
    messages.innerHTML = '';
    addMsg(msg, 'info');
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }

  function send() {
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, 'user');
    input.value = '';
    addMsg('...', 'bot');
    vscode.postMessage({ type: 'query', text });
  }

  window.addEventListener('message', e => {
    if (e.data.type === 'ready') { setReady('Ready! Ask about your code.'); return; }
    if (e.data.type === 'init_error') { setReady('Backend not running. Start uvicorn first.'); return; }

    const msgs = messages.querySelectorAll('.bot');
    const last = msgs[msgs.length - 1];
    if (last && last.textContent === '...') last.textContent = e.data.text;
    else addMsg(e.data.text, 'bot');
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
</script>
</body>
</html>`;
  }
}
