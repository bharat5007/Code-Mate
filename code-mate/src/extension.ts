import * as vscode from "vscode";
import { ChatViewProvider } from "./chatViewProvider";

const API_BASE = "http://localhost:8000"; // ← BACKEND URL

export function activate(context: vscode.ExtensionContext) {
  const provider = new ChatViewProvider(context);

  // Register sidebar
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider("code-mate.chatView", provider)
  );

  // Register file save watcher → update backend index
  // ↓ BACKEND CONNECTION 3: POST /update_chunks
  const watcher = vscode.workspace.createFileSystemWatcher("**/*.py");
  const repoPath = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? "";

  const onFileChange = async () => {
    const paths = await vscode.workspace
      .findFiles("**/*.py", "{.venv,node_modules}/**")
      .then((files) => files.map((f) => f.fsPath));

    await fetch(`${API_BASE}/update_chunks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_path: repoPath, paths }),
    }).catch(() => {});
  };

  watcher.onDidChange(onFileChange);
  watcher.onDidCreate(onFileChange);
  watcher.onDidDelete(onFileChange);
  context.subscriptions.push(watcher);

  // Inline edit command — select code → give instruction → see diff
  // ↓ BACKEND CONNECTION 4: POST /edit  (ye endpoint abhi backend mein nahi hai)
  context.subscriptions.push(
    vscode.commands.registerCommand("code-mate.editSelection", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) return;

      const selection = editor.selection;
      const selectedCode = editor.document.getText(selection);
      if (!selectedCode) {
        vscode.window.showWarningMessage("Select some code first");
        return;
      }

      const instruction = await vscode.window.showInputBox({
        prompt: "What do you want to do?",
        placeHolder: "e.g. add error handling, make it async",
      });
      if (!instruction) return;

      vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: "Code Mate: Generating edit..." },
        async () => {
          try {
            const res = await fetch(`${API_BASE}/edit`, { // ← BACKEND: /edit endpoint banana hai
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                repo_path: repoPath,
                code: selectedCode,
                instruction,
                file: editor.document.uri.fsPath,
              }),
            });
            const data = (await res.json()) as { new_code: string };
            await showDiff(editor, selection, selectedCode, data.new_code);
          } catch {
            vscode.window.showErrorMessage("Code Mate: Edit failed");
          }
        }
      );
    })
  );
}

async function showDiff(
  editor: vscode.TextEditor,
  selection: vscode.Selection,
  original: string,
  newCode: string
) {
  // Write original and new to temp files, open VS Code diff view
  const originalUri = vscode.Uri.parse("code-mate-diff:original");
  const modifiedUri = vscode.Uri.parse("code-mate-diff:modified");

  const provider = new (class implements vscode.TextDocumentContentProvider {
    contents: Record<string, string> = {
      original,
      modified: newCode,
    };
    provideTextDocumentContent(uri: vscode.Uri) {
      return this.contents[uri.path];
    }
  })();

  const d1 = vscode.workspace.registerTextDocumentContentProvider("code-mate-diff", provider);

  await vscode.commands.executeCommand(
    "vscode.diff",
    originalUri,
    modifiedUri,
    "Code Mate: Review Changes"
  );

  // Ask user to accept or reject
  const choice = await vscode.window.showInformationMessage(
    "Apply this edit?",
    "Accept",
    "Reject"
  );

  d1.dispose();

  if (choice === "Accept") {
    await editor.edit((editBuilder) => {
      editBuilder.replace(selection, newCode);
    });
  }
}

export function deactivate() {}
