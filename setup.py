"""Packaging configuration for Vizier."""
from __future__ import annotations

import re
from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent
VERSION_FILE = ROOT / "vizier" / "__version__.py"


def read_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else "0.0.0"


def read_readme() -> str:
    readme = ROOT / "README.md"
    return readme.read_text(encoding="utf-8") if readme.exists() else ""


setup(
    name="vizier",
    version=read_version(),
    description="A 100% local AI agent for computer use, filesystem management, and general assistance.",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="sonamcgoo-dev",
    author_email="sonamcgoo@gmail.com",
    url="https://github.com/sonamcgoo-dev/vizier",
    project_urls={
        "Source": "https://github.com/sonamcgoo-dev/vizier",
        "Issues": "https://github.com/sonamcgoo-dev/vizier/issues",
    },
    license="MIT",
    packages=find_packages(include=["vizier", "vizier.*"]),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28",
    ],
    extras_require={
        "gui": ["PySide6>=6.5"],
        "llm": ["llama-cpp-python>=0.2.60"],
        "computer": [
            "pyautogui>=0.9.54",
            "pyscreeze>=0.1.30",
            "Pillow>=10.0",
            "pytesseract>=0.3.10",
            "pygetwindow>=0.0.9",
            "pyperclip>=1.8",
        ],
        "mcp": ["mcp>=2.0"],
        "full": [
            "PySide6>=6.5",
            "llama-cpp-python>=0.2.60",
            "pyautogui>=0.9.54",
            "pyscreeze>=0.1.30",
            "Pillow>=10.0",
            "pytesseract>=0.3.10",
            "pygetwindow>=0.0.9",
            "pyperclip>=1.8",
            "mcp>=2.0",
        ],
        "dev": [
            "pytest>=7.4",
            "pytest-asyncio>=0.23",
            "ruff>=0.4",
        ],
    },
    entry_points={
        "console_scripts": [
            "vizier=vizier.cli:main",
            "vizier-mcp-server=vizier.servers.mcp_server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords=["ai", "agent", "local", "llm", "gguf", "mcp", "computer-use"],
)
