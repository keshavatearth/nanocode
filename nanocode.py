#!/usr/bin/env python3
"""nanocode - minimal gemini code alternative"""

import glob as globlib, json, os, re, subprocess, urllib.request


def load_dotenv(paths):
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if stripped.startswith("export "):
                        stripped = stripped[len("export ") :].lstrip()
                    if "=" not in stripped:
                        continue
                    key, value = stripped.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if not key:
                        continue
                    if (
                        (value.startswith("'") and value.endswith("'"))
                        or (value.startswith('"') and value.endswith('"'))
                    ):
                        value = value[1:-1]
                    elif "#" in value:
                        value = value.split("#", 1)[0].rstrip()
                    os.environ.setdefault(key, value)
        except OSError:
            continue


load_dotenv(
    [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
)

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = os.environ.get("MODEL", "gemini-3-flash-preview")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ANSI colors
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)


# --- Tool implementations ---


def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


def edit(args):
    text = open(args["path"]).read()
    old, new = args["old"], args["new"]
    if old not in text:
        return "error: old_string not found"
    count = text.count(old)
    if not args.get("all") and count > 1:
        return f"error: old_string appears {count} times, must be unique (use all=true)"
    replacement = (
        text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
    )
    with open(args["path"], "w") as f:
        f.write(replacement)
    return "ok"


def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


def grep(args):
    pattern = re.compile(args["pat"])
    hits = []
    for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
        try:
            for line_num, line in enumerate(open(filepath), 1):
                if pattern.search(line):
                    hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
        except Exception:
            pass
    return "\n".join(hits[:50]) or "none"


def bash(args):
    proc = subprocess.Popen(
        args["cmd"], shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True
    )
    output_lines = []
    try:
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                output_lines.append(line)
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        output_lines.append("\n(timed out after 30s)")
    return "".join(output_lines).strip() or "(empty)"


# --- Tool definitions: (description, schema, function) ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def make_schema():
    result = []
    for name, (description, params, _fn) in TOOLS.items():
        properties = {}
        required = []
        for param_name, param_type in params.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)
        schema = {
            "type": "object",
            "properties": properties,
        }
        if required:
            schema["required"] = required
        result.append(
            {
                "type": "function",
                "name": name,
                "description": description,
                "parameters": schema,
            }
        )
    return result


def call_api(input_data, system_prompt, previous_interaction_id=None):
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")
    payload = {
        "model": MODEL,
        "input": input_data,
        "tools": make_schema(),
        "system_instruction": system_prompt,
        "generation_config": {"max_output_tokens": 8192},
    }
    if previous_interaction_id:
        payload["previous_interaction_id"] = previous_interaction_id
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY,
        },
    )
    response = urllib.request.urlopen(request)
    return json.loads(response.read())


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def normalize_tool_args(tool_args):
    if isinstance(tool_args, dict):
        return tool_args, None
    if isinstance(tool_args, str):
        try:
            return json.loads(tool_args), None
        except json.JSONDecodeError:
            return None, f"error: tool arguments not valid JSON: {tool_args}"
    if tool_args is None:
        return {}, None
    return None, f"error: tool arguments must be object, got {type(tool_args).__name__}"


def preview_tool_args(tool_args):
    if isinstance(tool_args, dict) and tool_args:
        return str(next(iter(tool_args.values())))[:50]
    if tool_args:
        return str(tool_args)[:50]
    return ""


def handle_outputs(outputs):
    tool_calls = []
    for output in outputs:
        output_type = output.get("type")
        if output_type == "text":
            print(f"\n{CYAN}⏺{RESET} {render_markdown(output.get('text', ''))}")
        elif output_type == "function_call":
            tool_calls.append(output)
    return tool_calls


def main():
    print(f"{BOLD}nanocode{RESET} | {DIM}{MODEL} (Gemini) | {os.getcwd()}{RESET}\n")
    previous_interaction_id = None
    system_prompt = f"Concise coding assistant. cwd: {os.getcwd()}"

    while True:
        try:
            print(separator())
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()
            print(separator())
            if not user_input:
                continue
            if user_input in ("/q", "exit"):
                break
            if user_input == "/c":
                previous_interaction_id = None
                print(f"{GREEN}⏺ Cleared conversation{RESET}")
                continue

            # agentic loop: keep calling API until no more tool calls
            interaction = call_api(
                user_input,
                system_prompt,
                previous_interaction_id=previous_interaction_id,
            )
            previous_interaction_id = interaction.get("id", previous_interaction_id)
            while True:
                tool_calls = handle_outputs(interaction.get("outputs", []))
                if not tool_calls:
                    break

                tool_results = []
                for call in tool_calls:
                    tool_name = call.get("name", "")
                    raw_args = call.get("arguments", {})
                    arg_preview = preview_tool_args(raw_args)
                    print(
                        f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                    )

                    tool_args, arg_error = normalize_tool_args(raw_args)
                    if arg_error:
                        result = arg_error
                    else:
                        result = run_tool(tool_name, tool_args)
                    result_lines = result.split("\n")
                    preview = result_lines[0][:60]
                    if len(result_lines) > 1:
                        preview += f" ... +{len(result_lines) - 1} lines"
                    elif len(result_lines[0]) > 60:
                        preview += "..."
                    print(f"  {DIM}⎿  {preview}{RESET}")

                    tool_results.append(
                        {
                            "type": "function_result",
                            "name": tool_name,
                            "call_id": call.get("id", ""),
                            "result": result,
                        }
                    )

                interaction = call_api(
                    tool_results,
                    system_prompt,
                    previous_interaction_id=previous_interaction_id,
                )
                previous_interaction_id = interaction.get("id", previous_interaction_id)

            print()

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
