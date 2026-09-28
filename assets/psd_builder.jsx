#target photoshop
app.displayDialogs = DialogModes.NO;

/**
 * High-Level Photoshop Layer, Typography, Vector Shape & ActionManager FX Builder
 * (`assets/psd_builder.jsx`) for the `photoshop-design-dna` skill.
 *
 * Compatible across Adobe Photoshop 2021–2026 on macOS and Windows.
 */

function hexToRgbObj(hex) {
    var clean = String(hex || "#FFFFFF").replace("#", "");
    if (clean.length === 3) {
        clean = clean.charAt(0) + clean.charAt(0) + clean.charAt(1) + clean.charAt(1) + clean.charAt(2) + clean.charAt(2);
    }
    var num = parseInt(clean, 16);
    if (isNaN(num)) return { r: 255, g: 255, b: 255 };
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255
    };
}

function makeSolidColor(hex) {
    var rgb = hexToRgbObj(hex);
    var c = new SolidColor();
    c.rgb.red = rgb.r;
    c.rgb.green = rgb.g;
    c.rgb.blue = rgb.b;
    return c;
}

function escapeJsonStr(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n")
        .replace(/\t/g, "\\t");
}

function toJson(val) {
    if (val === null || val === undefined) return "null";
    if (typeof val === "number") return isFinite(val) ? String(val) : "null";
    if (typeof val === "boolean") return val ? "true" : "false";
    if (typeof val === "string") return '"' + escapeJsonStr(val) + '"';
    if (val instanceof Array) {
        var arr = [];
        for (var i = 0; i < val.length; i++) arr.push(toJson(val[i]));
        return "[" + arr.join(",") + "]";
    }
    if (typeof val === "object") {
        var obj = [];
        for (var k in val) {
            if (val.hasOwnProperty(k)) obj.push('"' + escapeJsonStr(k) + '":' + toJson(val[k]));
        }
        return "{" + obj.join(",") + "}";
    }
    return "null";
}

var _FONT_CACHE = null;
function resolveFontPostScript(requestedFont) {
    if (!requestedFont) return "Arial-BoldMT";
    try {
        if (!_FONT_CACHE) {
            _FONT_CACHE = [];
            for (var i = 0; i < app.fonts.length; i++) {
                var f = app.fonts[i];
                _FONT_CACHE.push({
                    ps: f.postScriptName,
                    name: f.name,
                    family: f.family,
                    style: f.style
                });
            }
        }
        var q = String(requestedFont).toLowerCase().replace(/[\s_-]+/g, "");
        for (var j = 0; j < _FONT_CACHE.length; j++) {
            var item = _FONT_CACHE[j];
            if (item.ps.toLowerCase().replace(/[\s_-]+/g, "") === q ||
                item.name.toLowerCase().replace(/[\s_-]+/g, "") === q) {
                return item.ps;
            }
        }
        for (var k = 0; k < _FONT_CACHE.length; k++) {
            var item2 = _FONT_CACHE[k];
            if (item2.ps.toLowerCase().replace(/[\s_-]+/g, "").indexOf(q) !== -1 ||
                item2.name.toLowerCase().replace(/[\s_-]+/g, "").indexOf(q) !== -1) {
                return item2.ps;
            }
        }
    } catch (e) {}
    return requestedFont;
}

function getBoundsPx(layer) {
    try {
        return [
            Math.round(layer.bounds[0].as("px")),
            Math.round(layer.bounds[1].as("px")),
            Math.round(layer.bounds[2].as("px")),
            Math.round(layer.bounds[3].as("px"))
        ];
    } catch (e) {
        return [0, 0, 0, 0];
    }
}

function createCanvas(widthPx, heightPx, dpi, docName, bgHex) {
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;
    var doc = app.documents.add(
        UnitValue(widthPx, "px"),
        UnitValue(heightPx, "px"),
        dpi || 72,
        docName || "Design_DNA_Output",
        NewDocumentMode.RGB,
        DocumentFill.TRANSPARENT
    );
    if (bgHex) {
        createSolidFillLayer("Base_Canvas_Color", bgHex, 100);
    }
    return doc;
}

