# Photoshop Design DNA (`photoshop-design-dna`)

A cross-platform (**Windows and macOS**) AI Agent Skill & Zero-Dependency MCP Server for **Adobe Photoshop** that:
1. **Extracts your company's or designer's Design DNA** from previous approved designs (`.psd`, `.psb`, `.png`, `.jpg`, `.webp`) — capturing exact PostScript font names, type hierarchy, hex color systems, safe-zone grids, layer grouping conventions, and Layer Styles (drop shadows, glows, strokes).
2. **Turns any plain-text creative brief into a 100% editable, agency-grade, fully layered `.psd` document inside Adobe Photoshop** — complete with organized layer folders, non-printing canvas guides, editable Type layers, vector rounded-rectangle cards, CTA button components, ambient light orbs, Smart Objects, and automatic bounding-box overlap detection.

Built with **zero UXP Developer Mode setup and zero manual clicks inside Photoshop**.

---

## ✨ Key Capabilities

1. **Zero-Plugin Native OS Bridge (`scripts/photoshop_cli.py` & `scripts/photoshop_mcp_server.py`)**:
   - **macOS**: Drives Adobe Photoshop natively via AppleEvents (`com.adobe.Photoshop`) + ExtendScript.
   - **Windows**: Drives Adobe Photoshop natively via COM Automation (`Photoshop.Application`) + ExtendScript.
   - **No UXP plugins to load, no external pip packages required**, and works immediately in your active chat session without restarting the IDE.

2. **Two-Pronged Design DNA Extractor (`scripts/extract_design_dna.py` + `assets/inspect_psd_dna.jsx`)**:
   - **From `.psd` / `.psb` files**: Opens reference PSDs silently in Photoshop and extracts ground-truth PostScript fonts (`textItem.font`), sizes, tracking, leading, hex colors, canvas guides, layer trees, and ActionManager FX (`dropShadow`, `outerGlow`, `stroke`).
   - **From `.png` / `.jpg` / `.webp` files**: Extracts canvas aspect ratios, dark/light luminance profiles, and dominant hex color clusters for multimodal synthesis into `.design-dna/brand_dna.json`.
   - **SHA-256 Corpus Caching**: Extracts your Design DNA once and caches `.design-dna/brand_dna.json` so every future text brief builds immediately in zero extra tokens.

3. **Declarative Layered PSD Builder & ActionManager FX Engine (`assets/psd_builder.jsx`)**:
   - Builds a standardized **7-Group Agency Layer Hierarchy** in Photoshop:
     - `00_BRAND_HEADER_FOOTER`
     - `01_CTA_AND_BADGES`
     - `02_TYPOGRAPHY_HIERARCHY`
     - `03_HERO_ASSETS_AND_GRAPHICS`
     - `04_CARDS_AND_CONTAINERS`
     - `05_ATMOSPHERE_AND_GLOWS`
     - `06_BACKGROUND_SYSTEM`
   - Automatically resolves font PostScript names, centers text inside CTA pills/buttons using exact pixel `bounds`, checks for text-on-text overlaps, saves the layered `.psd`, and exports a `.png` preview for multimodal visual critique.

---

## 📂 Repository Structure

```text
photoshop-design-dna/
├── SKILL.md                            # Complete 5-Stage Agent Skill workflow
├── README.md                           # Quickstart & documentation
├── LICENSE                             # MIT License
├── assets/
│   ├── inspect_psd_dna.jsx             # ExtendScript inspector for reference .psd/.psb files
│   └── psd_builder.jsx                 # High-level Layer, Vector Shape, Type & ActionManager FX builder
└── scripts/
    ├── setup_photoshop_mcp.py          # Cross-platform zero-touch installer & MCP config updater
    ├── photoshop_mcp_server.py         # Zero-dependency Stdio MCP server for Antigravity/Claude/Cursor
    ├── photoshop_cli.py                # Direct CLI bridge to Adobe Photoshop (macOS & Windows)
    └── extract_design_dna.py           # Reference design scanner & SHA-256 Design DNA cache manager
```

---

## 🚀 Installation (Windows & macOS)

> **Prerequisite:** Adobe Photoshop installed on the laptop.

### Option 1: Zero-Touch via Antigravity Chat (Recommended)
Paste this single prompt into Antigravity:
> **"Install the skill from https://github.com/vamshicreates/photoshop-design-dna into `.agents/skills/photoshop-design-dna` and run its setup script."**

### Option 2: 1-Line Terminal Install
```bash
git clone https://github.com/vamshicreates/photoshop-design-dna.git .agents/skills/photoshop-design-dna && python3 .agents/skills/photoshop-design-dna/scripts/setup_photoshop_mcp.py --ping
```
*(On Windows PowerShell, replace `python3` with `python`).*

---

## 🎨 How to Use

1. **Point to Previous Approved Designs (One-Time DNA Extraction)**:
   Drop your previous approved designs (`.psd` files and/or `.png`/`.jpg` exports) into a folder (e.g., `./approved-designs/`) and tell Antigravity:
   > **"Extract our Design DNA from `./approved-designs` and create this new post in Photoshop: [your text brief]."**
2. **Generate Any Future Design from a Text Brief Alone**:
   Once `.design-dna/brand_dna.json` is cached, just share your text brief:
   > **"Using our Design DNA, design a 1080x1350 launch graphic in Photoshop with headline '...' and CTA '...'."**
