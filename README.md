# Code Mate

A VS Code extension that helps developers understand and modify Python codebases using a RAG-powered chat interface with agentic code editing capabilities.

---

## Features

- **Chat-based Q&A** — Ask questions about your Python codebase and get answers with file and line references
- **Hybrid semantic search** — BM25 + FAISS retrieval with Reciprocal Rank Fusion (RRF) for high-recall chunk retrieval
- **Multi-query expansion** — Automatically generates 3 similar queries to improve retrieval recall
- **Agentic code editing** — Ask the LLM to modify functions; it uses `edit_lines`, `append_code`, or `edit_code` tools
- **Human-in-the-loop** — Code edits pause for user approval before writing to disk
- **Accept / Decline UI** — Review the proposed code change in the sidebar, then accept or decline
- **Incremental indexing** — File watcher updates only changed files, not the whole repo
- **Multi-session support** — Up to 3 parallel chat sessions with independent histories

---

## Architecture

```
VS Code Sidebar (TypeScript Webview)
        │
        │  HTTP (localhost:8000)
        ▼
FastAPI Backend (Python)
        │
        ├── /initialize  → Tree-sitter AST parse → BM25 + FAISS index
        ├── /query       → LangGraph pipeline → LLM response / pending edit
        ├── /approve_edit → Resume graph with accept/decline decision
        ├── /messages    → Load previous chat history
        └── /update_chunks → Incremental re-index on file change
```

### LangGraph Pipeline

![LangGraph Flow](assets/graph.png)

```
START
  └─► fetch_chunks
        └─► generate_similar_queries   (3 expanded queries for better recall)
              └─► call_llm             (structured output: response + tool decision)
                    ├─► call_tools ──► [interrupt: wait for user approval]
                    │     ├─► summarize_code_changes ──► reset_state ──► END
                    │     └─► call_llm  (loop for read/run tools, max 5 calls)
                    └─► reset_state ──► END
```

**Nodes:**
| Node | Role |
|---|---|
| `fetch_chunks` | Retrieves relevant code chunks from hybrid BM25+FAISS index |
| `generate_similar_queries` | Expands query into 3 variants for broader retrieval |
| `call_llm` | Calls LLM with retrieved context; decides tool + produces response |
| `call_tools` | Executes the chosen tool; interrupts for edit operations |
| `summarize_code_changes` | Generates a brief "Done. Changed X in Y." summary after edits |
| `reset_state` | Cleans up per-turn state counters before graph exits |

---

## Tech Stack

| Layer | Technology |
|---|---|
| VS Code Extension | TypeScript, VS Code Webview API |
| Backend API | FastAPI + Uvicorn |
| AST Parsing | Tree-sitter (`tree-sitter-python`) |
| Keyword Search | BM25 (`rank-bm25`) |
| Vector Search | FAISS (`faiss-cpu`) + SentenceTransformers (`all-MiniLM-L6-v2`) |
| Retrieval Fusion | Reciprocal Rank Fusion (RRF) |
| LLM Orchestration | LangGraph (`StateGraph` + `InMemorySaver` checkpointer) |
| LLM | SambaNova (`gpt-5-nano-2025-08-07`) via OpenAI-compatible API |
| Tools | `edit_lines`, `append_code`, `edit_code`, `read_file`, `run_terminal` |

---

## Project Structure

```
code_mate/
├── backend/
│   ├── indexer.py       # Tree-sitter AST parser → structured chunks per file
│   ├── retriver.py      # Hybrid BM25 + FAISS retriever with RRF
│   ├── llm.py           # LangGraph graph definition and all node functions
│   ├── tools.py         # LangChain tools: edit_lines, append_code, edit_code, read_file, run_terminal
│   ├── routes.py        # FastAPI endpoints
│   └── constants.py     # Shared `sessions` dict (repo_path → indexer/retriever)
│
├── code-mate/           # VS Code extension
│   ├── src/
│   │   ├── extension.ts         # Registers provider + FileSystemWatcher
│   │   └── chatViewProvider.ts  # Webview UI: chat, sessions, accept/decline
│   └── package.json
│
├── assets/
│   └── graph.png        # LangGraph flow diagram
│
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A SambaNova API key — set `SAMBANOVA_API_KEY` in `backend/.env`

### Backend

```bash
cd backend
pip install -r ../requirements.txt

# Create .env
echo "SAMBANOVA_API_KEY=your_key_here" > .env

# Start server
uvicorn routes:app --reload --port 8000
```

### VS Code Extension

```bash
cd code-mate
npm install
npm run compile
```

Press `F5` in VS Code to launch the extension in a new Extension Development Host window.

> The extension auto-discovers the open workspace root as `repo_path`. Open any Python project folder in the Extension Development Host to index it.

---

## How It Works

### Query Flow

1. User types a question in the sidebar chat
2. Extension POSTs `/query` with `repo_path`, `thread_id`, and the question
3. `fetch_chunks` + `generate_similar_queries` retrieve the most relevant code chunks using BM25 + FAISS + RRF
4. `call_llm` builds a detailed prompt with retrieved chunks and returns a structured response
5. If no tool is needed → response is shown in chat
6. If an edit tool is needed → `call_tools` fires `interrupt()`, pausing the graph

### Edit Flow

1. LLM decides to use `edit_lines`, `append_code`, or `edit_code`
2. `call_tools` calls `interrupt({tool, tool_input})` — graph pauses
3. Backend returns `{"pending_edit": {...}}` to extension
4. Sidebar shows a code preview card with **Accept** and **Decline** buttons
5. User clicks Accept → POST `/approve_edit` with `decision: "approve"` → graph resumes, tool executes → `summarize_code_changes` returns a brief summary
6. User clicks Decline → POST `/approve_edit` with `decision: "decline"` → graph resumes cleanly without writing any file

### Incremental Indexing

The extension registers a `FileSystemWatcher` on `**/*.py`. On any file create/change/delete, it POSTs `/update_chunks` with the affected paths. The indexer re-parses only those files, and the retriever updates BM25 corpus and FAISS index accordingly.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SAMBANOVA_API_KEY` | API key for SambaNova LLM endpoint |

---

## Known Limitations

- Only Python files are indexed (`.py` extension)
- Sessions are in-memory — restarting the backend clears all indexes and chat history
- `run_terminal` tool only allows `python`, `pytest`, and `git` commands