function ensureGroup(doc, groupName) {
    for (var i = 0; i < doc.layerSets.length; i++) {
        if (doc.layerSets[i].name === groupName) return doc.layerSets[i];
    }
    var grp = doc.layerSets.add();
    grp.name = groupName;
    return grp;
}

function addGuideGrid(doc, marginPx, cols, rows) {
    try {
        var w = doc.width.as("px");
        var h = doc.height.as("px");
        var m = marginPx || Math.round(Math.min(w, h) * 0.06);
        doc.guides.add(Direction.VERTICAL, UnitValue(m, "px"));
        doc.guides.add(Direction.VERTICAL, UnitValue(w - m, "px"));
        doc.guides.add(Direction.HORIZONTAL, UnitValue(m, "px"));
        doc.guides.add(Direction.HORIZONTAL, UnitValue(h - m, "px"));
        doc.guides.add(Direction.VERTICAL, UnitValue(Math.round(w / 2), "px"));
        doc.guides.add(Direction.HORIZONTAL, UnitValue(Math.round(h / 2), "px"));
    } catch (e) {}
}

function createSolidFillLayer(name, hexColor, opacity, parentGroup) {
    var rgb = hexToRgbObj(hexColor);
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putClass(stringIDToTypeID("contentLayer"));
    desc.putReference(charIDToTypeID("null"), ref);

    var layerDesc = new ActionDescriptor();
    var colorDesc = new ActionDescriptor();
    var rgbDesc = new ActionDescriptor();
    rgbDesc.putDouble(charIDToTypeID("Rd  "), rgb.r);
    rgbDesc.putDouble(charIDToTypeID("Grn "), rgb.g);
    rgbDesc.putDouble(charIDToTypeID("Bl  "), rgb.b);
    colorDesc.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), rgbDesc);
    layerDesc.putObject(charIDToTypeID("Type"), stringIDToTypeID("solidColorLayer"), colorDesc);
    desc.putObject(charIDToTypeID("Usng"), stringIDToTypeID("contentLayer"), layerDesc);
    executeAction(charIDToTypeID("Mk  "), desc, DialogModes.NO);

    var lyr = app.activeDocument.activeLayer;
    lyr.name = name || "Solid_Fill";
    if (opacity !== undefined) lyr.opacity = opacity;
    if (parentGroup) lyr.move(parentGroup, ElementPlacement.INSIDE);
    return lyr;
}

function createRoundedRectShape(x, y, w, h, radius, fillHex, strokeHex, strokeWidth, opacity, name, parentGroup) {
    var rgb = hexToRgbObj(fillHex || "#1E293B");
    var r = radius || 0;

    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putClass(stringIDToTypeID("contentLayer"));
    desc.putReference(charIDToTypeID("null"), ref);

    var contentDesc = new ActionDescriptor();
    var colorDesc = new ActionDescriptor();
    var rgbDesc = new ActionDescriptor();
    rgbDesc.putDouble(charIDToTypeID("Rd  "), rgb.r);
    rgbDesc.putDouble(charIDToTypeID("Grn "), rgb.g);
    rgbDesc.putDouble(charIDToTypeID("Bl  "), rgb.b);
    colorDesc.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), rgbDesc);
    contentDesc.putObject(charIDToTypeID("Type"), stringIDToTypeID("solidColorLayer"), colorDesc);

    var shapeDesc = new ActionDescriptor();
    shapeDesc.putInteger(stringIDToTypeID("unitValueQuadVersion"), 1);
    shapeDesc.putUnitDouble(charIDToTypeID("Top "), charIDToTypeID("#Pxl"), y);
    shapeDesc.putUnitDouble(charIDToTypeID("Left"), charIDToTypeID("#Pxl"), x);
    shapeDesc.putUnitDouble(charIDToTypeID("Btom"), charIDToTypeID("#Pxl"), y + h);
    shapeDesc.putUnitDouble(charIDToTypeID("Rght"), charIDToTypeID("#Pxl"), x + w);
    shapeDesc.putUnitDouble(stringIDToTypeID("topRight"), charIDToTypeID("#Pxl"), r);
    shapeDesc.putUnitDouble(stringIDToTypeID("topLeft"), charIDToTypeID("#Pxl"), r);
    shapeDesc.putUnitDouble(stringIDToTypeID("bottomLeft"), charIDToTypeID("#Pxl"), r);
    shapeDesc.putUnitDouble(stringIDToTypeID("bottomRight"), charIDToTypeID("#Pxl"), r);
    contentDesc.putObject(charIDToTypeID("Shp "), charIDToTypeID("Rctn"), shapeDesc);

    desc.putObject(charIDToTypeID("Usng"), stringIDToTypeID("contentLayer"), contentDesc);
    executeAction(charIDToTypeID("Mk  "), desc, DialogModes.NO);

    var lyr = app.activeDocument.activeLayer;
    lyr.name = name || "Rounded_Rect";
    if (opacity !== undefined) lyr.opacity = opacity;
    if (strokeHex && strokeWidth > 0) {
        applyLayerFX(lyr, { stroke: { color: strokeHex, size: strokeWidth, opacity: 100 } });
    }
    if (parentGroup) lyr.move(parentGroup, ElementPlacement.INSIDE);
    return lyr;
}

