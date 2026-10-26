# Publishing Vizier on GitHub

This guide covers the first push and a Windows release. The examples use
`sonamcgoo-dev/vizier`; replace it if you fork the project under another account.
organization name.

## 1. Check the working tree

```powershell
cd C:\Users\ones\Desktop\vizermain
git status
```

Build outputs (`build/`, `dist/`), caches, local logs, and user data are ignored by `.gitignore`.
Never commit a downloaded `.gguf` model or a real `config.json`.

## 2. Run the release checks locally

```powershell
$py = "C:\Users\ones\AppData\Local\Programs\Python\Python313\python.exe"
& $py -m ruff check vizier tests packaging scripts
& $py -m compileall -q vizier tests packaging scripts
$env:QT_QPA_PLATFORM = "offscreen"
& $py -m pytest -q
Remove-Item Env:QT_QPA_PLATFORM
```

Then build the bundle and installer:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Expected artifacts:

- `dist\Vizier\` — unpacked application
- `dist\Vizier-1.0.0-portable-x64.zip`
- `dist\installer\Vizier-Setup-1.0.0-x64.exe`
- `dist\SHA256SUMS-1.0.0.txt`

## 3. Create the first commit

```powershell
git init
git add .
git commit -m "Vizier 1.0.0: local AI agent with GUI, CLI, MCP, and Windows installer"
git branch -M main
```

## 4. Create and push the repository

With the GitHub CLI:

```powershell
gh repo create sonamcgoo-dev/vizier --public --source=. --remote=origin --push
```

Or create an empty repository in the GitHub web UI, then:

```powershell
git remote add origin https://github.com/sonamcgoo-dev/vizier.git
git push -u origin main
```

## 5. Update project URLs

Before publishing, replace the placeholder repository URL in `README.md` clone instructions with
your real repository URL.

## 6. Publish a GitHub release

```powershell
$version = "1.0.0"
gh release create "v$version" `
  "dist\installer\Vizier-Setup-$version-x64.exe" `
  "dist\Vizier-$version-portable-x64.zip" `
  "dist\SHA256SUMS-$version.txt" `
  --title "Vizier $version - Royal Advisor" `
  --notes-file RELEASE_NOTES.md
```

If `RELEASE_NOTES.md` does not exist, write the notes inline with `--notes "..."`.

Release notes should mention:

- Windows 10/11 x64, no Python required
- unsigned binaries (SmartScreen warning) and why
- installer keeps user data on uninstall by default
- no cloud, no API keys, no telemetry
- first-run model download requirement
- SHA-256 checksums

## 7. Optional CI

A minimal GitHub Actions workflow should run on `windows-latest`:

1. Set up Python 3.13.
2. `pip install -e ".[full,dev]"`
3. `ruff check vizier tests packaging scripts`
4. `pytest -q` with `QT_QPA_PLATFORM=offscreen`
5. Optionally install Inno Setup and run `scripts\build_windows.ps1`, uploading `dist\` artifacts.

Do not run model downloads or real inference in CI; the tests use fakes and local fixtures.

## 8. Repository settings

- Add a short description: “100% local AI agent for Windows — no cloud, no API keys, no telemetry.”
- Add topics: `local-llm`, `ai-agent`, `gguf`, `llama-cpp`, `mcp`, `qt`, `pyside6`, `privacy`.
- Enable Issues and Discussions if you want community support.
- Add a `SECURITY.md` if you plan to accept vulnerability reports.
- Keep the license (MIT) visible in the About section.
