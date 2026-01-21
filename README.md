# nanocode

Minimal Gemini Code alternative. Single Python file, zero dependencies, ~250 lines.

Built using Claude Code, then used to build itself.

![screenshot](screenshot.png)

## Features

- Full agentic loop with tool use (Gemini function calling)
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`
- Conversation history
- Colored terminal output

## Usage

```bash
export GEMINI_API_KEY="your-key"
python nanocode.py
```

Or create a `.env` with `GEMINI_API_KEY=...` in the current directory or the
`nanocode.py` directory (environment variables still take precedence).

To use a different Gemini model:

```bash
export GEMINI_API_KEY="your-key"
export MODEL="gemini-3-flash-preview"
python nanocode.py
```

## Commands

- `/c` - Clear conversation
- `/q` or `exit` - Quit

## Tools

| Tool | Description |
|------|-------------|
| `read` | Read file with line numbers, offset/limit |
| `write` | Write content to file |
| `edit` | Replace string in file (must be unique) |
| `glob` | Find files by pattern, sorted by mtime |
| `grep` | Search files for regex |
| `bash` | Run shell command |

## Example

```
────────────────────────────────────────
❯ what files are here?
────────────────────────────────────────

⏺ Glob(**/*.py)
  ⎿  nanocode.py

⏺ There's one Python file: nanocode.py
```

## License

MIT
