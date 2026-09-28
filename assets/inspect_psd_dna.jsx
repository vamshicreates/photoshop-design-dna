#target photoshop
app.displayDialogs = DialogModes.NO;

/**
 * Inspects a Photoshop document (.psd/.psb or activeDocument) and returns a
 * comprehensive Design DNA JSON object (canvas grid, layer hierarchy,
 * typography specs, hex palette, blend modes, and layer bounds).
 */

function rgbToHex(r, g, b) {
    function toHex(n) {
        var h = Math.round(Math.max(0, Math.min(255, n))).toString(16);
        return h.length === 1 ? "0" + h : h;
    }
    return "#" + toHex(r) + toHex(g) + toHex(b);
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
        var arrItems = [];
        for (var i = 0; i < val.length; i++) {
            arrItems.push(toJson(val[i]));
        }
        return "[" + arrItems.join(",") + "]";
    }
    if (typeof val === "object") {
        var objItems = [];
        for (var k in val) {
            if (val.hasOwnProperty(k)) {
                objItems.push('"' + escapeJsonStr(k) + '":' + toJson(val[k]));
            }
        }
        return "{" + objItems.join(",") + "}";
    }
    return "null";
}

function getSolidFillHex() {
    try {
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var desc = executeActionGet(ref);
        if (desc.hasKey(charIDToTypeID("Adjs"))) {
            var adjs = desc.getList(charIDToTypeID("Adjs"));
            if (adjs.count > 0) {
                var adj = adjs.getObjectValue(0);
                if (adj.hasKey(charIDToTypeID("Clr "))) {
                    var clr = adj.getObjectValue(charIDToTypeID("Clr "));
                    var r = clr.getDouble(charIDToTypeID("Rd  "));
                    var g = clr.getDouble(charIDToTypeID("Grn "));
                    var b = clr.getDouble(charIDToTypeID("Bl  "));
                    return rgbToHex(r, g, b);
                }
            }
        }
    } catch (e) {}
    return null;
}

function getLayerEffectsSummary() {
    var fx = [];
    try {
        var ref = new ActionReference();
        ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var desc = executeActionGet(ref);
        if (desc.hasKey(charIDToTypeID("Lefx"))) {
            var lefx = desc.getObjectValue(charIDToTypeID("Lefx"));
            if (lefx.hasKey(charIDToTypeID("DrSh"))) fx.push("dropShadow");
            if (lefx.hasKey(charIDToTypeID("OrGl"))) fx.push("outerGlow");
            if (lefx.hasKey(charIDToTypeID("FrFX"))) fx.push("stroke");
            if (lefx.hasKey(charIDToTypeID("GrFl"))) fx.push("gradientOverlay");
            if (lefx.hasKey(charIDToTypeID("ChFX"))) fx.push("satin");
            if (lefx.hasKey(charIDToTypeID("ebbl"))) fx.push("bevelEmboss");
        }
    } catch (e) {}
    return fx;
}

function inspectDoc(psdPath) {
    var origRuler = app.preferences.rulerUnits;
    var origType = app.preferences.typeUnits;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits = TypeUnits.PIXELS;

    var openedByUs = false;
    var doc = null;

    try {
        if (psdPath && psdPath.length > 0) {
            var f = new File(psdPath);
            if (!f.exists) {
                return toJson({ status: "error", message: "File not found: " + psdPath });
            }
            doc = app.open(f);
            openedByUs = true;
        } else {
            if (app.documents.length === 0) {
                return toJson({ status: "error", message: "No active document open in Photoshop." });
            }
            doc = app.activeDocument;
        }

        var width = doc.width.as("px");
        var height = doc.height.as("px");
        var resolution = doc.resolution;

        var guides = [];
        try {
            for (var g = 0; g < doc.guides.length; g++) {
                guides.push({
                    direction: String(doc.guides[g].direction),
                    coordinate: doc.guides[g].coordinate.as("px")
                });
            }
        } catch (e) {}

        var typographyList = [];
        var colorMap = {};
        var layerTree = [];

        function traverseLayers(container, depth) {
            var items = [];
            if (depth > 8) return items;
            for (var i = 0; i < container.layers.length; i++) {
                var lyr = container.layers[i];
                var b = [0, 0, 0, 0];
                try {
                    b = [
                        Math.round(lyr.bounds[0].as("px")),
                        Math.round(lyr.bounds[1].as("px")),
                        Math.round(lyr.bounds[2].as("px")),
                        Math.round(lyr.bounds[3].as("px"))
                    ];
                } catch (e) {}

                var node = {
                    name: lyr.name,
                    visible: lyr.visible,
                    opacity: Math.round(lyr.opacity),
                    blendMode: String(lyr.blendMode),
                    bounds: b,
                    width: b[2] - b[0],
                    height: b[3] - b[1]
                };

                if (lyr.typename === "LayerSet") {
                    node.type = "GROUP";
                    node.children = traverseLayers(lyr, depth + 1);
                } else {
                    node.type = String(lyr.kind);
                    try {
                        doc.activeLayer = lyr;
                        node.effects = getLayerEffectsSummary();
                    } catch (e) {
                        node.effects = [];
                    }

                    if (lyr.kind === LayerKind.TEXT) {
                        try {
                            var ti = lyr.textItem;
                            var fontName = "Unknown";
                            try { fontName = ti.font; } catch (e) {}
                            var fontSize = 24;
                            try { fontSize = Math.round(ti.size.as("px")); } catch (e) {}
                            var hexColor = "#FFFFFF";
                            try {
                                hexColor = rgbToHex(ti.color.rgb.red, ti.color.rgb.green, ti.color.rgb.blue);
                                colorMap[hexColor] = (colorMap[hexColor] || 0) + 1;
                            } catch (e) {}
                            var tracking = 0;
                            try { tracking = ti.tracking; } catch (e) {}

                            var textSpec = {
                                layerName: lyr.name,
                                contents: String(ti.contents).substring(0, 140),
                                fontPostScriptName: fontName,
                                sizePx: fontSize,
                                colorHex: hexColor,
                                tracking: tracking,
                                bounds: b
                            };
                            node.textSpec = textSpec;
                            typographyList.push(textSpec);
                        } catch (e) {}
                    } else if (lyr.kind === LayerKind.SOLIDFILL) {
                        var fillHex = getSolidFillHex();
                        if (fillHex) {
                            node.fillHex = fillHex;
                            colorMap[fillHex] = (colorMap[fillHex] || 0) + 1;
                        }
                    }
                }
                items.push(node);
            }
            return items;
        }

        layerTree = traverseLayers(doc, 0);

        var palette = [];
        for (var hex in colorMap) {
            if (colorMap.hasOwnProperty(hex)) {
                palette.push({ hex: hex, occurrences: colorMap[hex] });
            }
        }

        var result = {
            status: "success",
            documentName: doc.name,
            canvas: {
                widthPx: width,
                heightPx: height,
                aspectRatio: (width / height).toFixed(3),
                resolutionDpi: resolution,
                mode: String(doc.mode)
            },
            guides: guides,
            typography: typographyList,
            colors: palette,
            layerTree: layerTree
        };

        if (openedByUs && doc) {
            doc.close(SaveOptions.DONOTSAVECHANGES);
        }

        app.preferences.rulerUnits = origRuler;
        app.preferences.typeUnits = origType;
        return toJson(result);
    } catch (err) {
        if (openedByUs && doc) {
            try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}
        }
        app.preferences.rulerUnits = origRuler;
        app.preferences.typeUnits = origType;
        return toJson({ status: "error", message: String(err) + " (line " + err.line + ")" });
    }
}