function createAmbientGlowOrb(cx, cy, radiusPx, hexColor, opacity, name, parentGroup) {
    var doc = app.activeDocument;
    var lyr = doc.artLayers.add();
    lyr.name = name || "Ambient_Glow";
    doc.activeLayer = lyr;

    var r = radiusPx || 250;
    var desc = new ActionDescriptor();
    var ref = new ActionReference();
    ref.putProperty(charIDToTypeID("Chnl"), charIDToTypeID("fsel"));
    desc.putReference(charIDToTypeID("null"), ref);
    var ell = new ActionDescriptor();
    ell.putUnitDouble(charIDToTypeID("Top "), charIDToTypeID("#Pxl"), cy - r);
    ell.putUnitDouble(charIDToTypeID("Left"), charIDToTypeID("#Pxl"), cx - r);
    ell.putUnitDouble(charIDToTypeID("Btom"), charIDToTypeID("#Pxl"), cy + r);
    ell.putUnitDouble(charIDToTypeID("Rght"), charIDToTypeID("#Pxl"), cx + r);
    desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Elps"), ell);
    desc.putUnitDouble(charIDToTypeID("Fthr"), charIDToTypeID("#Pxl"), Math.min(250, Math.max(20, Math.round(r * 0.45))));
    desc.putBoolean(charIDToTypeID("AntA"), true);
    executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);

    doc.selection.fill(makeSolidColor(hexColor || "#38BDF8"));
    doc.selection.deselect();

    lyr.blendMode = BlendMode.SCREEN;
    lyr.opacity = opacity !== undefined ? opacity : 35;
    if (parentGroup) lyr.move(parentGroup, ElementPlacement.INSIDE);
    return lyr;
}

