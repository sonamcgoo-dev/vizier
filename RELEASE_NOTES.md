# Vizier 1.0.0 — “Royal Advisor”

**Release date:** 2026-10-26  
**Platform:** Windows 10/11 x64  
**License:** MIT

Vizier is a 100% local AI agent for computer use, filesystem management, shell access, and general
assistance. It runs a GGUF model on your own machine and gives it hands: read and write files, run
commands, take screenshots, move the mouse, type on the keyboard, and call tools exposed by Model
Context Protocol (MCP) servers. No cloud inference, no API key, no telemetry.

## Downloads

| File | Size | Purpose |
|---|---|---|
| `Vizier-Setup-1.0.0-x64.exe` | 49.2 MB | Installer (per-user, no administrator prompt) |
| `Vizier-1.0.0-portable-x64.zip` | 97.7 MB | Portable build (extract and run) |
| `SHA256SUMS-1.0.0.txt` | — | SHA-256 checksums for both archives |

Verify a download in PowerShell:

```powershell
Get-FileHash .\Vizier-Setup-1.0.0-x64.exe -Algorithm SHA256
```

## Highlights

- **Local inference** — GGUF models via `llama-cpp-python`; streaming responses and tool calls.
- **Desktop app** — Qt interface with the midnight-palace theme: midnight indigo, antique gold,
  crimson, turquoise, and the bundled Rakkas display wordmark.
- **CLI** — `VizierCLI.exe` with chat, models, hardware info, and a `doctor` self-check.
- **MCP both ways** — use MCP servers as a client, or expose Vizier's 15 tools as an MCP server
  over stdio, SSE, or streamable HTTP.
- **Hardware-aware model recommendations** — picks models that fit your CPU, RAM, and GPU, and
  downloads them with progress, cancellation, and safe `.part` cleanup.
- **Safe by default** — dangerous tools are blocked unless YOLO mode is explicitly enabled, and
  filesystem access is restricted to the configured root.
- **Session persistence** — conversations are saved atomically and can be renamed, reloaded, or
  deleted from the session browser.
- **Diagnostics** — `vizier doctor`, rotating logs, a crash log, and an About dialog with health
  checks, log access, and clipboard export.
- **Lean and fast** — lazy loading of MCP, computer-use, and download dependencies cuts GUI
  startup from ~3.4 s to ~0.6 s; the release pipeline prunes unused Qt, Pillow, and llama.cpp files
  for a 49.2 MB installer and a 180.4 MB unpacked bundle.

## Installation

1. Run `Vizier-Setup-1.0.0-x64.exe`.
2. The installer is per-user by default and installs to `%LOCALAPPDATA%\Programs\Vizier`. You can
   choose an all-users install from the elevation prompt.
3. Start-menu shortcuts are created; a desktop shortcut is offered during setup.
4. Launch **Vizier**, open **File → Model Manager…** (`Ctrl+M`), and download a model sized for your
   hardware. No account or API key is required, and no network access is needed after the download.

Settings, sessions, and models live in `%LOCALAPPDATA%\Vizier`. The portable ZIP uses the same data
directory, so both builds share your configuration.

## Uninstallation

Uninstall from **Settings → Apps → Vizier** or the Start-menu uninstall shortcut. Your settings,
sessions, and downloaded models are **kept by default**; the uninstaller asks before deleting the
data directory. A silent uninstall keeps the data directory automatically.

## Requirements

- Windows 10 or newer, x64. No Python installation is required for the packaged build.
- A GGUF model file (downloadable in-app). The bundled build is CPU-first; GPU acceleration depends
  on the `llama-cpp-python` wheel available for your hardware.
- Tesseract OCR is optional and not bundled; it is only needed for OCR features.

## Known limitations

- **Unsigned binaries.** No code-signing certificate is available for this release. Windows
  SmartScreen may show “Windows protected your PC”; choose **More info → Run anyway** only if you
  obtained the build from a source you trust.
- The MCP server intentionally bypasses the agent's YOLO gate. Only connect MCP clients you trust.
- Voice input, screen painting, a plugin marketplace, a web dashboard, user authentication, and
  prebuilt macOS/Linux packages are out of scope for this release. macOS and Linux run from source.

## Getting help

Run `VizierCLI.exe doctor` and include the output plus the tail of
`%LOCALAPPDATA%\Vizier\logs\vizier.log` in any report. Uncaught native crashes are written to
`crash.log` in the same directory.

## Source and build

Build from source with Python 3.10+ (tested on 3.13) and Inno Setup 6:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The pipeline runs lint, byte-compilation, the 101-test suite, PyInstaller, packaged smoke tests,
portable archiving, installer compilation, and checksum generation. See `README.md` for details.
