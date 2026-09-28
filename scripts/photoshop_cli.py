#!/usr/bin/env python3
"""
Cross-Platform Zero-Plugin Bridge for Adobe Photoshop (macOS & Windows).

How it works without requiring UXP Developer Mode or manual panel clicks:
- Wraps any ExtendScript (.jsx) payload so it writes its JSON return payload
  directly to a temporary UTF-8 file on disk (`result_<id>.json`) AND returns it.
- On macOS: Executes via `osascript` (`tell application id "com.adobe.Photoshop" to do javascript file ...`)
  with fallback to `open -a "<Photoshop.app>" <runner.jsx>`.
- On Windows: Executes via PowerShell COM (`New-Object -ComObject Photoshop.Application`)
  with fallback to direct `"<Photoshop.exe>" "<runner.jsx>"` invocation.
"""

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
INSPECT_JSX = ASSETS_DIR / "inspect_psd_dna.jsx"
BUILDER_JSX = ASSETS_DIR / "psd_builder.jsx"


def find_photoshop_executable() -> str | None:
    """Locate Adobe Photoshop across macOS and Windows."""
    env_path = os.environ.get("PHOTOSHOP_PATH") or os.environ.get("PHOTOSHOP_BIN")
    if env_path and Path(env_path).exists():
        return str(Path(env_path).resolve())

    system = platform.system()
    candidates = []

    if system == "Darwin":
        candidates.extend(sorted(glob.glob("/Applications/Adobe Photoshop*/Adobe Photoshop*.app"), reverse=True))
        candidates.extend(sorted(glob.glob(str(Path.home() / "Applications/Adobe Photoshop*/Adobe Photoshop*.app")), reverse=True))
        try:
            out = subprocess.check_output(
                ["mdfind", "kMDItemCFBundleIdentifier == 'com.adobe.Photoshop'"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            for line in out.splitlines():
                p = line.strip()
                if p.endswith(".app") and os.path.exists(p):
                    candidates.append(p)
        except Exception:
            pass

    elif system == "Windows":
        for base in [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]:
            if not base:
                continue
            candidates.extend(
                sorted(glob.glob(os.path.join(base, "Adobe", "Adobe Photoshop*", "Photoshop.exe")), reverse=True)
            )

    for c in candidates:
        if c and os.path.exists(c):
            return c
    return shutil.which("Photoshop") or shutil.which("photoshop")


def run_jsx_in_photoshop(jsx_body: str, include_builder: bool = True, timeout_sec: int = 90) -> dict:
    """
    Execute ExtendScript (`jsx_body`) inside Adobe Photoshop on macOS or Windows
    and return the parsed JSON result dictionary.
    """
    tmp_dir = Path(tempfile.gettempdir()) / "antigravity_photoshop_bridge"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:10]
    runner_jsx = tmp_dir / f"runner_{run_id}.jsx"
    result_json = tmp_dir / f"result_{run_id}.json"

    builder_code = BUILDER_JSX.read_text(encoding="utf-8") if (include_builder and BUILDER_JSX.exists()) else ""
    result_path_escaped = str(result_json).replace("\\", "/")

    wrapper = f"""#target photoshop
app.displayDialogs = DialogModes.NO;

{builder_code}

function __writeResultFile(strPayload) {{
    var f = new File("{result_path_escaped}");
    f.encoding = "UTF-8";
    f.open("w");
    f.write(String(strPayload));
    f.close();
    return String(strPayload);
}}

function __runMain() {{
    try {{
{jsx_body}
    }} catch (err) {{
        return '{{"status":"error","message":"' + String(err).replace(/\\\\/g, "\\\\\\\\").replace(/"/g, '\\\\"') + ' (line ' + err.line + ')"}}';
    }}
}}

__writeResultFile(__runMain());
"""
    runner_jsx.write_text(wrapper, encoding="utf-8")

    system = platform.system()
    ps_path = find_photoshop_executable()
    stdout_val = ""

    try:
        if system == "Darwin":
            # Primary: AppleScript via bundle identifier com.adobe.Photoshop
            osa_script = (
                'tell application id "com.adobe.Photoshop"\n'
                '    activate\n'
                f'    do javascript file POSIX file "{str(runner_jsx)}"\n'
                'end tell'
            )
            proc = subprocess.run(
                ["osascript", "-e", osa_script],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            stdout_val = (proc.stdout or "").strip()

            # Fallback: open -a "<Photoshop.app>" runner.jsx
            if proc.returncode != 0 and not result_json.exists() and ps_path:
                subprocess.run(["open", "-a", ps_path, str(runner_jsx)], check=False)

        elif system == "Windows":
            # Primary: COM Automation via PowerShell
            jsx_win_path = str(runner_jsx).replace("'", "''")
            ps_cmd = (
                "$ErrorActionPreference = 'Stop'; "
                "$app = New-Object -ComObject Photoshop.Application; "
                f"$res = $app.DoJavaScriptFile('{jsx_win_path}'); "
                "Write-Output $res"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            stdout_val = (proc.stdout or "").strip()

            # Fallback: Direct Photoshop.exe invocation
            if proc.returncode != 0 and not result_json.exists() and ps_path:
                subprocess.Popen([ps_path, str(runner_jsx)])

        # Wait for result_json if launched asynchronously
        deadline = time.time() + min(timeout_sec, 45)
        while not result_json.exists() and time.time() < deadline:
            if stdout_val.startswith("{") and stdout_val.endswith("}"):
                break
            time.sleep(0.35)

        if result_json.exists():
            raw = result_json.read_text(encoding="utf-8").strip()
            return json.loads(raw)

        if stdout_val:
            try:
                return json.loads(stdout_val)
            except Exception:
                return {"status": "success", "raw_output": stdout_val}

        return {
            "status": "error",
            "message": "Photoshop did not return a response. Make sure Adobe Photoshop is installed and open.",
            "detected_photoshop": ps_path,
        }
    finally:
        for p in (runner_jsx, result_json):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


def cmd_status() -> dict:
    ps_bin = find_photoshop_executable()
    if not ps_bin:
        return {
            "status": "PHOTOSHOP_NOT_FOUND",
            "os": platform.system(),
            "message": "Adobe Photoshop was not found in standard paths. Set PHOTOSHOP_PATH if installed in a custom directory.",
        }
    ping_jsx = """
        return toJson({
            status: "success",
            appName: app.name,
            version: String(app.version),
            openDocuments: app.documents.length
        });
    """
    res = run_jsx_in_photoshop(ping_jsx, include_builder=True, timeout_sec=30)
    res["photoshop_executable"] = ps_bin
    return res


def cmd_inspect_psd(psd_path: str | None = None) -> dict:
    inspect_code = INSPECT_JSX.read_text(encoding="utf-8")
    target_arg = ""
    if psd_path:
        abs_psd = str(Path(psd_path).resolve()).replace("\\", "/")
        target_arg = f'"{abs_psd}"'
    jsx = f"""
{inspect_code}
return inspectDoc({target_arg});
"""
    return run_jsx_in_photoshop(jsx, include_builder=False, timeout_sec=90)


def cmd_build_from_spec(spec_file: str) -> dict:
    spec_data = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    # Normalize output paths to absolute paths
    if spec_data.get("outputPsd"):
        spec_data["outputPsd"] = str(Path(spec_data["outputPsd"]).resolve()).replace("\\", "/")
    if spec_data.get("outputPng"):
        spec_data["outputPng"] = str(Path(spec_data["outputPng"]).resolve()).replace("\\", "/")
    for img in spec_data.get("images", []):
        if img.get("path"):
            img["path"] = str(Path(img["path"]).resolve()).replace("\\", "/")

    spec_json_literal = json.dumps(spec_data)
    jsx = f"""
        var specObj = {spec_json_literal};
        return buildFromSpec(specObj);
    """
    return run_jsx_in_photoshop(jsx, include_builder=True, timeout_sec=120)


def cmd_preview(out_png: str) -> dict:
    abs_png = str(Path(out_png).resolve()).replace("\\", "/")
    jsx = f"""
        if (app.documents.length === 0) {{
            return toJson({{ status: "error", message: "No active document in Photoshop." }});
        }}
        var saved = exportPreviewPNG(app.activeDocument, "{abs_png}");
        return toJson({{
            status: "success",
            documentName: app.activeDocument.name,
            previewPng: saved
        }});
    """
    return run_jsx_in_photoshop(jsx, include_builder=True, timeout_sec=60)


def main():
    parser = argparse.ArgumentParser(description="Cross-platform Adobe Photoshop CLI Bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check Adobe Photoshop installation and live connection")

    p_insp = sub.add_parser("inspect-psd", help="Extract full Design DNA from a .psd file or active document")
    p_insp.add_argument("--file", default=None, help="Optional path to .psd/.psb file (omit to inspect active document)")

    p_build = sub.add_parser("build-spec", help="Build a complete layered PSD in Photoshop from a JSON spec file")
    p_build.add_argument("spec_json", help="Path to design_spec.json")

    p_exec = sub.add_parser("exec", help="Execute custom ExtendScript (.jsx) in Photoshop with psd_builder helpers loaded")
    p_exec.add_argument("-c", "--code", help="Inline ExtendScript code")
    p_exec.add_argument("-f", "--file", help="Path to .jsx file")

    p_prev = sub.add_parser("preview", help="Export the current active Photoshop document to a PNG for visual inspection")
    p_prev.add_argument("output_png", help="Output PNG file path")

    args = parser.parse_args()

    if args.cmd == "status":
        print(json.dumps(cmd_status(), indent=2))
    elif args.cmd == "inspect-psd":
        print(json.dumps(cmd_inspect_psd(args.file), indent=2))
    elif args.cmd == "build-spec":
        print(json.dumps(cmd_build_from_spec(args.spec_json), indent=2))
    elif args.cmd == "exec":
        code = Path(args.file).read_text(encoding="utf-8") if args.file else (args.code or sys.stdin.read())
        # If user code doesn't have an explicit return, wrap it so it returns a status JSON
        if "return " not in code:
            code = code + '\nreturn toJson({ status: "success", documentName: app.documents.length ? app.activeDocument.name : null });'
        print(json.dumps(run_jsx_in_photoshop(code, include_builder=True), indent=2))
    elif args.cmd == "preview":
        print(json.dumps(cmd_preview(args.output_png), indent=2))


if __name__ == "__main__":
    main()
