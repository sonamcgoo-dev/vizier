"""Generate the PyInstaller VSVersionInfo resource for Windows builds."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "vizier" / "__version__.py"
OUTPUT = ROOT / "build" / "vizier_version_info.txt"


def read_version() -> tuple[str, str]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    version = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    codename = re.search(r'__codename__\s*=\s*["\']([^"\']+)["\']', text)
    return (
        version.group(1) if version else "1.0.0",
        codename.group(1) if codename else "",
    )


TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Vizier Project'),
         StringStruct('FileDescription', 'Vizier - Local AI Agent'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'Vizier'),
         StringStruct('LegalCopyright', 'Copyright (c) Vizier Project'),
         StringStruct('OriginalFilename', 'Vizier.exe'),
         StringStruct('ProductName', 'Vizier ({codename})'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    version, codename = read_version()
    parts = [int(p) for p in re.findall(r"\d+", version)[:3]]
    while len(parts) < 4:
        parts.append(0)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        TEMPLATE.format(
            version=version,
            codename=codename,
            version_tuple=tuple(parts[:4]),
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
