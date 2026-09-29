---
name: photoshop-design-dna
description: >-
  Cross-platform (Windows & macOS) AI Agent Skill for Adobe Photoshop that
  extracts a designer's or company's Design DNA from previous approved designs
  (.psd, .psb, .png, .jpg, .webp) and turns any text brief into a complete,
  agency-grade, fully layered .psd file in Photoshop (with organized layer
  groups, editable typography, vector shapes, Smart Objects, and ActionManager
  layer styles). Zero UXP plugin or manual setup required.
---

# Photoshop Design DNA (`photoshop-design-dna`)

A cross-platform (**Windows and macOS**) AI Agent Skill that connects directly to **Adobe Photoshop** (with **zero UXP plugins or manual setup clicks**), learns a designer's or company's **Design DNA** from their previous approved designs (`.psd`, `.psb`, `.png`, `.jpg`, `.webp`), and turns any plain-text creative brief into a **100% editable, multi-group layered `.psd` document** in Photoshop.

---

## Cross-Platform Execution Notes (Windows & macOS)

- **Python Command:**
  - **Windows (PowerShell / CMD):** Use `python` (or `py -3`).
  - **macOS:** Use `python3`.
- **Skill Directory Resolution:**
  - Determine `<SKILL_DIR>` as `.agents/skills/photoshop-design-dna` (workspace) or `~/.gemini/config/skills/photoshop-design-dna` (global).
- **Zero-Plugin Photoshop Bridge (`scripts/photoshop_cli.py` & `scripts/photoshop_mcp_server.py`):**
  - **macOS:** Communicates directly with Adobe Photoshop via native AppleEvents (`tell application id "com.adobe.Photoshop" to do javascript file ...`) with `open -a` fallback.
  - **Windows:** Communicates directly with Adobe Photoshop via native COM Automation (`New-Object -ComObject Photoshop.Application`) with direct `Photoshop.exe` `.jsx` runner fallback.
  - **Works Immediately Without Restarting the IDE:** You can invoke either the registered MCP tools (`photoshop_*`) OR run `python3 <SKILL_DIR>/scripts/photoshop_cli.py` directly in the terminal.

---

## Stage 0: Zero-Touch Setup & Connection Check

On first run (or if `photoshop_*` MCP tools are not yet loaded in the current session), run:

```bash
python3 <SKILL_DIR>/scripts/setup_photoshop_mcp.py --ping
```

- Automatically locates Adobe Photoshop on Windows or macOS, registers `"photoshop"` in `~/.gemini/config/mcp_config.json`, and verifies live ExtendScript execution.

---

## The 5-Stage Design DNA $\rightarrow$ Brief $\rightarrow$ Layered PSD Pipeline

### Stage 1: Design DNA Extraction & Caching (`.design-dna/brand_dna.json`)

Whenever the user provides previous approved designs (a folder of `.psd`, `.psb`, `.png`, `.jpg`, or `.webp` files) or asks to learn their brand style:

1. **Run the Automated DNA Scanner**:
   ```bash
   python3 <SKILL_DIR>/scripts/extract_design_dna.py <PATH_TO_PREVIOUS_DESIGNS> --state-dir .design-dna
   ```
   - **If `status == "CACHE_HIT"`**: Do **not** re-scan unchanged files. Read `.design-dna/brand_dna.json` directly and proceed to Stage 2.
   - **If `status == "SCAN_COMPLETED"`**:
     - For `.psd` / `.psb` files, `extract_design_dna.py` automatically runs [`assets/inspect_psd_dna.jsx`](assets/inspect_psd_dna.jsx) in Photoshop to extract **exact PostScript font names**, font sizes, tracking, leading, hex color codes, canvas dimensions, guides, layer group conventions, and Layer Styles (`dropShadow`, `outerGlow`, `stroke`).
     - For `.png` / `.jpg` / `.webp` files, `extract_design_dna.py` extracts exact pixel dimensions, aspect ratios, dark/light luminance profiles, and dominant hex color clusters.
