#!/usr/bin/env python3
"""
Cross-Platform Zero-Plugin Live Foreground Bridge for Adobe Photoshop (macOS & Windows).

How it works so the user watches every action happen live inside Photoshop:
1. Brings Adobe Photoshop to the foreground on both macOS (`osascript activate`) and
   Windows (`WScript.Shell.AppActivate` + Win32 `SetForegroundWindow` + `$app.Visible = $true`).
2. Executes ExtendScript in **Multi-Stage Live Streaming Mode** (`cmd_build_from_spec`),
   sending each visual stage (Canvas & Guides -> Background & Glows -> Cards -> Smart Objects
   -> CTA Buttons -> Typography Layers) as separate live foreground steps so Photoshop's UI
   redraws continuously in front of the user's eyes.
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


def bring_photoshop_to_front():
    """Bring the Adobe Photoshop application window to the front on macOS or Windows."""
    system = platform.system()
    ps_path = find_photoshop_executable()
    try:
        if system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell application id "com.adobe.Photoshop" to activate'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        elif system == "Windows":
            ps_focus = (
                "$wshell = New-Object -ComObject WScript.Shell; "
                "[void]$wshell.AppActivate('Photoshop'); "
                "[void]$wshell.AppActivate('Adobe Photoshop')"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_focus],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
    except Exception:
        if ps_path and system == "Darwin":
            subprocess.run(["open", "-a", ps_path], check=False)


def run_jsx_in_photoshop(jsx_body: str, include_builder: bool = True, foreground: bool = True, timeout_sec: int = 90) -> dict:
    """
    Execute ExtendScript (`jsx_body`) inside Adobe Photoshop on macOS or Windows
    with the Photoshop window visible in the foreground.
    """
    if foreground:
        bring_photoshop_to_front()

    tmp_dir = Path(tempfile.gettempdir()) / "antigravity_photoshop_bridge"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:10]
    runner_jsx = tmp_dir / f"runner_{run_id}.jsx"
    result_json = tmp_dir / f"result_{run_id}.json"

    builder_code = BUILDER_JSX.read_text(encoding="utf-8") if (include_builder and BUILDER_JSX.exists()) else ""
    result_path_escaped = str(result_json).replace("\\", "/")

    wrapper = f"""#target photoshop
