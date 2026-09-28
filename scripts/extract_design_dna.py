#!/usr/bin/env python3
"""
Design DNA Extractor (`scripts/extract_design_dna.py`) for `photoshop-design-dna`.

Scans a folder or list of the designer's previous approved designs (`.psd`, `.psb`, `.png`, `.jpg`, `.webp`)
and extracts:
1. From `.psd` / `.psb` files (via Photoshop live inspection + binary header fallback):
   - Canvas dimensions, aspect ratios, guides/margins
   - Exact PostScript font names, sizes, tracking, leading, and hex colors
   - Layer hierarchy conventions (groups, naming patterns, blend modes, FX)
2. From `.png` / `.jpg` / `.webp` exported designs:
   - Exact dimensions, aspect ratios, dark-vs-light luminance profile, and dominant hex color clusters
3. Caches the aggregated report to `.design-dna/raw_dna_scan.json` so the agent can synthesize
   the definitive `.design-dna/brand_dna.json` in one pass.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
from collections import Counter
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from photoshop_cli import cmd_inspect_psd, find_photoshop_executable  # noqa: E402

SUPPORTED_EXTS = {".psd", ".psb", ".png", ".jpg", ".jpeg", ".webp"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def parse_psd_header_binary(path: Path) -> dict:
    """Fast zero-dependency binary header reader for .psd/.psb files."""
    try:
        with open(path, "rb") as f:
            header = f.read(26)
            if len(header) < 26 or header[:4] not in (b"8BPS",):
                return {}
            version, _, channels, height, width, depth, color_mode = struct.unpack(">H6sHIIHH", header[4:26])
            return {
                "widthPx": width,
                "heightPx": height,
                "aspectRatio": round(width / max(1, height), 3),
                "channels": channels,
                "bitDepth": depth,
                "colorMode": color_mode,
            }
    except Exception:
        return {}


def parse_image_dimensions_and_colors(path: Path) -> dict:
    """Extract dimensions and dominant hex colors from PNG/JPEG/WebP (uses PIL if available, else pure-Python header)."""
    info = {"file": str(path), "type": path.suffix.lower()}
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            w, h = img.size
            info["widthPx"] = w
            info["heightPx"] = h
            info["aspectRatio"] = round(w / max(1, h), 3)

            small = img.convert("RGB").resize((80, 80))
            pixels = list(small.getdata())
            avg_lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in pixels) / max(1, len(pixels))
            info["themeLuminance"] = "dark" if avg_lum < 128 else "light"

            # Quantize to 16-level buckets to find dominant brand colors
            buckets = Counter()
            for r, g, b in pixels:
                qr = min(255, round(r / 16) * 16)
                qg = min(255, round(g / 16) * 16)
                qb = min(255, round(b / 16) * 16)
                buckets[f"#{qr:02x}{qg:02x}{qb:02x}"] += 1

            info["dominantHexColors"] = [
                {"hex": hex_code, "sharePct": round(count * 100.0 / len(pixels), 1)}
                for hex_code, count in buckets.most_common(8)
            ]
            return info
    except Exception:
        pass

    # Pure-Python PNG dimension fallback
    try:
        with open(path, "rb") as f:
            data = f.read(32)
            if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
                w, h = struct.unpack(">II", data[16:24])
                info["widthPx"] = w
                info["heightPx"] = h
                info["aspectRatio"] = round(w / max(1, h), 3)
    except Exception:
        pass

    return info


def discover_design_files(target_path: Path) -> list[Path]:
    if target_path.is_file() and target_path.suffix.lower() in SUPPORTED_EXTS:
        return [target_path]
    found = []
    for root, dirs, files in os.walk(target_path):
        # Skip hidden folders and node_modules / venv
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", "__pycache__")]
        for fn in sorted(files):
            p = Path(root) / fn
            if p.suffix.lower() in SUPPORTED_EXTS and not fn.startswith("._"):
                found.append(p)
    return found


def main():
    parser = argparse.ArgumentParser(description="Extract Design DNA from reference PSDs and images")
    parser.add_argument("source", nargs="?", default=".", help="Folder or file path of previous approved designs")
    parser.add_argument("--state-dir", default=".design-dna", help="Directory to store extracted Design DNA")
    parser.add_argument("--skip-photoshop", action="store_true", help="Do not open .psd files in Photoshop during scan")
    args = parser.parse_args()

    source_path = Path(args.source).resolve()
    state_dir = Path(args.state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)

    files = discover_design_files(source_path)
    if not files:
        print(json.dumps({
            "status": "NO_DESIGN_FILES_FOUND",
            "searched_path": str(source_path),
            "supported_extensions": sorted(list(SUPPORTED_EXTS)),
        }, indent=2))
        sys.exit(0)

    corpus_hash = hashlib.sha256(
        "|".join(f"{p.name}:{file_sha256(p)}" for p in files).encode("utf-8")
    ).hexdigest()[:16]

    scan_cache_file = state_dir / "raw_dna_scan.json"
    brand_dna_file = state_dir / "brand_dna.json"

    if scan_cache_file.exists() and brand_dna_file.exists():
        try:
            existing = json.loads(scan_cache_file.read_text(encoding="utf-8"))
            if existing.get("corpus_hash") == corpus_hash:
                print(json.dumps({
                    "status": "CACHE_HIT",
                    "corpus_hash": corpus_hash,
                    "brand_dna_file": str(brand_dna_file),
                    "file_count": len(files),
                }, indent=2))
                sys.exit(0)
        except Exception:
            pass

    ps_bin = find_photoshop_executable()
    psd_reports = []
    image_reports = []
    all_fonts = Counter()
    all_colors = Counter()
    all_dimensions = Counter()

    for fpath in files[:15]:  # Cap at 15 reference files per scan
        ext = fpath.suffix.lower()
        if ext in (".psd", ".psb"):
            header_info = parse_psd_header_binary(fpath)
            psd_entry = {"file": str(fpath), "header": header_info}
            if ps_bin and not args.skip_photoshop:
                live = cmd_inspect_psd(str(fpath))
                if live.get("status") == "success":
                    psd_entry["live_inspection"] = live
                    for t in live.get("typography", []):
                        if t.get("fontPostScriptName"):
                            all_fonts[t["fontPostScriptName"]] += 1
                    for c in live.get("colors", []):
                        if c.get("hex"):
                            all_colors[c["hex"].lower()] += c.get("occurrences", 1)
                    canvas = live.get("canvas", {})
                    if canvas.get("widthPx") and canvas.get("heightPx"):
                        all_dimensions[f"{canvas['widthPx']}x{canvas['heightPx']}"] += 1
            psd_reports.append(psd_entry)
        else:
            img_info = parse_image_dimensions_and_colors(fpath)
            image_reports.append(img_info)
            if img_info.get("widthPx") and img_info.get("heightPx"):
                all_dimensions[f"{img_info['widthPx']}x{img_info['heightPx']}"] += 1
            for c in img_info.get("dominantHexColors", [])[:4]:
                all_colors[c["hex"].lower()] += 1

    aggregated = {
        "status": "SCAN_COMPLETED",
        "corpus_hash": corpus_hash,
        "total_files_scanned": len(psd_reports) + len(image_reports),
        "most_common_canvases": [dim for dim, _ in all_dimensions.most_common(5)],
        "detected_fonts": [f for f, _ in all_fonts.most_common(10)],
        "frequent_hex_colors": [c for c, _ in all_colors.most_common(12)],
        "psd_files": psd_reports,
        "image_files": image_reports,
        "next_step": f"Inspect the reference images visually and write the synthesized brand system to {brand_dna_file}",
    }

    scan_cache_file.write_text(json.dumps(aggregated, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregated, indent=2))


if __name__ == "__main__":
    main()