2. **Visual Inspection of Approved Designs**:
   - View up to 3–5 representative images from the folder using `view_file` to analyze visual composition, grid margins, badge styles, card treatments, glow placement, and brand logo position.
3. **Synthesize & Save `.design-dna/brand_dna.json`**:
   - Write `.design-dna/brand_dna.json` using this standardized schema:
   ```json
   {
     "brand_name": "Company / Creator Name",
     "corpus_hash": "<from_raw_dna_scan>",
     "canvas_defaults": {
       "width": 1080,
       "height": 1350,
       "dpi": 72,
       "safe_margin_px": 72
     },
     "color_system": {
       "background_primary": "#0B0F19",
       "background_secondary": "#111827",
       "surface_card": "#1E293B",
       "surface_border": "#334155",
       "text_primary": "#F8FAFC",
       "text_secondary": "#94A3B8",
       "accent_primary": "#38BDF8",
       "accent_secondary": "#818CF8",
       "cta_bg": "#38BDF8",
       "cta_text": "#0B0F19"
     },
     "typography_system": {
       "eyebrow": { "font": "Inter-Bold", "size": 22, "tracking": 120, "allCaps": true },
       "hero_headline": { "font": "Inter-ExtraBold", "size": 76, "tracking": -20, "leading": 84, "allCaps": false },
       "subheadline": { "font": "Inter-Medium", "size": 32, "tracking": 0, "leading": 44 },
       "body_copy": { "font": "Inter-Regular", "size": 26, "tracking": 0, "leading": 38 },
       "cta_button": { "font": "Inter-Bold", "size": 26, "tracking": 40, "allCaps": true },
       "brand_meta": { "font": "Inter-SemiBold", "size": 20, "tracking": 60 }
     },
     "layout_archetypes": {
       "alignment": "left | center | split",
       "uses_ambient_glows": true,
       "uses_rounded_cards": true,
       "card_radius_px": 28,
       "button_radius_px": 999,
       "header_footer_pattern": "Top-left brand mark + bottom handle/URL bar"
     },
     "extracted_brand_assets": [
       { "name": "Brand_Logo", "path": "/absolute/path/to/logo.png" }
     ]
   }
   ```

---

### Stage 2: Text Brief Deconstruction & Layered Spec Generation

When the user shares a **text brief** for a new design:
1. Load `.design-dna/brand_dna.json`.
2. Map the brief into a complete **7-Group Agency Layer Architecture**:
   - `00_BRAND_HEADER_FOOTER` — Brand logo Smart Object, header tag, footer handle/website.
   - `01_CTA_AND_BADGES` — Eyebrow pill badge (`createComponentButton`) and primary Call-to-Action button component (vector rounded rectangle + drop shadow/glow + centered editable text layer).
   - `02_TYPOGRAPHY_HIERARCHY` — Fully editable Photoshop Type layers (`LayerKind.TEXT`) for Hero Headline (broken into clean visual lines or accent-colored emphasis lines), Subheadline, Stat Callouts, and Feature Bullets.
   - `03_HERO_ASSETS_AND_GRAPHICS` — Product screenshots, cutouts, icons, or decorative geometric shapes placed as Smart Objects (`placeSmartObject`) with drop shadows/strokes.
   - `04_CARDS_AND_CONTAINERS` — Editable vector rounded-rectangle cards (`createRoundedRectShape`) with surface fill, subtle border stroke, and drop shadow.
   - `05_ATMOSPHERE_AND_GLOWS` — Soft feathered radial light orbs (`createAmbientGlowOrb`) with `BlendMode.SCREEN` for depth and color atmosphere.
   - `06_BACKGROUND_SYSTEM` — Non-destructive Solid Color Fill base layer + optional background texture/grid.
3. Write a declarative **`design_spec.json`** file for [`assets/psd_builder.jsx`](assets/psd_builder.jsx):

