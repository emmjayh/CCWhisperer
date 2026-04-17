# CCWhisperer  <img width="1024" height="1024" alt="Default_Here_is_a_design_concept_for_CCWhispererThis_icon_inco_0_49ce1859-55a1-4022-bb9b-b3ff1336a98d_0" src="https://github.com/user-attachments/assets/9c0a062f-403d-4296-bdf5-9df1059f98fc" />


AI-powered code change explanations for Claude Code sessions. Automatically generates human-readable explanations of file changes using local Ollama models.

<img width="1251" height="492" alt="image" src="https://github.com/user-attachments/assets/acb6325b-fe73-4b15-88c3-64aa873cb810" />

![CCWhisperer](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Automatic Explanations**: Intercepts file edits (Write, Edit, MultiEdit) and generates explanations
- **Multiple Tones**: Choose between ELI5, Standard, or Developer-focused explanations

- **Web Dashboard**: View explanations in a modern dark-themed web interface
- **Regenerate**: Re-generate explanations in different tones with one click
- **Filter by Mode**: View only explanations from a specific tone
- **Local & Private**: All processing happens locally with Ollama - no data leaves your machine

## Prerequisites

- **Python 3.8+**
- **Ollama** installed and running locally
- **Claude Code** CLI

### Ollama Setup

1. Install Ollama from [ollama.ai](https://ollama.ai)

2. Pull a model (gemma4 is recommended):
   ```bash
   ollama pull gemma4:e4b
   ```

   Other models that work well:
   - `qwen3:8b`
   - `llama3.2:latest`
   - `mistral:7b`

3. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

## Installation

### 1. Clone or copy the project

```bash
git clone https://github.com/CCWhisperer/CCWhisperer.git
cd CCWhisperer
```

Or just copy `CCWhisperer.py` and `viewer.py` to your desired location.

### 2. Install the Claude Code Hook

Run this command **in your project directory** where you want explanations:

```bash
python CCWhisperer.py --install
```

This creates a `.claude/settings.json` file with the hook configuration.

**Note**: The hook is per-project. Run `--install` in each Claude Code project where you want explanations.

## Usage

### Automatic Explanations

Once installed, simply use Claude Code normally. Every time you edit a file:

1. The hook captures the diff
2. Sends it to Ollama
3. Prints the explanation to stderr
4. Saves it to the session log

### Web Dashboard

Start the viewer to see explanations in a browser:

```bash
python viewer.py
```

This opens http://localhost:8080 in your browser.

**Features**:
- View all explanations with collapsible diffs
- Filter by explanation tone (ELI5 / Standard / Dev)
- Regenerate any explanation in a different tone
- Delete unwanted explanations
- Auto-refreshes every 5 seconds

### CLI Commands

Print explanations to terminal:

```bash
python CCWhisperer.py --log
```

## Configuration

### Changing the Model

Edit the `OLLAMA_MODEL` in `CCWhisperer.py`:

```python
OLLAMA_MODEL = "qwen3:8b"  # Change to your preferred model
```

Or override at runtime:

```bash
python CCWhisperer.py --model llama3.2:latest
```

### Changing Default Tone

The default tone is set in `~/.CCWhisperer/config.json`:

```json
{"mode": "eli5"}
```

Valid modes: `eli5`, `standard`, `dev`

### Ollama Host

To use a remote Ollama instance, edit `OLLAMA_HOST`:

```python
OLLAMA_HOST = "http://192.168.1.100:11434"
```

## Project Structure

```
CCWhisperer/
├── CCWhisperer.py   # Main hook script
├── viewer.py          # Web dashboard
├── .gitignore
└── README.md
```

## How It Works

1. **Hook Trigger**: Claude Code's PostToolUse hook fires after Write/Edit/MultiEdit
2. **Diff Generation**: Computes unified diff from old vs new content
3. **LLM Processing**: Sends diff + system prompt to Ollama
4. **Output**: Prints explanation + saves to session log
5. **View**: Web viewer displays log with filtering/regeneration

## Troubleshooting

### "Ollama unreachable"

- Ensure Ollama is running: `ollama serve`
- Check the model is available: `ollama list`
- Verify host/port if using remote Ollama

### Hook not firing

- Verify hook is installed: Check `.claude/settings.json`
- Run `--install` in the correct project directory
- Ensure you're using Claude Code (not Claude CLI)

### Viewer shows no entries

- Check the log file location: `~/.CCWhisperer/` or temp directory
- Verify hook is generating explanations (check Claude Code stderr)
- Try making a small edit and watching the viewer

## License

MIT License - feel free to use, modify, and distribute.

## Contributing

Contributions welcome! Open an issue or PR on GitHub.
