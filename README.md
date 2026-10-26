# Vizier — Royal Advisor

**A 100% local AI agent for computer use, filesystem management, shell access, and general assistance.**

**Repository:** [github.com/sonamcgoo-dev/vizier](https://github.com/sonamcgoo-dev/vizier)

Vizier runs a GGUF language model on your own machine and gives it hands: it can read and write
files, run commands, take screenshots, move the mouse, type on the keyboard, and call tools exposed
by Model Context Protocol (MCP) servers. There is no cloud inference, no API key, and no telemetry.

- **No cloud / no BYOK / no telemetry** — inference is local via `llama-cpp-python`
- **Safe by default** — dangerous tools are blocked unless YOLO mode is explicitly enabled
- **Hardware-aware** — recommends models based on your CPU, RAM, and GPU
- **Two front ends** — a Qt desktop app and a terminal REPL
- **MCP both ways** — Vizier can use MCP servers *and* expose its own tools as an MCP server
- **Midnight-palace theme** — midnight indigo, antique gold, crimson, and turquoise, with a Rakkas
  wordmark and intentionally restrained motion

> **Status:** v1.0.0 release candidate (“Royal Advisor”). Core agent, GUI, CLI, MCP client/server,
> diagnostics, packaging, and a 101-test suite are implemented. Windows builds are unsigned (no
> code-signing certificate), so SmartScreen may ask for confirmation on first launch. Voice, screen
> painting, and a plugin marketplace are intentionally out of scope for this release.

---

## Requirements

- **Python 3.10+** (tested on 3.13)
- **A GGUF model** (`.gguf`) such as Qwen 3, Llama 3.2, Gemma 2, Phi-3, or Mistral
- Optional: **Tesseract OCR** for `ocr_screen` / `screenshot` OCR
- Optional: a GPU with CUDA/Vulkan/Metal support for faster inference

On Windows, install Python from [python.org](https://www.python.org/downloads/) and make sure
`python` is on `PATH` (or use the full path to `python.exe`).

---

## Install on Windows

The packaged build does **not** require Python or any developer tools.

1. Download `Vizier-Setup-1.0.0-x64.exe` from the release page (or build it locally with
   [`scripts/build_windows.ps1`](scripts/build_windows.ps1)).
2. Run the installer. It installs per-user by default (no administrator prompt) into
   `%LOCALAPPDATA%\Programs\Vizier`, adds Start-menu and optional desktop shortcuts, and includes
   the GUI, CLI, and MCP server.
3. Launch **Vizier**, open **File → Model Manager…**, and download a model sized for your hardware.
   No account, API key, or internet connection is needed after that first download.

**Portable build:** extract `Vizier-1.0.0-portable-x64.zip` anywhere and run `Vizier.exe`. Settings,
models, and sessions still live in `%LOCALAPPDATA%\Vizier`.

**Uninstalling** keeps your models and sessions by default and asks before deleting the data
directory. The executables are unsigned, so Windows SmartScreen may show “Windows protected your PC”;
choose **More info → Run anyway** if you built or downloaded the release yourself.

Bundled executables:

| File | Purpose |
|---|---|
| `Vizier.exe` | Desktop GUI |
| `VizierCLI.exe` | Full command-line interface |
| `VizierMCP.exe` | MCP server over stdio or HTTP |

---

## Quick start from source

```bash
# 1. Clone and install from source (full dependency set)
git clone https://github.com/sonamcgoo-dev/vizier.git
cd vizier
python -m pip install -e ".[full]"

# 2. See what your hardware can run
python -m vizier models --recommend

# 3. Download a model (example: Qwen 3 8B, Q4_K_M)
python -m vizier models --download "Qwen/Qwen3-8B-GGUF qwen3-8b-q4_k_m.gguf"

# 4. Launch the desktop app
python -m vizier

# ...or chat in the terminal
python -m vizier chat --model "%LOCALAPPDATA%\Vizier\models\qwen3-8b-q4_k_m.gguf"
```

If you install the package normally (`pip install vizier`), the `vizier` and `vizier-mcp-server`
commands are available directly:

```bash
vizier
vizier chat --model path/to/model.gguf
vizier mcp-server --stdio
```

In the packaged build, use `VizierCLI.exe` in place of `vizier` and `VizierMCP.exe --stdio` for the
MCP server. The CLI executable lives next to `Vizier.exe` in the install directory.

### Install only what you need

```bash
python -m pip install -e .              # core (requests)
python -m pip install -e ".[gui]"       # + PySide6 desktop app
python -m pip install -e ".[llm]"       # + llama-cpp-python
python -m pip install -e ".[computer]"  # + screenshots, mouse, keyboard, OCR
python -m pip install -e ".[mcp]"       # + MCP client/server (mcp 2.x)
python -m pip install -e ".[dev]"       # + pytest, ruff
python -m pip install -e ".[full]"      # everything above
```

> **GPU builds:** `pip install llama-cpp-python` installs a CPU build by default. For CUDA or
> Vulkan, follow the
> [llama-cpp-python installation guide](https://github.com/abetlen/llama-cpp-python#installation-with-hardware-acceleration)
> and set `model_n_gpu_layers` in your config.

---

## Desktop GUI

Launch with `vizier` (or `python -m vizier`). The window has a sidebar with model/tool controls and
a chat pane with streamed responses and collapsible-looking tool activity blocks.

- **Load a model:** `File → Load Model…` (`Ctrl+L`) or **drag a `.gguf` file anywhere onto the window**
- **Model manager:** `Ctrl+M` — hardware recommendations, downloads, and local model list
- **Chat:** type in the input box and press `Enter`
- **New chat:** `Ctrl+N` — **Open session:** `Ctrl+O` — **Save session:** `Ctrl+S` — **Quit:** `Ctrl+Q`
- **Settings:** `Ctrl+,` — context size, GPU layers, sampling, system prompt, YOLO default
- **Clear chat:** `Ctrl+Shift+Delete`
- **YOLO mode:** toggle in the sidebar or `View → YOLO Mode`
- **Tool toggles:** uncheck a tool in the sidebar to hide it from the model
- **Data folder / logs:** `View → Open Data Folder`; logs are under `logs\vizier.log`
- **Help / About / self-check:** `F1` opens the docs; **Help → About Vizier** runs health checks and
  can copy diagnostics to the clipboard

Model loading and agent turns run on background threads, so the UI stays responsive while the model
is working. Sessions are saved automatically after each turn and can be renamed or reloaded from
disk. Downloads can be cancelled and clean up their partial files.

---

## CLI reference

```
usage: vizier [-h] [--version] [--model GLOBAL_MODEL] [--verbose] {gui,chat,mcp-server,models,info,doctor,version} ...
```

| Command | Description |
|---|---|
| `vizier` / `vizier gui` | Launch the desktop GUI |
| `vizier chat --model PATH [--yolo]` | Interactive terminal chat |
| `vizier mcp-server [--stdio\|--sse\|--streamable-http]` | Run Vizier as an MCP server |
| `vizier models --recommend` | Show models suited to your hardware |
| `vizier models --local` | List downloaded models |
| `vizier models --search QUERY` | Search Hugging Face for GGUF repos |
| `vizier models --download "REPO FILE"` | Download a GGUF file |
| `vizier info` | Print a hardware and configuration report |
| `vizier doctor` | Self-check Python, GUI, inference, tools, models, disk, and logging |
| `vizier version` | Print the version |
| `vizier --model PATH` | Launch the GUI with a model preloaded |

### Chat slash commands

| Command | Description |
|---|---|
| `/help` | Show command help |
| `/exit`, `/quit`, `/q` | Quit |
| `/clear` | Clear conversation history |
| `/yolo` | Toggle YOLO mode |
| `/tools` | List registered tools |
| `/history` | Show conversation length |
| `/model PATH` | Switch GGUF model (reloads) |
| `/config` | Print the current configuration |

---

## MCP integration

### Vizier as an MCP server

Vizier exposes 15 tools over stdio, SSE, or streamable HTTP:

```bash
vizier-mcp-server --stdio
vizier-mcp-server --sse --host 127.0.0.1 --port 9000
vizier-mcp-server --streamable-http --host 127.0.0.1 --port 9000
```

Example client configuration (Claude Desktop, Cursor, VS Code, etc.):

```json
{
  "mcpServers": {
    "vizier": {
      "command": "vizier-mcp-server",
      "args": ["--stdio"]
    }
  }
}
```

Exposed tools: `file_read`, `file_write`, `file_list`, `file_info`, `file_move`, `file_delete`,
`file_search`, `shell_run`, `screenshot`, `mouse_click`, `mouse_move`, `keyboard_type`,
`keyboard_hotkey`, `screen_size`, `list_windows`. Resources:
`config://models-directory`, `config://user-home`, `config://platform-info`.

> The MCP server does **not** apply the agent's YOLO gate: tools are exposed directly. Only register
> it with clients you trust, and prefer a restricted working directory.

### Vizier as an MCP client

Add servers to `mcp_servers` in your `config.json`; they are connected on startup when
`mcp_auto_start` is true. Each server's tools become `mcp_<server>_<tool>` entries in Vizier's
registry.

```json
{
  "mcp_auto_start": true,
  "mcp_servers": [
    {
      "name": "filesystem",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\you\\Documents"],
      "env": {},
      "enabled": true,
      "auto_start": true
    },
    {
      "name": "remote",
      "transport": "sse",
      "url": "http://127.0.0.1:9000/sse",
      "enabled": true,
      "auto_start": false
    }
  ]
}
```

`stdio` servers use `command`, `args`, and `env`. Non-stdio servers use `url`.

---

## Configuration

Vizier stores user data in a platform-specific directory:

| Platform | Directory |
|---|---|
| Windows | `%LOCALAPPDATA%\Vizier` |
| macOS | `~/Library/Application Support/Vizier` |
| Linux | `~/.local/share/vizier` |

- `config.json` — preferences (written atomically, with `config.json.bak` recovery)
- `models/` — downloaded GGUF files
- `sessions/` — saved conversations (JSON)
- `cache/` — screenshots and temporary files
- `logs/` — rotating `vizier.log`, plus `crash.log` for native crashes

Example `config.json`:

```json
{
  "model_path": "C:\\Users\\you\\AppData\\Local\\Vizier\\models\\qwen3-8b-q4_k_m.gguf",
  "model_n_ctx": 8192,
  "model_n_gpu_layers": 0,
  "model_temperature": 0.7,
  "model_top_p": 0.9,
  "model_repeat_penalty": 1.1,
  "yolo_enabled": false,
  "max_tool_rounds": 10,
  "system_prompt": "You are Vizier, a local AI agent...",
  "mcp_auto_start": true,
  "mcp_servers": []
}
```

| Key | Meaning |
|---|---|
| `model_path` | Path to the GGUF model |
| `model_n_ctx` | Context window size |
| `model_n_gpu_layers` | Layers to offload to the GPU (`0` = CPU only) |
| `model_temperature` / `model_top_p` / `model_repeat_penalty` | Sampling parameters |
| `yolo_enabled` | Allow dangerous tools without blocking |
| `max_tool_rounds` | Maximum tool-call rounds per user turn |
| `system_prompt` | System prompt prepended to every conversation |
| `mcp_servers` / `mcp_auto_start` | MCP client configuration |

---

## Safety and YOLO mode

Vizier is designed to be useful but not reckless:

- **YOLO mode is off by default.** When off, the agent may use read-only and UI tools, but
  `write_file`, `move_file`, `delete_file`, and `shell` are **blocked** and the model receives a
  `BLOCKED` tool result.
- **YOLO mode must be enabled explicitly** (checkbox, menu, `/yolo`, or `--yolo`). It permits
  destructive filesystem operations and arbitrary shell commands. Treat it like handing an agent a
  terminal.
- **Filesystem access is root-restricted by default.** `FilesystemManager` only permits paths under
  the user's home directory and the current working directory (`strict=True`). Paths outside those
  roots raise `PermissionError` rather than silently succeeding.
- **Shell commands time out** (default 60s at the manager level; per-call `timeout` is available).
- **Tool calls have a timeout** (default 60s) and failures are reported back to the model instead of
  crashing the loop.

> The MCP server bypasses the YOLO gate by design — it is a direct tool server for trusted clients.

---

## Hardware-aware model recommendations

`vizier models --recommend` detects your CPU/RAM/GPU and prints models at or below your tier.
Curated entries include:

| Tier | Models (examples) |
|---|---|
| CPU / integrated | Qwen 3 0.6B, Qwen 3 1.8B, Gemma 2B, Phi-3 Mini |
| 8 GB GPU | Qwen 3 8B, Llama 3.2 3B, Gemma 2 9B |
| 16 GB GPU | Qwen 3 14B, Llama 3.1 8B, Mistral Small 24B |
| 24 GB GPU | Qwen 3 30B-A3B, Qwen 3 32B, DeepSeek R1 32B |
| 64 GB+ GPU | Qwen 3 72B |

Recommendations are ordered from largest/most capable to smallest. The list is a starting point, not
a hard limit — any compatible GGUF can be loaded manually.

---

## Project structure

```
vizier/
├── __main__.py            # python -m vizier
├── cli.py                 # Argument parsing + GUI/chat/MCP/models/doctor commands
├── config.py              # Atomic, sanitised config (dataclass + JSON)
├── diagnostics.py         # Health checks for `vizier doctor` and the About box
├── logging_setup.py       # Rotating logs, crash log, exception hook
├── theme.py               # Midnight-palace Qt theme + bundled font loading
├── utils.py               # Data dirs, hardware detection, colors
├── core/
│   ├── agent.py           # Agent loop, tool execution, YOLO gate
│   ├── tool.py            # VizierTool base + FunctionTool schema inference
│   ├── types.py           # Messages, tool calls, results
│   ├── session.py         # Conversation persistence (atomic writes)
│   ├── mcp_client.py      # MCP client + tool adapters
│   ├── skill.py           # Skill discovery (experimental)
│   ├── llm/
│   │   ├── provider.py    # LLMProvider interface
│   │   ├── llama_cpp.py   # GGUF streaming provider
│   │   └── model_manager.py  # Recommend/search/download models (.part safe)
│   ├── fs/file_ops.py     # Root-restricted filesystem manager
│   ├── shell/__init__.py  # Shell execution with timeout
│   └── computer/          # Screen capture, mouse, keyboard, vision
├── tools/                 # Registry + built-in tool wrappers
├── ui/
│   ├── main_window.py     # Qt desktop app
│   └── dialogs.py         # Settings, model manager, sessions, About
└── servers/mcp_server.py  # Vizier as an MCP server

packaging/windows/         # PyInstaller spec, entry points, Inno Setup script
scripts/                   # Asset/version generation + build automation
tests/                     # pytest suite (101 tests)
```

---

## Development

```bash
# Install runtime + dev dependencies
python -m pip install -e ".[full,dev]"

# Syntax check every file
python -m compileall -q vizier tests packaging scripts

# Run the test suite (headless Qt)
$env:QT_QPA_PLATFORM = "offscreen"   # PowerShell
python -m pytest -q

# Lint
ruff check vizier tests packaging scripts
```

The tests cover config persistence and recovery, filesystem safety, shell execution, tool registry,
the agent loop (including YOLO blocking, timeouts, and callbacks), sessions, model
recommendations/downloads, MCP configuration/adapters, diagnostics, logging, the CLI, and headless
GUI/dialog tests.

Build a Windows release (tests → lint → PyInstaller → smoke tests → installer → checksums):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Requirements: Python 3.10+ with the `full`/`dev` extras, and
[Inno Setup 6](https://jrsoftware.org/isdl.php) for the installer. Add `-SkipInstaller` for a
portable bundle only. Artifacts land in `dist\`, including `SHA256SUMS-<version>.txt`.

Headless GUI check:

```bash
# PowerShell
$env:QT_QPA_PLATFORM = "offscreen"
python -c "from PySide6.QtWidgets import QApplication; app=QApplication([]); from vizier.ui.main_window import VizierWindow; w=VizierWindow(); print(w.windowTitle()); w.close()"
```

Build a wheel/sdist:

```bash
python -m pip install build
python -m build
```

---

## Troubleshooting

**Windows SmartScreen or antivirus warning**
Release binaries are unsigned. SmartScreen shows “Windows protected your PC” for new unsigned
executables; choose **More info → Run anyway** only if you downloaded the release from a source you
trust. Builds from this repository are reproducible with `scripts\build_windows.ps1`.

**Something went wrong / the app closes immediately**
Open `%LOCALAPPDATA%\Vizier\logs\vizier.log` (or **Help → About Vizier → Open log folder**) and run
`VizierCLI.exe doctor`. The self-check reports missing dependencies, model problems, disk space, and
logging issues.

**`llama-cpp-python` fails to install**
Install a prebuilt wheel or the required C++ toolchain; see the upstream README. On Windows,
`pip install llama-cpp-python --prefer-binary` often helps.

**GUI does not start**
Install PySide6 (`pip install -e ".[gui]"`). On a headless machine, set
`QT_QPA_PLATFORM=offscreen` for smoke tests.

**MCP server/client errors**
Vizier targets the **mcp 2.x** API (`Client`, `MCPServer`). Install `mcp>=2.0`; code written for
`mcp<2` (for example `FastMCP`) is not compatible.

**`FileNotFoundError` or `PermissionError`**
The filesystem manager only allows paths under your home directory and the current working
directory. Start Vizier from the directory you want to work in, or construct
`FilesystemManager(allowed_roots=[...])` in your own code.

**OCR does nothing**
Install Tesseract and make sure `tesseract` is on `PATH` (Windows: the UB Mannheim build). Set
`pytesseract.pytesseract.tesseract_cmd` if needed.

**Model output is slow**
Try a smaller quant (Q4_K_M), reduce `model_n_ctx`, and offload layers with
`model_n_gpu_layers` if you have a compatible GPU.

---

## Roadmap / out of scope

Completed: core agent, tool registry, GGUF streaming, YOLO gate, filesystem/shell/computer tools,
MCP client/server, hardware detection, model manager, sessions, CLI, desktop GUI, diagnostics,
logging, PyInstaller bundle, Windows installer, and tests.

Not in this release: voice input, screen painting/drawing, clipboard history, plugin/skill
marketplace, web dashboard, user authentication, and prebuilt macOS/Linux packages (both run from
source). See [`DEVELOPMENT_CHECKLIST.md`](DEVELOPMENT_CHECKLIST.md) for the full status.

---

## License

MIT — see [`LICENSE`](LICENSE).

Vizier is an independent project. “Vizier” refers to the historical royal advisor; the name is not
affiliated with any other software product.
