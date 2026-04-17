#!/usr/bin/env python3
"""
diffwhisperer viewer - Web frontend for viewing diff explanations
"""

import http.server
import socketserver
import tempfile
import os
import re
import webbrowser
import argparse
import json
from urllib import request, error

PORT = 8080
LOG_PATH = os.path.join(tempfile.gettempdir(), "diffwhisperer_current.md")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".diffwhisperer", "config.json")

SYSTEM_PROMPTS = {
    "eli5": "You explain code changes to a 5 year old child. Use the simple words. Avoid technical terms.",
    "standard": "You explain code changes clearly to a non-technical person. Describe what changed and why it matters.",
    "dev": "You are a senior engineer summarizing a code diff for a colleague. Be concise. Cover: what changed and risks.",
}


def get_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"mode": "eli5"}


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def parse_log_entries():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    entries = []
    parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^## (.+?) . (.+?) \[(.+?)\]$", part, flags=re.MULTILINE)
        if not m:
            continue
        filename = m.group(1).strip()
        timestamp = m.group(2).strip()
        mode = m.group(3).strip()
        body = part[len(m.group(0)) :].strip()
        det = re.search(r"<details>.*?</details>", body, re.DOTALL)
        explanation = body[: det.start()].strip() if det else body
        diff = ""
        if det:
            dm = re.search(r"```diff\n(.*?)\n```", det.group(0), re.DOTALL)
            if dm:
                diff = dm.group(1).strip()
        entries.append({"filename": filename, "timestamp": timestamp, "mode": mode, "explanation": explanation, "diff": diff})
    return list(reversed(entries))


def regenerate_explanation(filename, diff, mode):
    prompt = f"File: {filename}\nChanges:\n{diff}\n\nExplain these changes."
    payload = {
        "model": "gemma4:e4b",
        "prompt": prompt,
        "system": SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["standard"]),
        "stream": False,
        "options": {"temperature": 0.3},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("response", "").strip()
    except Exception as e:
        return f"Error: {e}"


def update_log_entry(filename, new_explanation, mode):
    if not os.path.exists(LOG_PATH):
        return False
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    updated_parts = []
    found = False
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r"^## (.+?) . (.+?) \[(.+?)\]$", part, flags=re.MULTILINE)
        if m and m.group(1).strip() == filename:
            found = True
            timestamp = m.group(2).strip()
            body = part[len(m.group(0)) :].strip()
            det = re.search(r"<details>.*?</details>", body, re.DOTALL)
            diff = ""
            if det:
                dm = re.search(r"```diff\n(.*?)\n```", det.group(0), re.DOTALL)
                if dm:
                    diff = dm.group(1).strip()
            new_entry = f"## {filename} — {timestamp} [{mode}]\n{new_explanation}\n\n<details><summary>Diff</summary>\n\n```diff\n{diff}\n```\n\n</details>\n\n"
            updated_parts.append(new_entry)
        else:
            updated_parts.append(part)
    if found:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("".join(updated_parts))
        return True
    return False


def delete_log_entry(filename):
    if not os.path.exists(LOG_PATH):
        return False
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    updated_parts = []
    found = False
    for part in parts:
        if not part.strip():
            continue
        m = re.match(r"^## (.+?) . (.+?) \[(.+?)\]$", part, flags=re.MULTILINE)
        if m and m.group(1).strip() == filename:
            found = True
            continue
        updated_parts.append(part)
    if found:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("".join(updated_parts))
        return True
    return False


HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>diffwhisperer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#1e1e2e;color:#cdd6f4;padding:2rem}
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid #3a3a4e;flex-wrap:wrap;gap:1rem}
h1{color:#89dceb}
.mode-selector{display:flex;gap:0.5rem}
.mode-btn{padding:0.5rem 1rem;border:none;border-radius:6px;cursor:pointer;font-size:0.9rem;background:#3a3a4e;color:#cdd6f4;transition:all 0.2s}
.mode-btn:hover{background:#4a4a5e}
.mode-btn.active{background:#89dceb;color:#1e1e2e;font-weight:bold}
.status{margin-bottom:1rem;color:#6c7086;font-size:0.9rem}
.entries{display:flex;flex-direction:column;gap:1rem;max-width:900px}
.card{background:#2a2a3c;border-radius:8px;border:1px solid #3a3a4e;overflow:hidden}
.card-header{display:flex;align-items:center;justify-content:space-between;padding:1rem;background:#252536;border-bottom:1px solid #3a3a4e;flex-wrap:wrap;gap:0.5rem}
.filename{color:#89dceb;font-weight:bold}
.timestamp{color:#6c7086;font-size:0.85rem}
.mode-badge{background:#89dceb;color:#1e1e2e;padding:0.15rem 0.5rem;border-radius:4px;font-size:0.75rem;font-weight:bold}
.card-actions{display:flex;gap:0.25rem}
.btn{padding:0.3rem 0.6rem;border:none;border-radius:4px;cursor:pointer;font-size:0.8rem;background:#3a3a4e;color:#cdd6f4;transition:all 0.15s}
.btn:hover{background:#4a4a5e}
.btn.delete{background:#f38ba8;color:#1e1e2e}
.btn.delete:hover{background:#ff6b8a}
.btn.regen{background:#89b4fa;color:#1e1e2e}
.btn.regen:hover{background:#a0c4ff}
.card-body{padding:1rem}
.explanation{white-space:pre-wrap;line-height:1.6}
.diff-block{background:#1e1e2e;padding:1rem;border-radius:6px;margin-top:0.75rem;overflow-x:auto;font-family:'SF Mono',Consolas,monospace;font-size:0.85rem;white-space:pre}
.add{color:#a6e3a1}
.del{color:#f38ba8}
.diff-header{color:#6c7086}
details{margin-top:0.75rem}
summary{cursor:pointer;color:#6c7086;font-size:0.9rem}
summary:hover{color:#cdd6f4}
.empty{text-align:center;padding:3rem;color:#6c7086}
.loading{opacity:0.5;pointer-events:none}
</style>
</head>
<body>
<div class="header">
  <h1>diffwhisperer</h1>
  <div class="mode-selector">
    <button class="mode-btn" data-filter="all">All</button>
    <button class="mode-btn" data-filter="eli5">ELI5</button>
    <button class="mode-btn" data-filter="standard">Standard</button>
    <button class="mode-btn" data-filter="dev">Dev</button>
  </div>
</div>
<div class="status" id="status">Loading...</div>
<div class="entries" id="entries"></div>
<script>
var currentFilter = 'all';
var entries = [];

function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDiff(diffText) {
    if (!diffText) return '';
    var lines = diffText.split('\\n');
    var html = '';
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        var escaped = escapeHtml(line);
        if (line.indexOf('+++') === 0 || line.indexOf('---') === 0 || line.indexOf('@@') === 0) {
            html += '<div class="diff-header">' + escaped + '</div>';
        } else if (line.indexOf('+') === 0) {
            html += '<div class="add">' + escaped + '</div>';
        } else if (line.indexOf('-') === 0) {
            html += '<div class="del">' + escaped + '</div>';
        } else {
            html += '<div>' + escaped + '</div>';
        }
    }
    return html;
}

function render() {
    var container = document.getElementById('entries');
    var status = document.getElementById('status');
    container.innerHTML = '';

    var filtered = entries;
    if (currentFilter !== 'all') {
        filtered = [];
        for (var i = 0; i < entries.length; i++) {
            if (entries[i].mode === currentFilter) {
                filtered.push(entries[i]);
            }
        }
    }

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty">No explanations yet.</div>';
        status.textContent = currentFilter === 'all' ? '0 explanations' : '0 in ' + currentFilter;
        return;
    }

    status.textContent = filtered.length + ' in ' + currentFilter;

    for (var i = 0; i < filtered.length; i++) {
        var entry = filtered[i];
        var idx = entries.indexOf(entry);
        var card = document.createElement('div');
        card.className = 'card';
        card.id = 'card-' + idx;

        var header = document.createElement('div');
        header.className = 'card-header';

        var left = document.createElement('div');
        left.style.display = 'flex';
        left.style.alignItems = 'center';
        left.style.gap = '0.75rem';

        var fn = document.createElement('span');
        fn.className = 'filename';
        fn.textContent = entry.filename;

        var ts = document.createElement('span');
        ts.className = 'timestamp';
        ts.textContent = entry.timestamp;

        var badge = document.createElement('span');
        badge.className = 'mode-badge';
        badge.textContent = entry.mode || '';

        left.appendChild(fn);
        left.appendChild(ts);
        left.appendChild(badge);

        var actions = document.createElement('div');
        actions.className = 'card-actions';

        var modes = ['eli5', 'standard', 'dev'];
        for (var j = 0; j < modes.length; j++) {
            var btn = document.createElement('button');
            btn.className = 'btn regen';
            btn.textContent = modes[j] === 'standard' ? 'Std' : modes[j].charAt(0).toUpperCase() + modes[j].slice(1);
            btn.onclick = (function(index, mode) {
                return function() { regenEntry(index, mode); };
            })(idx, modes[j]);
            actions.appendChild(btn);
        }

        var delBtn = document.createElement('button');
        delBtn.className = 'btn delete';
        delBtn.textContent = 'X';
        delBtn.onclick = (function(index) {
            return function() { deleteEntry(index); };
        })(idx);
        actions.appendChild(delBtn);

        header.appendChild(left);
        header.appendChild(actions);

        var body = document.createElement('div');
        body.className = 'card-body';

        var exp = document.createElement('div');
        exp.className = 'explanation';
        exp.textContent = entry.explanation || '';
        body.appendChild(exp);

        if (entry.diff) {
            var details = document.createElement('details');
            var summary = document.createElement('summary');
            summary.textContent = 'View Diff';
            var diffDiv = document.createElement('div');
            diffDiv.className = 'diff-block';
            diffDiv.innerHTML = formatDiff(entry.diff);
            details.appendChild(summary);
            details.appendChild(diffDiv);
            body.appendChild(details);
        }

        card.appendChild(header);
        card.appendChild(body);
        container.appendChild(card);
    }
}

function regenEntry(idx, mode) {
    var entry = entries[idx];
    if (!entry) return;
    var card = document.getElementById('card-' + idx);
    card.classList.add('loading');

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/regen', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            card.classList.remove('loading');
            if (xhr.status === 200) {
                var data = JSON.parse(xhr.responseText);
                if (data.explanation && !data.explanation.startsWith('Error:')) {
                    entry.explanation = data.explanation;
                    entry.mode = mode;
                    currentFilter = mode;
                    render();
                } else {
                    alert('Error: ' + (data.error || data.explanation));
                }
            }
        }
    };
    xhr.send(JSON.stringify({filename: entry.filename, diff: entry.diff, mode: mode}));
}

function deleteEntry(idx) {
    var entry = entries[idx];
    if (!entry) return;
    if (!confirm('Delete explanation for ' + entry.filename + '?')) return;

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/delete', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && xhr.status === 200) {
            entries.splice(idx, 1);
            render();
        }
    };
    xhr.send(JSON.stringify({filename: entry.filename}));
}

function loadEntries() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/api/entries', true);
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && xhr.status === 200) {
            entries = JSON.parse(xhr.responseText);
            render();
        }
    };
    xhr.send();
}

function setFilter(filter) {
    currentFilter = filter;
    var buttons = document.querySelectorAll('.mode-btn');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.remove('active');
        if (buttons[i].getAttribute('data-filter') === filter) {
            buttons[i].classList.add('active');
        }
    }
    render();
}

function init() {
    var buttons = document.querySelectorAll('.mode-btn');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].onclick = (function(filter) {
            return function() { setFilter(filter); };
        })(buttons[i].getAttribute('data-filter'));
    }
    loadEntries();
    setInterval(loadEntries, 5000);
}

init();
</script>
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/entries":
            entries = parse_log_entries()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(entries).encode())
        elif self.path == "/api/config":
            config = get_config()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(config).encode())
        elif self.path == "/" or self.path == "/index.html":
            content = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            config = get_config()
            if "mode" in data and data["mode"] in SYSTEM_PROMPTS:
                config["mode"] = data["mode"]
                save_config(config)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(config).encode())
        elif self.path == "/api/regen":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            filename = data.get("filename", "")
            diff = data.get("diff", "")
            mode = data.get("mode", "standard")
            explanation = regenerate_explanation(filename, diff, mode)
            if not explanation.startswith("Error:"):
                update_log_entry(filename, explanation, mode)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"explanation": explanation}).encode())
        elif self.path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)
            filename = data.get("filename", "")
            success = delete_log_entry(filename)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
        else:
            self.send_error(404)

    def log_message(self, s, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    print("Starting on http://localhost:" + str(args.port))
    print("Log path: " + LOG_PATH)
    webbrowser.open("http://localhost:" + str(args.port))
    socketserver.TCPServer(("", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