function applyLayerFX(layer, fxSpec) {
    if (!fxSpec) return;
    try {
        app.activeDocument.activeLayer = layer;
        var desc = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Lefx"));
        ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        desc.putReference(charIDToTypeID("null"), ref);

        var lefx = new ActionDescriptor();
        lefx.putUnitDouble(charIDToTypeID("Scl "), charIDToTypeID("#Prc"), 100.0);

        if (fxSpec.dropShadow) {
            var ds = fxSpec.dropShadow;
            var dsRgb = hexToRgbObj(ds.color || "#000000");
            var drSh = new ActionDescriptor();
            drSh.putBoolean(charIDToTypeID("enab"), true);
            drSh.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Mltp"));
            var cDesc = new ActionDescriptor();
            cDesc.putDouble(charIDToTypeID("Rd  "), dsRgb.r);
            cDesc.putDouble(charIDToTypeID("Grn "), dsRgb.g);
            cDesc.putDouble(charIDToTypeID("Bl  "), dsRgb.b);
            drSh.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), cDesc);
            drSh.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), ds.opacity !== undefined ? ds.opacity : 45);
            drSh.putBoolean(charIDToTypeID("uglg"), false);
            drSh.putUnitDouble(charIDToTypeID("lagl"), charIDToTypeID("#Ang"), ds.angle !== undefined ? ds.angle : 120);
            drSh.putUnitDouble(charIDToTypeID("Dstn"), charIDToTypeID("#Pxl"), ds.distance !== undefined ? ds.distance : 12);
            drSh.putUnitDouble(charIDToTypeID("Ckmt"), charIDToTypeID("#Pxl"), ds.spread !== undefined ? ds.spread : 0);
            drSh.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), ds.size !== undefined ? ds.size : 28);
            lefx.putObject(charIDToTypeID("DrSh"), charIDToTypeID("DrSh"), drSh);
        }

        if (fxSpec.outerGlow) {
            var og = fxSpec.outerGlow;
            var ogRgb = hexToRgbObj(og.color || "#38BDF8");
            var orGl = new ActionDescriptor();
            orGl.putBoolean(charIDToTypeID("enab"), true);
            orGl.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Scrn"));
            var ogClr = new ActionDescriptor();
            ogClr.putDouble(charIDToTypeID("Rd  "), ogRgb.r);
            ogClr.putDouble(charIDToTypeID("Grn "), ogRgb.g);
            ogClr.putDouble(charIDToTypeID("Bl  "), ogRgb.b);
            orGl.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), ogClr);
            orGl.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), og.opacity !== undefined ? og.opacity : 45);
            orGl.putUnitDouble(charIDToTypeID("Ckmt"), charIDToTypeID("#Pxl"), og.spread !== undefined ? og.spread : 0);
            orGl.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), og.size !== undefined ? og.size : 24);
            lefx.putObject(charIDToTypeID("OrGl"), charIDToTypeID("OrGl"), orGl);
        }

        if (fxSpec.stroke) {
            var st = fxSpec.stroke;
            var stRgb = hexToRgbObj(st.color || "#FFFFFF");
            var frFX = new ActionDescriptor();
            frFX.putBoolean(charIDToTypeID("enab"), true);
            frFX.putEnumerated(charIDToTypeID("Styl"), charIDToTypeID("FStl"), charIDToTypeID("InsF"));
            frFX.putEnumerated(charIDToTypeID("PntT"), charIDToTypeID("FrFl"), charIDToTypeID("SClr"));
            frFX.putEnumerated(charIDToTypeID("Md  "), charIDToTypeID("BlnM"), charIDToTypeID("Nrml"));
            frFX.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), st.opacity !== undefined ? st.opacity : 100);
            frFX.putUnitDouble(charIDToTypeID("Sz  "), charIDToTypeID("#Pxl"), st.size !== undefined ? st.size : 2);
            var stClr = new ActionDescriptor();
            stClr.putDouble(charIDToTypeID("Rd  "), stRgb.r);
            stClr.putDouble(charIDToTypeID("Grn "), stRgb.g);
            stClr.putDouble(charIDToTypeID("Bl  "), stRgb.b);
            frFX.putObject(charIDToTypeID("Clr "), charIDToTypeID("RGBC"), stClr);
            lefx.putObject(charIDToTypeID("FrFX"), charIDToTypeID("FrFX"), frFX);
        }

        desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Lefx"), lefx);
        executeAction(charIDToTypeID("setd"), desc, DialogModes.NO);
    } catch (e) {}
}

