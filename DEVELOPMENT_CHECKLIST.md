# Vizier — Development Status & Release Checklist

**Version:** 1.0.0 “Royal Advisor”  
**Status:** Release candidate for Windows (unsigned)  
**Last updated:** 2026-10-26

This document replaces the original planning checklist. Everything below was verified on Windows 11
with Python 3.13.15, PySide6 6.12.0, llama-cpp-python 0.3.36, MCP 2.3.0, PyInstaller, and Inno Setup
6.7.3.

---

## Phase 1 — Core framework [COMPLETE]

- [x] Agent loop with streaming, tool rounds, timeouts, and callbacks
- [x] Tool registry with 19 built-in tools and per-tool enable/disable
- [x] Local GGUF inference via `llama-cpp-python`
- [x] YOLO safety gate (dangerous tools blocked by default)
- [x] Root-restricted filesystem operations with path traversal protection
- [x] Shell execution with timeout
- [x] Computer-use tools (screen, mouse, keyboard, window listing)
- [x] MCP client (stdio/SSE/streamable HTTP) and MCP server (15 exposed tools)
- [x] Hardware detection and tiered model recommendations
- [x] Session persistence with atomic writes
- [x] Config persistence with sanitisation, ranges, atomic save, and `.bak` recovery

## Phase 2 — Desktop GUI [COMPLETE]

- [x] Midnight-palace theme (indigo / antique gold / crimson / turquoise) with Rakkas wordmark
- [x] Streaming chat with tool activity blocks
- [x] Drag-and-drop GGUF loading and automatic last-model restore
- [x] Model Manager: recommendations, downloads, cancellation, local models
- [x] Settings dialog (context, GPU layers, sampling, system prompt, MCP, YOLO)
- [x] Session browser with preview, rename, delete, and restore
- [x] About/diagnostics dialog with health checks, clipboard export, and log-folder shortcut
- [x] Keyboard shortcuts, menus, sidebar controls, status bar
- [x] Safe background-thread shutdown (no QThread destroyed while running)

## Phase 3 — Testing & quality [COMPLETE]

- [x] 101 automated tests (`pytest`)
- [x] Headless Qt tests (`QT_QPA_PLATFORM=offscreen`)
- [x] Agent, tools, filesystem safety, shell, sessions, config recovery
- [x] Model recommendations/download helpers
- [x] MCP configuration and tool adapters
- [x] CLI, diagnostics, and logging tests
- [x] Dialog construction and settings round-trip tests
- [x] `ruff check` clean (E, F, I, UP, B, C4, SIM, RET, PERF, RUF)
- [x] `compileall` clean
- [x] Lazy imports for MCP, computer-use, and download dependencies
- [x] Bundle pruning: unused Qt modules/plugins, Qt translations, Pillow AVIF, `hf_xet`, and
  llama.cpp static import libraries removed automatically before smoke tests

## Phase 4 — Packaging & release [COMPLETE FOR WINDOWS]

- [x] PyInstaller onedir bundle with three executables:
  - `Vizier.exe` (GUI, no console)
  - `VizierCLI.exe` (console)
  - `VizierMCP.exe` (console)
- [x] Windows version resources and application icon
- [x] Branding assets and wizard artwork
- [x] Inno Setup installer (`packaging/windows/Vizier.iss`)
  - per-user install by default, optional all-users elevation
  - Start-menu and desktop shortcuts
  - keeps user data on uninstall unless explicitly removed
- [x] Portable ZIP and SHA-256 checksums
- [x] Automated build pipeline (`scripts/build_windows.ps1`)
- [x] Packaged smoke tests: CLI version/doctor, GUI startup, MCP help
- [x] Silent install validated: version resources, Start-menu/desktop shortcuts, uninstall entry
- [x] Silent uninstall validated: app and shortcuts removed, user data kept by default
- [x] Portable ZIP extracted and smoke-tested; packaged MCP stdio handshake and tool call verified
- [ ] Code signing — blocked: no certificate available; binaries are unsigned

## Phase 5 — Future work [OUT OF SCOPE]

- [ ] Voice input
- [ ] Screen painting / drawing
- [ ] Clipboard history
- [ ] Plugin/skill marketplace
- [ ] Web dashboard
- [ ] User authentication
- [ ] Prebuilt macOS/Linux packages (source installs work)
- [ ] Automatic update checks (deliberately avoided to preserve the no-network guarantee)

---

## Release checklist

Before publishing a build:

1. `python -m ruff check vizier tests packaging scripts`
2. `python -m compileall -q vizier tests packaging scripts`
3. `$env:QT_QPA_PLATFORM="offscreen"; python -m pytest -q`
4. `powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1`
5. Verify the printed smoke-test results and `dist\SHA256SUMS-<version>.txt`.
6. Install with `Vizier-Setup-<version>-x64.exe` on a clean Windows profile.
7. Launch the GUI, download/load a small GGUF, send one prompt, and check tool gating with YOLO off.
8. Uninstall and confirm user data is preserved unless the removal prompt is accepted.
9. Publish the installer, portable ZIP, checksums, and release notes.

## Known limitations

- Windows binaries are unsigned, so SmartScreen may warn.
- GPU acceleration depends on the `llama-cpp-python` wheel; the bundled build is CPU-first.
- Tesseract OCR is an optional external dependency and is not bundled.
- The MCP server intentionally bypasses the agent's YOLO gate; only connect trusted clients.
- macOS and Linux are supported from source, not as prebuilt installers.

## Contributing

- Report issues with the output of `VizierCLI.exe doctor` and the relevant `vizier.log` tail.
- Keep changes PEP 8 compliant and run `ruff` plus the full offline test suite.
- Preserve the midnight-palace visual identity and the local-only privacy guarantee.
