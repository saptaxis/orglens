# orglens

Give AI agents a lens into your org-mode life.

orglens is a lightweight bridge between your running Emacs and CLI-based AI agents (Claude Code, Codex, etc.). It lets agents query your agenda, search your notes, capture tasks, and understand your workload — all by calling into your live Emacs session via `emacsclient`.

You keep your org-mode setup exactly as it is. orglens just makes it visible to agents.

## Why

If you use org-mode seriously — GTD, agenda views, capture templates, multi-file setups — and you also use AI coding agents in the terminal, you have two disconnected worlds. The agent can't see your agenda. It doesn't know what you're working on, what's overdue, or what's in your inbox. You can write CLAUDE.md instructions, but that's static text, not your live state.

orglens connects these worlds. Your agent can ask "what's in-progress?" and get a real answer from your real agenda.

## Architecture

```
┌─────────────┐      emacsclient --eval       ┌─────────────────┐
│  AI Agent    │  ──────────────────────────►   │  Running Emacs   │
│  (terminal)  │  ◄──────────────────────────   │  (org-mode)      │
└─────────────┘      stdout (text)             └─────────────────┘
       │
       │ uses
       ▼
┌─────────────┐
│   Skills     │  (Claude Code skills, or any
│   / Prompts  │   agent harness that can run
└─────────────┘   shell commands)
```

Two components:

1. **Elisp library** (`orglens.el`) — Functions that return org data as clean text, designed to be called via `emacsclient --eval`. These are thin wrappers around org-mode's own APIs.

2. **Skills pack** — Claude Code skills (and potentially other agent harnesses) that call the elisp functions and know how to use the results in context.

No MCP server. No protocol. No daemon. Emacs is the backend. `emacsclient` is the transport. Skills are the interface.

## What exists already (and how orglens differs)

### [org-mcp](https://github.com/laurynas-biveinis/org-mcp) (elisp, by laurynas-biveinis)

MCP server written in elisp that runs *inside* Emacs. Exposes raw file/headline operations (read outlines, update TODO states, add items). Structured around MCP protocol with resources and tools.

**Difference:** orglens doesn't use MCP. It calls `emacsclient` from outside. It exposes computed views (your actual agenda with groupings and filters), not just raw file operations.

### [org-mcp-server](https://github.com/szaffarano/org-mcp-server) (Rust, by szaffarano)

Standalone MCP server in Rust that parses org files directly using `orgize`. No running Emacs needed. Has agenda querying with filtering, fuzzy search, CLI tool.

**Difference:** Parsing org files outside Emacs means losing everything Emacs computes — custom agenda views, org-super-agenda groupings, skip functions, capture templates, dynamic blocks. orglens uses the real thing via emacsclient.

### [claude-code-ide.el](https://github.com/manzaltu/claude-code-ide.el) (by manzaltu)

Runs Claude Code CLI inside Emacs (vterm/eat). Bidirectional MCP bridge exposing Emacs features (LSP, tree-sitter, imenu, diagnostics) to Claude. Supports custom elisp as MCP tools.

**Difference:** claude-code-ide.el solves generic Emacs ↔ Claude integration. orglens is specifically about org-mode. They're complementary — orglens works whether you run Claude inside Emacs or in a separate terminal.

### [dev-agent-backlog](https://github.com/farra/dev-agent-backlog) (by farra)

Full project management methodology using org-mode templates. Design-doc-driven workflow with checkout/reconcile pattern. Claude Code slash commands for backlog management. Imposes its own org structure.

**Difference:** dev-agent-backlog is an opinionated project management system that uses org-mode as its format. orglens reads your *existing* org setup — whatever it looks like. dev-agent-backlog answers "what's the next task in this project?" orglens answers "what's on my plate today?"

### Summary

| Project | Approach | Requires Emacs? | Your org setup? |
|---------|----------|-----------------|-----------------|
| [org-mcp](https://github.com/laurynas-biveinis/org-mcp) | MCP inside Emacs | Yes (hosts MCP) | Raw file access |
| [org-mcp-server](https://github.com/szaffarano/org-mcp-server) | Standalone Rust parser | No | Re-parses files |
| [claude-code-ide.el](https://github.com/manzaltu/claude-code-ide.el) | Claude runs in Emacs | Yes (hosts Claude) | Not org-specific |
| [dev-agent-backlog](https://github.com/farra/dev-agent-backlog) | Methodology + templates | No | Imposes its own |
| **orglens** | **emacsclient + skills** | **Yes (running)** | **Reads yours as-is** |

## Planned features

### Elisp (orglens.el)

Atomic functions callable via `emacsclient --eval`:

- **Agenda** — Render any agenda view as text (`orglens-agenda "p"`)
- **TODO by state** — List items by state across files (`orglens-todos "IN-PROGRESS"`)
- **Search** — Full-text search across org files (`orglens-search "deployment"`)
- **Heading at point** — Read a specific heading by ID or path
- **Capture** — Add to inbox using capture templates (`orglens-capture "task text" "t"`)
- **TODO state transition** — Change state of a heading (`orglens-set-todo ID "DONE"`)
- **Tags/properties** — Query headings by tag or property
- **Clock** — What's currently clocked in, clock in/out

Each function returns plain text optimized for LLM consumption — not raw elisp objects, not JSON, just readable text.

### Skills

Claude Code skills that compose the elisp primitives into useful workflows:

- **"What's on my plate?"** — Pull agenda, in-progress items, inbox count. Provide as context.
- **"Capture this"** — Agent captures a task/note to your inbox mid-conversation.
- **"What did I work on?"** — Recent DONE items, clock report.
- **"Find my notes on X"** — Search across org files, return relevant headings.

Skills are the opinionated layer — they decide *when* and *how* to call the elisp functions. The elisp functions are generic; the skills encode workflow knowledge.

## Status

Early design phase. Contributions and ideas welcome.

## License

MIT