function createTextLayer(spec, parentGroup) {
    var doc = app.activeDocument;
    var lyr = doc.artLayers.add();
    lyr.kind = LayerKind.TEXT;
    lyr.name = spec.name || String(spec.text || "Text").substring(0, 32);

    var ti = lyr.textItem;
    var rawText = String(spec.text || "").replace(/\n/g, "\r");
    if (spec.allCaps) rawText = rawText.toUpperCase();

    if (spec.paragraphWidth && spec.paragraphHeight) {
        ti.kind = TextType.PARAGRAPHTEXT;
        ti.width = UnitValue(spec.paragraphWidth, "px");
        ti.height = UnitValue(spec.paragraphHeight, "px");
    } else {
        ti.kind = TextType.POINTTEXT;
    }

    var resolvedFont = resolveFontPostScript(spec.font || "Arial-BoldMT");
    try { ti.font = resolvedFont; } catch (e) {}
    var fontSize = spec.size || 48;
    ti.size = UnitValue(fontSize, "px");
    ti.useAutoLeading = false;
    ti.leading = UnitValue(spec.leading || Math.round(fontSize * 1.15), "px");
    if (spec.tracking !== undefined) ti.tracking = spec.tracking;
    ti.color = makeSolidColor(spec.color || "#FFFFFF");

    var alignStr = String(spec.align || "left").toLowerCase();
    if (alignStr === "center") ti.justification = Justification.CENTER;
    else if (alignStr === "right") ti.justification = Justification.RIGHT;
    else ti.justification = Justification.LEFT;

    ti.contents = rawText;
    ti.position = [UnitValue(spec.x || 100, "px"), UnitValue(spec.y || 100, "px")];

    // Position adjustment so spec.y represents the TOP of the text bounding box if topAlign is true (default)
    if (spec.topAlign !== false) {
        var b = getBoundsPx(lyr);
        var dy = (spec.y || 100) - b[1];
        var dx = 0;
        if (alignStr === "left") dx = (spec.x || 100) - b[0];
        else if (alignStr === "center") dx = (spec.x || 100) - Math.round((b[0] + b[2]) / 2);
        else if (alignStr === "right") dx = (spec.x || 100) - b[2];
        lyr.translate(UnitValue(dx, "px"), UnitValue(dy, "px"));
    }

    if (spec.opacity !== undefined) lyr.opacity = spec.opacity;
    if (spec.fx) applyLayerFX(lyr, spec.fx);
    if (parentGroup) lyr.move(parentGroup, ElementPlacement.INSIDE);
    return lyr;
}

function createComponentButton(spec, parentGroup) {
    var doc = app.activeDocument;
    var grp = doc.layerSets.add();
    grp.name = spec.name || "CTA_Button_Component";
    if (parentGroup) grp.move(parentGroup, ElementPlacement.INSIDE);

    var x = spec.x || 100;
    var y = spec.y || 100;
    var w = spec.width || 320;
    var h = spec.height || 72;
    var radius = spec.radius !== undefined ? spec.radius : Math.round(h / 2);

    var bgShape = createRoundedRectShape(
        x, y, w, h, radius,
        spec.bgColor || "#38BDF8",
        spec.borderColor || null,
        spec.borderWidth || 0,
        spec.opacity !== undefined ? spec.opacity : 100,
        (spec.name || "CTA") + "_Bg",
        grp
    );
    if (spec.fx) applyLayerFX(bgShape, spec.fx);

    var txtLayer = createTextLayer({
        name: (spec.name || "CTA") + "_Label",
        text: spec.text || "GET STARTED",
        font: spec.font || "Arial-BoldMT",
        size: spec.fontSize || 24,
        color: spec.textColor || "#0F172A",
        tracking: spec.tracking !== undefined ? spec.tracking : 40,
        align: "center",
        x: Math.round(x + w / 2),
        y: y,
        topAlign: true
    }, grp);

    // Vertically center text inside button rect
    var tb = getBoundsPx(txtLayer);
    var th = tb[3] - tb[1];
    var targetTop = Math.round(y + (h - th) / 2);
    txtLayer.translate(UnitValue(0, "px"), UnitValue(targetTop - tb[1], "px"));

    return grp;
}