```json
{
  "canvas": {
    "name": "Campaign_Post_01",
    "width": 1080,
    "height": 1350,
    "dpi": 72,
    "margin": 72,
    "bgColor": "#0B0F19"
  },
  "outputPsd": "./output/Campaign_Post_01.psd",
  "outputPng": "./output/Campaign_Post_01_preview.png",
  "glows": [
    { "name": "Top_Accent_Glow", "x": 860, "y": 240, "radius": 380, "color": "#38BDF8", "opacity": 30 },
    { "name": "Bottom_Secondary_Glow", "x": 220, "y": 1120, "radius": 340, "color": "#818CF8", "opacity": 25 }
  ],
  "shapes": [
    {
      "name": "Feature_Highlight_Card",
      "x": 72,
      "y": 640,
      "width": 936,
      "height": 360,
      "radius": 28,
      "fillColor": "#151F32",
      "strokeColor": "#334155",
      "strokeWidth": 2,
      "opacity": 95,
      "fx": {
        "dropShadow": { "color": "#000000", "opacity": 45, "distance": 18, "size": 36, "angle": 120 }
      }
    }
  ],
  "buttons": [
    {
      "name": "Eyebrow_Pill_Tag",
      "text": "NEW RELEASE",
      "x": 72,
      "y": 160,
      "width": 250,
      "height": 52,
      "radius": 26,
      "bgColor": "#1E293B",
      "borderColor": "#38BDF8",
      "borderWidth": 2,
      "textColor": "#38BDF8",
      "font": "Inter-Bold",
      "fontSize": 20,
      "tracking": 100
    },
    {
      "name": "Primary_CTA_Button",
      "text": "TRY IT FREE TODAY",
      "x": 72,
      "y": 1080,
      "width": 420,
      "height": 84,
      "radius": 42,
      "bgColor": "#38BDF8",
      "textColor": "#0B0F19",
      "font": "Inter-Bold",
      "fontSize": 26,
      "tracking": 40,
      "fx": {
        "outerGlow": { "color": "#38BDF8", "opacity": 35, "size": 28 },
        "dropShadow": { "color": "#000000", "opacity": 40, "distance": 12, "size": 24 }
      }
    }
  ],
  "texts": [
    {
      "name": "Hero_Headline_Line1",
      "text": "DESIGN AT THE",
      "font": "Inter-ExtraBold",
      "size": 78,
      "color": "#F8FAFC",
      "tracking": -20,
      "x": 72,
      "y": 245,
      "align": "left"
    },
    {
      "name": "Hero_Headline_Accent",
      "text": "SPEED OF THOUGHT.",
      "font": "Inter-ExtraBold",
      "size": 78,
      "color": "#38BDF8",
      "tracking": -20,
      "x": 72,
      "y": 335,
      "align": "left"
    },
    {
      "name": "Subheadline_Copy",
      "text": "Turn approved brand systems into fully layered\rPhotoshop files from a single text brief.",
      "font": "Inter-Medium",
      "size": 32,
      "leading": 46,
      "color": "#94A3B8",
      "x": 72,
      "y": 450,
      "align": "left"
    }
  ]
}
```

---

### Stage 3: Build the Layered PSD in Adobe Photoshop

Execute the spec in Photoshop via `photoshop_cli.py build-spec` (or the `photoshop_build_from_spec` MCP tool):

```bash
python3 <SKILL_DIR>/scripts/photoshop_cli.py build-spec ./output/design_spec.json
```

- **Custom Bespoke Layers (Optional)**: If the brief calls for custom decorative paths, diagonal split masks, or bespoke layer manipulations beyond the JSON spec, run additional `.jsx` code on the open document via:
  ```bash
  python3 <SKILL_DIR>/scripts/photoshop_cli.py exec -f ./output/custom_details.jsx
  ```
  *(All helper functions from [`assets/psd_builder.jsx`](assets/psd_builder.jsx) — `createRoundedRectShape`, `createTextLayer`, `createComponentButton`, `createAmbientGlowOrb`, `applyLayerFX`, `placeSmartObject`, `exportPreviewPNG`, `savePSD` — are automatically pre-loaded!)*

---

### Stage 4: Automated Overlap Audit & Multimodal Visual Critique Loop

Never deliver a Photoshop file without inspecting both the **JSON Layer Bounds Manifest** and the **Visual PNG Preview**:

