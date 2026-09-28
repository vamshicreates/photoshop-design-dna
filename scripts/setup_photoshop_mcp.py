#!/usr/bin/env python3
"""
Zero-Touch Cross-Platform Setup Script for `photoshop-design-dna` (macOS & Windows).

1. Locates the installed Adobe Photoshop executable on macOS or Windows.
2. Registers the zero-dependency `"photoshop"` MCP server in `~/.gemini/config/mcp_config.json`
   (preserving all existing MCP servers and creating a `.backup`).
3. Optionally tests the live Photoshop ExtendScript bridge.
"""

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
MCP_SERVER_SCRIPT = SCRIPTS_DIR / "photoshop_mcp_server.py"
sys.path.insert(0, str(SCRIPTS_DIR))

from photoshop_cli import cmd_status, find_photoshop_executable  # noqa: E402


def update_mcp_config() -> str:
    config_dir = Path.home() / ".gemini" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "mcp_config.json"

    data = {"mcpServers": {}}
    if config_file.exists():
        try:
            shutil.copy2(config_file, config_dir / "mcp_config.json.backup")
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(data.get("mcpServers"), dict):
                data["mcpServers"] = {}
        except Exception:
            data = {"mcpServers": {}}

    python_bin = sys.executable or ("python" if platform.system() == "Windows" else "python3")
    data["mcpServers"]["photoshop"] = {
        "command": python_bin,
        "args": [str(MCP_SERVER_SCRIPT.resolve())],
    }

    config_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(config_file)


def main():
    parser = argparse.ArgumentParser(description="Zero-touch setup for Photoshop Design DNA skill & MCP")
    parser.add_argument("--ping", action="store_true", help="Launch/ping Adobe Photoshop immediately to verify connection")
    args = parser.parse_args()

    ps_bin = find_photoshop_executable()
    mcp_config_path = update_mcp_config()

    summary = {
        "os": platform.system(),
        "photoshop_executable": ps_bin,
        "mcp_server_script": str(MCP_SERVER_SCRIPT.resolve()),
        "mcp_config_updated": mcp_config_path,
        "status": "READY" if ps_bin else "MCP_REGISTERED_INSTALL_PHOTOSHOP",
    }

    if args.ping and ps_bin:
        summary["live_ping"] = cmd_status()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