function placeSmartObject(filePath, x, y, targetWidth, targetHeight, name, parentGroup, fxSpec) {
    var f = new File(filePath);
    if (!f.exists) return null;

    var desc = new ActionDescriptor();
    desc.putPath(charIDToTypeID("null"), f);
    desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
    executeAction(charIDToTypeID("Plc "), desc, DialogModes.NO);

    var lyr = app.activeDocument.activeLayer;
    if (name) lyr.name = name;

    var b = getBoundsPx(lyr);
    var curW = Math.max(1, b[2] - b[0]);
    var curH = Math.max(1, b[3] - b[1]);

    if (targetWidth || targetHeight) {
        var scalePct = 100;
        if (targetWidth && targetHeight) {
            scalePct = Math.min((targetWidth / curW) * 100, (targetHeight / curH) * 100);
        } else if (targetWidth) {
            scalePct = (targetWidth / curW) * 100;
        } else if (targetHeight) {
            scalePct = (targetHeight / curH) * 100;
        }
        lyr.resize(scalePct, scalePct, AnchorPosition.MIDDLECENTER);
    }

    b = getBoundsPx(lyr);
    if (x !== undefined && y !== undefined) {
        lyr.translate(UnitValue(x - b[0], "px"), UnitValue(y - b[1], "px"));
    }

    if (fxSpec) applyLayerFX(lyr, fxSpec);
    if (parentGroup) lyr.move(parentGroup, ElementPlacement.INSIDE);
    return lyr;
}

function exportPreviewPNG(doc, pngPath) {
    var outFile = new File(pngPath);
    var folder = outFile.parent;
    if (folder && !folder.exists) folder.create();

    var opts = new ExportOptionsSaveForWeb();
    opts.format = SaveDocumentType.PNG;
    opts.PNG8 = false;
    opts.transparency = true;
    opts.interlaced = false;
    opts.quality = 100;
    doc.exportDocument(outFile, ExportType.SAVEFORWEB, opts);
    return outFile.fsName;
}

function savePSD(doc, psdPath) {
    var outFile = new File(psdPath);
    var folder = outFile.parent;
    if (folder && !folder.exists) folder.create();

    var opts = new PhotoshopSaveOptions();
    opts.layers = true;
    opts.embedColorProfile = true;
    opts.maximizeCompatibility = true;
    doc.saveAs(outFile, opts, false, Extension.LOWERCASE);
    return outFile.fsName;
}

