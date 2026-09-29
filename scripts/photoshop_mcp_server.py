#!/usr/bin/env python3
"""
Zero-Dependency Stdio MCP Server for Adobe Photoshop (`scripts/photoshop_mcp_server.py`).

Implements the Model Context Protocol (JSON-RPC 2.0 over stdio) using 100% Python
standard library so it runs out of the box on any Windows or macOS laptop without
requiring `pip` or `uv`.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from photoshop_cli import (  # noqa: E402
    cmd_build_from_spec,
    cmd_inspect_psd,
    cmd_preview,
    cmd_status,
    run_jsx_in_photoshop,
)

from laya_decision_gate import evaluate_decision as _laya_eval  # noqa: E402

TOOLS = [
    {'name': 'photoshop_laya_decide', 'description': 'Evaluate a creative brief or decision for Adobe Photoshop using the embedded Laya model (https://github.com/NandhaKishorM/laya) with strict complexity gating. CALL ONLY WHEN NECESSARY for complex/ambiguous multi-branch tasks; for basic tasks, execute directly without calling Laya.', 'inputSchema': {'type': 'object', 'properties': {'state': {'type': 'string', 'description': 'The complex user brief or decision state to evaluate.'}, 'force_laya': {'type': 'boolean', 'description': 'Optional override to force Laya Router evaluation (default: false).'}}, 'required': ['state']}},
    {
        "name": "photoshop_status",
        "description": "Check Adobe Photoshop installation and live connection on macOS or Windows.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "photoshop_inspect_psd",
        "description": "Extract full Design DNA (canvas size, guides, layer tree, exact PostScript fonts, hex palette, and layer FX) from a .psd/.psb file or the active Photoshop document.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Optional path to a .psd or .psb file. Omit to inspect the currently active document in Photoshop.",
                }
            },
        },
    },
    {
        "name": "photoshop_extract_design_dna",
        "description": "Scan a folder of the designer's previous approved designs (.psd, .psb, .png, .jpg, .webp) and extract aggregated Design DNA to .design-dna/raw_dna_scan.json.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_dir": {"type": "string", "description": "Directory or file path of reference designs."},
                "state_dir": {"type": "string", "description": "Output cache directory (default: .design-dna)."},
            },
            "required": ["source_dir"],
        },
    },
    {
        "name": "photoshop_build_from_spec",
        "description": "Build a complete, agency-grade, multi-group layered PSD in Adobe Photoshop from a declarative JSON spec file (includes guides, background, ambient glows, vector cards, Smart Objects, CTA button components, editable typography, overlap check, PSD save, and PNG preview).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spec_json_path": {"type": "string", "description": "Path to the design_spec.json file."}
            },
            "required": ["spec_json_path"],
        },
    },
    {
        "name": "photoshop_execute_jsx",
        "description": "Execute custom ExtendScript (.jsx) inside Adobe Photoshop with all high-level psd_builder.jsx helpers pre-loaded.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "ExtendScript (.jsx) code to run inside Photoshop."}
            },
            "required": ["code"],
        },
    },
    {
        "name": "photoshop_export_preview",
        "description": "Export the currently active Photoshop document to a PNG file for multimodal visual inspection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_png_path": {"type": "string", "description": "Path where the preview PNG should be saved."}
            },
            "required": ["output_png_path"],
        },
    },
]


def handle_tool_call(name: str, arguments: dict) -> dict:
    try:
        if name == "photoshop_laya_decide":
            res = _laya_eval(
                state_text=arguments.get("state", ""),
                force_laya=bool(arguments.get("force_laya", False)),
            )
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
        if name == "photoshop_status":
            res = cmd_status()
        elif name == "photoshop_inspect_psd":
            res = cmd_inspect_psd(arguments.get("file_path"))
        elif name == "photoshop_extract_design_dna":
            src = arguments.get("source_dir", ".")
            state = arguments.get("state_dir", ".design-dna")
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "extract_design_dna.py"), src, "--state-dir", state],
                capture_output=True,
                text=True,
                timeout=180,
            )
            try:
                res = json.loads(proc.stdout)
            except Exception:
                res = {"status": "completed", "stdout": proc.stdout, "stderr": proc.stderr}
        elif name == "photoshop_build_from_spec":
            res = cmd_build_from_spec(arguments["spec_json_path"])
        elif name == "photoshop_execute_jsx":
            code = arguments["code"]
            if "return " not in code:
                code += '\nreturn toJson({ status: "success", documentName: app.documents.length ? app.activeDocument.name : null });'
            res = run_jsx_in_photoshop(code, include_builder=True)
        elif name == "photoshop_export_preview":
            res = cmd_preview(arguments["output_png_path"])
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}], "isError": res.get("status") == "error"}
    except Exception as exc:
        return {"content": [{"type": "text", "text": json.dumps({"status": "error", "message": str(exc)})}], "isError": True}


def main():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "photoshop-design-dna", "version": "1.1.0"},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            continue

        elif method == "ping":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {}}) + "\n")
            sys.stdout.flush()

        elif method == "tools/list":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            params = msg.get("params", {})
            tool_res = handle_tool_call(params.get("name", ""), params.get("arguments", {}) or {})
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": tool_res}) + "\n")
            sys.stdout.flush()

        elif msg_id is not None:
            sys.stdout.write(
                json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}) + "\n"
            )
            sys.stdout.flush()


if __name__ == "__main__":
    main()