app.displayDialogs = DialogModes.NO;
try {{ app.bringToFront(); }} catch (e) {{}}

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

            if proc.returncode != 0 and not result_json.exists() and ps_path:
                subprocess.run(["open", "-a", ps_path, str(runner_jsx)], check=False)

        elif system == "Windows":
            jsx_win_path = str(runner_jsx).replace("'", "''")
            ps_cmd = (
                "$ErrorActionPreference = 'Stop'; "
                "$app = New-Object -ComObject Photoshop.Application; "
                "$app.Visible = $true; "
                "$wshell = New-Object -ComObject WScript.Shell; "
                "[void]$wshell.AppActivate('Photoshop'); "
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

            if proc.returncode != 0 and not result_json.exists() and ps_path:
                subprocess.Popen([ps_path, str(runner_jsx)])

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
    res = run_jsx_in_photoshop(ping_jsx, include_builder=True, foreground=True, timeout_sec=30)
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
    return run_jsx_in_photoshop(jsx, include_builder=False, foreground=True, timeout_sec=90)


def cmd_build_from_spec(spec_file: str) -> dict:
    """
    Execute the PSD build in Multi-Stage Live Foreground Mode so the user watches
    every stage appear on the Photoshop canvas in real time.
    """
    spec_data = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    if spec_data.get("outputPsd"):
        spec_data["outputPsd"] = str(Path(spec_data["outputPsd"]).resolve()).replace("\\", "/")
    if spec_data.get("outputPng"):
        spec_data["outputPng"] = str(Path(spec_data["outputPng"]).resolve()).replace("\\", "/")
    for img in spec_data.get("images", []):
        if img.get("path"):
            img["path"] = str(Path(img["path"]).resolve()).replace("\\", "/")

    bring_photoshop_to_front()

    # Stage 1: Canvas, Layer Folders, Guides & Base Background
    c = spec_data.get("canvas", {})
    stage1_jsx = f"""
        var c = {json.dumps(c)};
        var doc = createCanvas(c.width || 1080, c.height || 1350, c.dpi || 72, c.name || "Design_DNA_Output", null);
        addGuideGrid(doc, c.margin || Math.round(Math.min(c.width || 1080, c.height || 1350) * 0.065));
        var grpBg = ensureGroup(doc, "06_BACKGROUND_SYSTEM");
        ensureGroup(doc, "05_ATMOSPHERE_AND_GLOWS");
        ensureGroup(doc, "04_CARDS_AND_CONTAINERS");
        ensureGroup(doc, "03_HERO_ASSETS_AND_GRAPHICS");
        ensureGroup(doc, "02_TYPOGRAPHY_HIERARCHY");
        ensureGroup(doc, "01_CTA_AND_BADGES");
        ensureGroup(doc, "00_BRAND_HEADER_FOOTER");
        createSolidFillLayer("Base_Canvas_Bg", c.bgColor || "#0B0F19", 100, grpBg);
        fitCanvasOnScreen();
        forceCanvasRedraw(250);
        return toJson({{ status: "stage1_canvas_ready", docName: doc.name }});
    """
    s1 = run_jsx_in_photoshop(stage1_jsx, include_builder=True, foreground=True)
    if s1.get("status") == "error":
        return s1

    # Stage 2: Ambient Glow Orbs (one live call per glow so user sees each light up)
    for idx, gl in enumerate(spec_data.get("glows", [])):
        gl_jsx = f"""
            var gl = {json.dumps(gl)};
            var grpAtmos = ensureGroup(app.activeDocument, "05_ATMOSPHERE_AND_GLOWS");
            var lyr = createAmbientGlowOrb(gl.x, gl.y, gl.radius || 300, gl.color || "#38BDF8", gl.opacity !== undefined ? gl.opacity : 35, gl.name || "Ambient_Glow_{idx+1}", grpAtmos);
            forceCanvasRedraw(200);
            return toJson({{ status: "glow_added", name: lyr.name }});
        """
        run_jsx_in_photoshop(gl_jsx, include_builder=True, foreground=False)

    # Stage 3: Cards & Vector Containers (one live call per card)
    for idx, sh in enumerate(spec_data.get("shapes", [])):
        sh_jsx = f"""
            var sh = {json.dumps(sh)};
            var grpCards = ensureGroup(app.activeDocument, "04_CARDS_AND_CONTAINERS");
            var lyr = createRoundedRectShape(sh.x, sh.y, sh.width, sh.height, sh.radius || 24, sh.fillColor || "#1E293B", sh.strokeColor || null, sh.strokeWidth || 0, sh.opacity !== undefined ? sh.opacity : 100, sh.name || "Card_{idx+1}", grpCards);
            if (sh.fx) applyLayerFX(lyr, sh.fx);
            forceCanvasRedraw(200);
            return toJson({{ status: "shape_added", name: lyr.name }});
        """
        run_jsx_in_photoshop(sh_jsx, include_builder=True, foreground=False)

    # Stage 4: Smart Objects / Logos (one live call per asset)
    for idx, img_spec in enumerate(spec_data.get("images", [])):
        im_jsx = f"""
            var im = {json.dumps(img_spec)};
            var grp = ensureGroup(app.activeDocument, im.isBrandLogo ? "00_BRAND_HEADER_FOOTER" : "03_HERO_ASSETS_AND_GRAPHICS");
            var lyr = placeSmartObject(im.path, im.x, im.y, im.width, im.height, im.name || "Asset_{idx+1}", grp, im.fx);
            forceCanvasRedraw(200);
            return toJson({{ status: "image_placed", name: lyr ? lyr.name : null }});
        """
        run_jsx_in_photoshop(im_jsx, include_builder=True, foreground=False)

    # Stage 5: Buttons & Pill Badges (one live call per button component)
    for idx, btn_spec in enumerate(spec_data.get("buttons", [])):
        btn_jsx = f"""
            var btn = {json.dumps(btn_spec)};
            var grpCta = ensureGroup(app.activeDocument, "01_CTA_AND_BADGES");
            var grp = createComponentButton(btn, grpCta);
            forceCanvasRedraw(200);
            return toJson({{ status: "button_added", name: grp.name }});
        """
        run_jsx_in_photoshop(btn_jsx, include_builder=True, foreground=False)

    # Stage 6: Editable Typography Layers (one live call per text layer so user watches text appear line by line)
    for idx, t_spec in enumerate(spec_data.get("texts", [])):
        txt_jsx = f"""
            var tSpec = {json.dumps(t_spec)};
            var grp = ensureGroup(app.activeDocument, tSpec.isBrandMeta ? "00_BRAND_HEADER_FOOTER" : "02_TYPOGRAPHY_HIERARCHY");
            var lyr = createTextLayer(tSpec, grp);
            forceCanvasRedraw(200);
            return toJson({{ status: "text_added", name: lyr.name, bounds: getBoundsPx(lyr) }});
        """
        run_jsx_in_photoshop(txt_jsx, include_builder=True, foreground=False)

    # Final Stage: Audit all layer bounds, check text overlaps, save PSD & export preview PNG
    finalize_jsx = f"""
        var doc = app.activeDocument;
        fitCanvasOnScreen();
        forceCanvasRedraw(150);

        var textBoundsList = [];
        var grpType = ensureGroup(doc, "02_TYPOGRAPHY_HIERARCHY");
        for (var i = 0; i < grpType.artLayers.length; i++) {{
            var l = grpType.artLayers[i];
            if (l.kind === LayerKind.TEXT) {{
                textBoundsList.push({{ name: l.name, bounds: getBoundsPx(l) }});
            }}
        }}

        var overlaps = [];
        for (var aIdx = 0; aIdx < textBoundsList.length; aIdx++) {{
            for (var bIdx = aIdx + 1; bIdx < textBoundsList.length; bIdx++) {{
                var a = textBoundsList[aIdx].bounds;
                var b2 = textBoundsList[bIdx].bounds;
                var ix = Math.max(0, Math.min(a[2], b2[2]) - Math.max(a[0], b2[0]));
                var iy = Math.max(0, Math.min(a[3], b2[3]) - Math.max(a[1], b2[1]));
                if (ix > 4 && iy > 4) {{
                    overlaps.push({{ layerA: textBoundsList[aIdx].name, layerB: textBoundsList[bIdx].name, overlapPx: [ix, iy] }});
                }}
            }}
        }}

        var outPsd = {json.dumps(spec_data.get("outputPsd"))};
        var outPng = {json.dumps(spec_data.get("outputPng"))};
        var savedPsd = outPsd ? savePSD(doc, outPsd) : null;
        var savedPng = outPng ? exportPreviewPNG(doc, outPng) : null;

        return toJson({{
            status: "success",
            executionMode: "live_foreground_step_by_step",
            documentName: doc.name,
            canvas: {{ width: doc.width.as("px"), height: doc.height.as("px") }},
            savedPsd: savedPsd,
            savedPng: savedPng,
            textOverlapWarnings: overlaps,
            textLayersBounds: textBoundsList
        }});
    """
    return run_jsx_in_photoshop(finalize_jsx, include_builder=True, foreground=True)


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
    return run_jsx_in_photoshop(jsx, include_builder=True, foreground=True, timeout_sec=60)


def main():
    parser = argparse.ArgumentParser(description="Cross-platform Adobe Photoshop Live Foreground CLI Bridge")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check Adobe Photoshop installation and live connection")

    p_insp = sub.add_parser("inspect-psd", help="Extract full Design DNA from a .psd file or active document")
    p_insp.add_argument("--file", default=None, help="Optional path to .psd/.psb file (omit to inspect active document)")

    p_build = sub.add_parser("build-spec", help="Build a complete layered PSD live on screen in Photoshop from a JSON spec")
    p_build.add_argument("spec_json", help="Path to design_spec.json")

    p_exec = sub.add_parser("exec", help="Execute custom ExtendScript (.jsx) live in Photoshop")
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
        if "return " not in code:
            code = code + '\nforceCanvasRedraw(150);\nreturn toJson({ status: "success", documentName: app.documents.length ? app.activeDocument.name : null });'
        print(json.dumps(run_jsx_in_photoshop(code, include_builder=True, foreground=True), indent=2))
    elif args.cmd == "preview":
        print(json.dumps(cmd_preview(args.output_png), indent=2))


if __name__ == "__main__":
    main()