1. **Check `textOverlapWarnings` in the Build Output**:
   - `psd_builder.jsx` automatically computes the exact pixel bounding box (`[left, top, right, bottom]`) of every rendered layer and flags any text-on-text collisions in `textOverlapWarnings`. If any warning is present, immediately adjust the `y` coordinates or font sizes and rebuild.
2. **Inspect the Rendered Preview (`view_file`)**:
   - View `outputPng` (`Campaign_Post_01_preview.png`) with `view_file` and compare it against the company's Design DNA across 5 checks:
     1. **Grid & Safe Margins**: Are all text elements and cards aligned cleanly to the margin guide (`x = 72`) with balanced negative space?
     2. **Typography Hierarchy & Line Breaks**: Does the Hero Headline dominate cleanly without awkward word wraps or cramped leading?
     3. **Color & Contrast Fidelity**: Do background, card surface, accent highlights, and text contrast match `.design-dna/brand_dna.json`?
     4. **Component Polish**: Is the CTA button label perfectly centered horizontally and vertically inside its pill/rounded rect?
     5. **Layer Completeness**: Are all 7 layer groups properly named and organized so a human designer can open the `.psd` and edit any text or shape in 1 click?
3. **Self-Correction Pass**:
   - If anything looks off in `preview.png`, update `design_spec.json` (or run a targeted `photoshop_cli.py exec` adjustment) and re-verify `preview.png`.

---

### Stage 5: Final Delivery

Deliver to the user:
1. The **live open document inside Adobe Photoshop** with all organized layer groups (`00_BRAND_HEADER_FOOTER` through `06_BACKGROUND_SYSTEM`).
2. The saved **`.psd` file path** (with `maximizeCompatibility = true` and all editable Type/Shape/Smart Object layers preserved).
3. The exported high-resolution **`.png` preview** and a concise summary of the extracted Design DNA tokens applied.

---

## Embedded Laya Decision Gate (`NandhaKishorM/laya`) — Call Laya ONLY When Necessary

This skill embeds the **[Laya Non-Autoregressive Decision Model (`https://github.com/NandhaKishorM/laya`)](https://github.com/NandhaKishorM/laya)** inside [`scripts/laya_decision_gate.py`](scripts/laya_decision_gate.py) (`from laya import Router`).

### Strict Execution Policy: When to Call Laya vs. Manual Execution

1. **BASIC / EXPLICIT TASKS → DO NOT CALL LAYA (Execute Directly & Manually)**:
   - If the user gives a clear, direct, or single-step command (for example: *"change headline text to 'HELLO WORLD'"*, *"set background color to #0F172A"*, *"export PNG preview"*, *"move CTA button down 40px"*), **DO NOT call Laya**.
   - Execute the step directly using the skill's native CLI/MCP tools to keep execution instant and zero-overhead.
2. **COMPLEX / AMBIGUOUS MULTI-BRANCH TASKS → CALL LAYA (`laya_decision_gate.py`)**:
   - Call Laya **only when** a genuine typed decision (`choice`, `score`, `noul`) across multiple creative lanes or ambiguous requirements is needed (for example: *Select the optimal multi-group composition archetype and visual hierarchy for an open-ended campaign brief*; *Arbitrate between competing Design DNA layout patterns across multiple product categories*).
   - Run the Laya Decision Gate:
     ```bash
     python3 scripts/laya_decision_gate.py --state "<user_brief_or_complex_state>"
     ```
   - `laya_decision_gate.py` automatically runs `should_call_laya()` first:
     - If the task is basic, it immediately returns `"laya_called": false, "execution_mode": "direct_manual_execution"` without loading neural weights.
     - If the task is genuinely complex, it invokes `laya.Router().predict(...)` in a single forward pass (~33ms) with calibrated confidence gating (`min_confidence=0.55`) and neutral `noul` labels (`{"true": "A", "false": "B"}`).
   - To install the `laya` neural weights package (`pip install laya`) on a machine:
     ```bash
     python3 scripts/laya_decision_gate.py --install
     ```
