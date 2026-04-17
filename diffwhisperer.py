#!/usr/bin/env python3
"""
diffwhisperer - Claude Code change explainer tool
Runs as a PostToolUse hook to explain file changes using Ollama
"""

import sys
import os
import json
import difflib
from datetime import datetime
from urllib import request
from urllib.error import URLError

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:e4b"
OLLAMA_TIMEOUT = 60

SYSTEM_PROMPTS = {
    "eli5": "You explain code changes to a 5 year old child. Use the simple words. Avoid technical terms.",
    "standard": "You explain code changes clearly to a non-technical person. Describe what changed and why it matters. You can include code snippets if they are fully explained.",
    "dev": "You are a senior engineer summarizing a code diff for a colleague. Be concise. Cover: what changed, the likely intent, and any potential side effects or risks worth noting",
}

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".diffwhisperer", "config.json")


def get_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"mode": "eli5"}


def get_explanation_mode():
    return get_config().get("mode", "eli5")


def is_binary_content(content):
    return "\x00" in content


def compute_unified_diff(old_content, new_content, filename, lineterm=""):
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=filename, tofile=filename, lineterm=lineterm
    )
    return "".join(diff)


def normalize_tool_input(tool_name, tool_input):
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        new_content = tool_input.get("content", "")
        old_content = ""
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        old_content = tool_input.get("old_string", "")
        new_content = tool_input.get("new_string", "")
    elif tool_name == "MultiEdit":
        file_path = tool_input.get("file_path", "")
        edits = tool_input.get("edits", [])
        old_parts = []
        new_parts = []
        for edit in edits:
            old_parts.append(edit.get("old_string", ""))
            new_parts.append(edit.get("new_string", ""))
        old_content = "".join(old_parts)
        new_content = "".join(new_parts)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
    return file_path, old_content, new_content


def call_ollama(prompt, model, mode):
    system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["standard"])
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=OLLAMA_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "").strip()
    except URLError as e:
        print(f"diffwhisperer: Ollama unreachable ({e})", file=sys.stderr)
        return None
    except Exception as e:
        print(f"diffwhisperer: Error calling Ollama ({e})", file=sys.stderr)
        return None


def get_session_log_path():
    import tempfile
    return os.path.join(tempfile.gettempdir(), "diffwhisperer_current.md")


def append_to_session_log(filename, explanation, diff, mode):
    log_path = get_session_log_path()
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"## {filename} — {timestamp} [{mode}]\n{explanation}\n\n<details><summary>Diff</summary>\n\n```diff\n{diff}\n```\n\n</details>\n\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"diffwhisperer: Could not write session log ({e})", file=sys.stderr)


def print_session_log():
    log_path = get_session_log_path()
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("No session log found.", file=sys.stderr)


def has_colors():
    return sys.stderr.isatty()


def print_explanation(filename, mode, explanation):
    filename_color = "\033[36m" if has_colors() else ""
    separator_color = "\033[90m" if has_colors() else ""
    reset = "\033[0m" if has_colors() else ""

    print(
        f"{separator_color}─────────────────────────────────────────{reset}",
        file=sys.stderr,
    )
    print(
        f"{separator_color}💬 diffwhisperer · {mode} · {filename_color}{filename}{reset}{separator_color}",
        file=sys.stderr,
    )
    print(
        f"{separator_color}─────────────────────────────────────────{reset}",
        file=sys.stderr,
    )
    print(explanation, file=sys.stderr)
    print(
        f"{separator_color}─────────────────────────────────────────{reset}",
        file=sys.stderr,
    )


def install_hook():
    settings_path = os.path.join(os.getcwd(), ".claude", "settings.json")
    script_path = os.path.abspath(__file__)

    hook_config = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [{"type": "command", "command": f"python {script_path.replace(os.sep, '/')}"}],
                }
            ]
        }
    }

    existing = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            pass

    if "hooks" not in existing:
        existing["hooks"] = {}
    if "PostToolUse" not in existing["hooks"]:
        existing["hooks"]["PostToolUse"] = []

    for hook_group in existing["hooks"]["PostToolUse"]:
        if hook_group.get("matcher") == "Write|Edit|MultiEdit":
            hook_group["hooks"] = hook_config["hooks"]["PostToolUse"][0]["hooks"]
            break
    else:
        existing["hooks"]["PostToolUse"].append(hook_config["hooks"]["PostToolUse"][0])

    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    print(f"Hook installed: {script_path}")
    print(f"Settings written to: {settings_path}")


def main():
    override_model = None
    for i, arg in enumerate(sys.argv):
        if arg == "--model" and i + 1 < len(sys.argv):
            override_model = sys.argv[i + 1]
            sys.argv = sys.argv[:i] + sys.argv[i + 2 :]
            break

    model = override_model if override_model else OLLAMA_MODEL

    input_data = sys.stdin.read()
    if not input_data:
        return

    try:
        event = json.loads(input_data)
    except json.JSONDecodeError:
        return

    tool_name = event.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return

    tool_input = event.get("tool_input", {})
    if not tool_input:
        return

    try:
        file_path, old_content, new_content = normalize_tool_input(
            tool_name, tool_input
        )
    except Exception:
        return

    if old_content == new_content:
        return

    if is_binary_content(old_content) or is_binary_content(new_content):
        return

    filename = os.path.basename(file_path)
    diff = compute_unified_diff(old_content, new_content, filename)

    if not diff:
        return

    prompt = f"File: {filename}\nChanges:\n{diff}\n\nExplain these changes."

    explanation = call_ollama(prompt, model, get_explanation_mode())

    if explanation:
        print_explanation(filename, get_explanation_mode(), explanation)
        append_to_session_log(filename, explanation, diff, get_explanation_mode())
    else:
        print("diffwhisperer: Could not generate explanation", file=sys.stderr)


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_hook()
    elif "--log" in sys.argv:
        print_session_log()
    else:
        main()
