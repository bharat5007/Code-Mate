import * as vscode from "vscode";

const API_BASE = "http://localhost:8000";
const MAX_SESSIONS = 3;

export class ChatViewProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private repoPath: string;
  private sessions: string[];      // list of threadIds
  private activeSession: number;   // index into sessions

  constructor(_context: vscode.ExtensionContext) {
    this.repoPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";
    this.sessions = [crypto.randomUUID()];
    this.activeSession = 0;
  }

  private get threadId(): string {
    return this.sessions[this.activeSession];
  }

  resolveWebviewView(webviewView: vscode.WebviewView) {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.getHtml();

    this.initializeBackend();

    webviewView.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === "query") {
        const data = await this.sendQuery(msg.text);
        if (data.pending_edit) {
          webviewView.webview.postMessage({ type: "pending_edit", edit: data.pending_edit });
        } else {
          webviewView.webview.postMessage({ type: "response", text: data.results ?? "No results found" });
        }
      }

      if (msg.type === "approve_edit") {
        const result = await this.approveEdit(msg.accepted);
        webviewView.webview.postMessage({ type: "response", text: result });
      }

      if (msg.type === "switch_session") {
        this.activeSession = msg.index;
        await this.loadPreviousMessages();
      }

      if (msg.type === "new_session") {
        if (this.sessions.length >= MAX_SESSIONS) return;
        this.sessions.push(crypto.randomUUID());
        this.activeSession = this.sessions.length - 1;
        webviewView.webview.postMessage({
          type: "session_created",
          sessions: this.sessions.length,
          active: this.activeSession,
        });
        webviewView.webview.postMessage({ type: "ready" });
      }
    });
  }

  private async initializeBackend() {
    try {
      const res = await fetch(`${API_BASE}/initialize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_path: this.repoPath,
          exclude_dirs: [".venv", "node_modules", "__pycache__"],
          exclude_files: ["setup.py"],
        }),
      });
      const data = (await res.json()) as { Message: string; Indexing_exist: boolean };

      if (data.Indexing_exist) {
        await this.loadPreviousMessages();
      } else {
        this._view?.webview.postMessage({ type: "ready" });
      }
    } catch {
      this._view?.webview.postMessage({ type: "init_error" });
      vscode.window.showErrorMessage("Code Mate: Backend not running");
    }
  }

  private async loadPreviousMessages() {
    try {
      const res = await fetch(
        `${API_BASE}/messages?repo_path=${encodeURIComponent(this.repoPath)}&thread_id=${this.threadId}`
      );
      const data = (await res.json()) as { messages: string[] };
      const msgs = (data.messages ?? []).map((text, i) => ({
        text,
        role: i % 2 === 0 ? "user" : "bot",
      }));
      this._view?.webview.postMessage({ type: "history", messages: msgs });
    } catch {
      this._view?.webview.postMessage({ type: "ready" });
    }
  }

  async sendQuery(query: string): Promise<{ results?: string; pending_edit?: { tool: string; tool_input: string } }> {
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_path: this.repoPath,
          query,
          n: 10,
          thread_id: this.threadId,
        }),
      });
      return await res.json();
    } catch {
      return { results: "Error: Backend not reachable" };
    }
  }

  private async approveEdit(accepted: boolean): Promise<string> {
    try {
      const res = await fetch(`${API_BASE}/approve_edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: this.threadId,
          decision: accepted ? "approve" : "decline",
        }),
      });
      const data = (await res.json()) as { results?: string };
      return data.results ?? (accepted ? "Edit applied." : "Edit declined.");
    } catch {
      return "Error: Backend not reachable";
    }
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html>
<head>
<style>
  * { box-sizing: border-box; }
  body { font-family: var(--vscode-font-family); padding: 0; margin: 0; display: flex; flex-direction: column; height: 100vh; }

  #session-bar { display: flex; align-items: center; gap: 4px; padding: 6px 8px; border-bottom: 1px solid var(--vscode-panel-border); flex-shrink: 0; }
  .session-btn { background: transparent; color: var(--vscode-foreground); border: 1px solid var(--vscode-panel-border); border-radius: 4px; padding: 3px 10px; cursor: pointer; font-size: 0.8em; opacity: 0.6; }
  .session-btn.active { background: var(--vscode-button-background); color: var(--vscode-button-foreground); opacity: 1; border-color: transparent; }
  #new-session-btn { margin-left: auto; background: transparent; color: var(--vscode-foreground); border: 1px dashed var(--vscode-panel-border); border-radius: 4px; padding: 3px 8px; cursor: pointer; font-size: 0.8em; }
  #new-session-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  #messages { flex: 1; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 8px; }
  .msg { padding: 6px 10px; border-radius: 6px; max-width: 90%; word-wrap: break-word; white-space: pre-wrap; }
  .user { background: var(--vscode-button-background); color: var(--vscode-button-foreground); align-self: flex-end; }
  .bot  { background: var(--vscode-editor-inactiveSelectionBackground); align-self: flex-start; }
  .info { color: var(--vscode-descriptionForeground); font-size: 0.85em; align-self: center; }

  #input-row { display: flex; padding: 8px; gap: 6px; border-top: 1px solid var(--vscode-panel-border); flex-shrink: 0; }
  #input { flex: 1; background: var(--vscode-input-background); color: var(--vscode-input-foreground); border: 1px solid var(--vscode-input-border); border-radius: 4px; padding: 6px; resize: none; font-family: inherit; font-size: inherit; }
  #input:disabled, #send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  #send-btn { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; }

  .pending-edit { border: 1px solid var(--vscode-editorWidget-border, #454545); border-radius: 6px; overflow: hidden; align-self: stretch; max-width: 100%; }
  .edit-meta { background: var(--vscode-editorGroupHeader-tabsBackground); padding: 6px 10px; font-size: 0.8em; display: flex; gap: 8px; align-items: center; }
  .edit-tool { background: var(--vscode-badge-background); color: var(--vscode-badge-foreground); border-radius: 3px; padding: 1px 6px; font-family: monospace; }
  .edit-file { color: var(--vscode-descriptionForeground); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .edit-code { margin: 0; padding: 8px 10px; font-family: var(--vscode-editor-font-family, monospace); font-size: 0.85em; background: var(--vscode-editor-background); overflow-x: auto; max-height: 200px; overflow-y: auto; white-space: pre; }
  .edit-actions { display: flex; gap: 8px; padding: 8px 10px; border-top: 1px solid var(--vscode-panel-border); }
  .accept-btn { background: #2d7d46; color: #fff; border: none; border-radius: 4px; padding: 4px 14px; cursor: pointer; font-size: 0.85em; }
  .accept-btn:hover { background: #3a9d59; }
  .decline-btn { background: transparent; color: var(--vscode-errorForeground, #f48771); border: 1px solid var(--vscode-errorForeground, #f48771); border-radius: 4px; padding: 4px 14px; cursor: pointer; font-size: 0.85em; }
  .decline-btn:hover { background: rgba(244,135,113,0.1); }
  .accept-btn:disabled, .decline-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>

<div id="session-bar">
  <button class="session-btn active" onclick="switchSession(0)">Chat 1</button>
  <button id="new-session-btn" onclick="newSession()">+ New</button>
</div>

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
  const sessionBar = document.getElementById('session-bar');
  const newSessionBtn = document.getElementById('new-session-btn');

  let totalSessions = 1;
  let activeSession = 0;

  function addMsg(text, role) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function setReady(msg) {
    messages.innerHTML = '';
    if (msg) addMsg(msg, 'info');
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }

  function updateSessionBar() {
    // Remove existing session buttons (keep new-session-btn)
    sessionBar.querySelectorAll('.session-btn').forEach(b => b.remove());
    for (let i = 0; i < totalSessions; i++) {
      const btn = document.createElement('button');
      btn.className = 'session-btn' + (i === activeSession ? ' active' : '');
      btn.textContent = 'Chat ' + (i + 1);
      btn.onclick = () => switchSession(i);
      sessionBar.insertBefore(btn, newSessionBtn);
    }
    newSessionBtn.disabled = totalSessions >= ${MAX_SESSIONS};
  }

  function switchSession(index) {
    activeSession = index;
    updateSessionBar();
    messages.innerHTML = '';
    addMsg('Loading...', 'info');
    input.disabled = true;
    sendBtn.disabled = true;
    vscode.postMessage({ type: 'switch_session', index });
  }

  function newSession() {
    if (totalSessions >= ${MAX_SESSIONS}) return;
    vscode.postMessage({ type: 'new_session' });
  }

  function send() {
    const text = input.value.trim();
    if (!text) return;
    addMsg(text, 'user');
    input.value = '';
    addMsg('...', 'bot');
    vscode.postMessage({ type: 'query', text });
  }

  function escHtml(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function showPendingEdit(edit) {
    // Remove the '...' placeholder
    const bots = messages.querySelectorAll('.bot');
    const last = bots[bots.length - 1];
    if (last && last.textContent === '...') last.remove();

    let toolInput = {};
    try { toolInput = JSON.parse(edit.tool_input); } catch {}

    const filePath = toolInput.file_path ?? '';
    const code = toolInput.new_code ?? toolInput.new_content ?? '';
    const lineInfo = edit.tool === 'edit_lines'
      ? \` (lines \${toolInput.start_line}–\${toolInput.end_line})\`
      : '';

    const card = document.createElement('div');
    card.className = 'pending-edit';
    card.innerHTML =
      '<div class="edit-meta">' +
        '<span class="edit-tool">' + escHtml(edit.tool) + '</span>' +
        '<span class="edit-file" title="' + escHtml(filePath) + '">' + escHtml(filePath.split('/').pop() + lineInfo) + '</span>' +
      '</div>' +
      '<pre class="edit-code">' + escHtml(code) + '</pre>' +
      '<div class="edit-actions">' +
        '<button class="accept-btn" onclick="approveEdit(true)">&#10003; Accept</button>' +
        '<button class="decline-btn" onclick="approveEdit(false)">&#10007; Decline</button>' +
      '</div>';
    messages.appendChild(card);
    messages.scrollTop = messages.scrollHeight;
  }

  function approveEdit(accepted) {
    document.querySelectorAll('.accept-btn, .decline-btn').forEach(b => b.disabled = true);
    addMsg(accepted ? 'Applying edit...' : 'Declining edit...', 'info');
    input.disabled = true;
    sendBtn.disabled = true;
    vscode.postMessage({ type: 'approve_edit', accepted });
  }

  window.addEventListener('message', e => {
    const d = e.data;

    if (d.type === 'ready') { setReady('Ready! Ask about your code.'); return; }
    if (d.type === 'init_error') { setReady('Backend not running. Start uvicorn first.'); return; }

    if (d.type === 'history') {
      messages.innerHTML = '';
      if (d.messages.length === 0) addMsg('No previous messages.', 'info');
      else d.messages.forEach(m => addMsg(m.text, m.role));
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
      return;
    }

    if (d.type === 'session_created') {
      totalSessions = d.sessions;
      activeSession = d.active;
      updateSessionBar();
      return;
    }

    if (d.type === 'pending_edit') {
      showPendingEdit(d.edit);
      return;
    }

    if (d.type === 'response') {
      const bots = messages.querySelectorAll('.bot');
      const last = bots[bots.length - 1];
      if (last && last.textContent === '...') last.textContent = d.text;
      else addMsg(d.text, 'bot');
      input.disabled = false;
      sendBtn.disabled = false;
      return;
    }
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
</script>
</body>
</html>`;
  }
}