function buildFromSpec(spec) {
    var c = spec.canvas || {};
    var doc = createCanvas(
        c.width || 1080,
        c.height || 1350,
        c.dpi || 72,
        c.name || "Design_DNA_Output",
        null
    );

    addGuideGrid(doc, c.margin || Math.round(Math.min(c.width || 1080, c.height || 1350) * 0.065));

    // Create standardized Agency Layer Groups (from bottom to top)
    var grpBg = ensureGroup(doc, "06_BACKGROUND_SYSTEM");
    var grpAtmos = ensureGroup(doc, "05_ATMOSPHERE_AND_GLOWS");
    var grpCards = ensureGroup(doc, "04_CARDS_AND_CONTAINERS");
    var grpHero = ensureGroup(doc, "03_HERO_ASSETS_AND_GRAPHICS");
    var grpType = ensureGroup(doc, "02_TYPOGRAPHY_HIERARCHY");
    var grpCta = ensureGroup(doc, "01_CTA_AND_BADGES");
    var grpBrand = ensureGroup(doc, "00_BRAND_HEADER_FOOTER");

    // 1. Background fill
    createSolidFillLayer("Base_Canvas_Bg", c.bgColor || "#0B0F19", 100, grpBg);

    var manifest = [];

    // 2. Ambient Glow Orbs
    var glows = spec.glows || [];
    for (var g = 0; g < glows.length; g++) {
        var gl = glows[g];
        var glowLyr = createAmbientGlowOrb(
            gl.x, gl.y, gl.radius || 300, gl.color || "#38BDF8",
            gl.opacity !== undefined ? gl.opacity : 35,
            gl.name || ("Ambient_Glow_" + (g + 1)),
            grpAtmos
        );
        manifest.push({ name: glowLyr.name, group: grpAtmos.name, type: "GLOW", bounds: getBoundsPx(glowLyr) });
    }

    // 3. Cards & Vector Shapes
    var shapes = spec.shapes || [];
    for (var s = 0; s < shapes.length; s++) {
        var sh = shapes[s];
        var shLyr = createRoundedRectShape(
            sh.x, sh.y, sh.width, sh.height, sh.radius || 24,
            sh.fillColor || "#1E293B",
            sh.strokeColor || null,
            sh.strokeWidth || 0,
            sh.opacity !== undefined ? sh.opacity : 100,
            sh.name || ("Card_" + (s + 1)),
            grpCards
        );
        if (sh.fx) applyLayerFX(shLyr, sh.fx);
        manifest.push({ name: shLyr.name, group: grpCards.name, type: "SHAPE", bounds: getBoundsPx(shLyr) });
    }

    // 4. Placed Images / Logos / Smart Objects
    var images = spec.images || [];
    for (var im = 0; im < images.length; im++) {
        var imgSpec = images[im];
        var targetGrp = imgSpec.isBrandLogo ? grpBrand : grpHero;
        var placed = placeSmartObject(
            imgSpec.path, imgSpec.x, imgSpec.y,
            imgSpec.width, imgSpec.height,
            imgSpec.name || ("Asset_" + (im + 1)),
            targetGrp,
            imgSpec.fx
        );
        if (placed) {
            manifest.push({ name: placed.name, group: targetGrp.name, type: "SMART_OBJECT", bounds: getBoundsPx(placed) });
        }
    }

    // 5. Pills / Badges & CTA Buttons
    var buttons = spec.buttons || [];
    for (var bIdx = 0; bIdx < buttons.length; bIdx++) {
        var btnSpec = buttons[bIdx];
        var btnGrp = createComponentButton(btnSpec, grpCta);
        manifest.push({ name: btnGrp.name, group: grpCta.name, type: "BUTTON_COMPONENT", bounds: getBoundsPx(btnGrp) });
    }

    // 6. Typography Hierarchy
    var texts = spec.texts || [];
    var textBoundsList = [];
    for (var t = 0; t < texts.length; t++) {
        var tSpec = texts[t];
        var targetTextGrp = tSpec.isBrandMeta ? grpBrand : grpType;
        var tLyr = createTextLayer(tSpec, targetTextGrp);
        var tb = getBoundsPx(tLyr);
        textBoundsList.push({ name: tLyr.name, bounds: tb });
        manifest.push({ name: tLyr.name, group: targetTextGrp.name, type: "TEXT", bounds: tb });
    }

    // Check for accidental text-on-text collisions
    var overlaps = [];
    for (var i = 0; i < textBoundsList.length; i++) {
        for (var j = i + 1; j < textBoundsList.length; j++) {
            var a = textBoundsList[i].bounds;
            var b2 = textBoundsList[j].bounds;
            var ix = Math.max(0, Math.min(a[2], b2[2]) - Math.max(a[0], b2[0]));
            var iy = Math.max(0, Math.min(a[3], b2[3]) - Math.max(a[1], b2[1]));
            if (ix > 4 && iy > 4) {
                overlaps.push({ layerA: textBoundsList[i].name, layerB: textBoundsList[j].name, overlapPx: [ix, iy] });
            }
        }
    }

    var savedPsd = null;
    var savedPng = null;
    if (spec.outputPsd) savedPsd = savePSD(doc, spec.outputPsd);
    if (spec.outputPng) savedPng = exportPreviewPNG(doc, spec.outputPng);

    return toJson({
        status: "success",
        documentName: doc.name,
        canvas: { width: doc.width.as("px"), height: doc.height.as("px") },
        savedPsd: savedPsd,
        savedPng: savedPng,
        layerCount: manifest.length,
        textOverlapWarnings: overlaps,
        layers: manifest
    });
}
