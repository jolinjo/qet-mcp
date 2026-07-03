#!/usr/bin/env python3
"""Convert a DXF drawing into a QET .elmt element.

Geometry: LWPOLYLINE/LINE/ARC/CIRCLE → <polygon> (curves flattened),
axis-aligned ELLIPSE → <ellipse>. Flips Y (DXF up → QET down), centres on
the hotspot, scales (4 px/mm by default).

Terminals: taken from a dedicated DXF layer (default "pin"). Each POINT /
CIRCLE / short line on that layer becomes a QET <terminal>; a TEXT/MTEXT
sitting next to it supplies the pin number. If the layer is absent the
element is built with no terminals (add them later in QET's editor).

The element also gets a dynamic label text so its designation (-Z1…) shows
when placed on a folio. Usage:
  dxf_to_elmt.py <in.dxf> <out.elmt> [name] [scale] [pin_layer]
"""
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import ezdxf
from ezdxf import path as ezpath

STYLE = "line-style:normal;line-weight:normal;filling:none;color:black"
FONT = "Sans Serif,9,-1,5,50,0,0,0,0,0"


def load_polylines(msp, skip_layer=None):
    """Every entity as a flattened list of (x, y) points + closed flag.
    Entities on `skip_layer` (the terminal layer) are ignored."""
    polys, ellipses = [], []
    for e in msp:
        if skip_layer and e.dxf.layer == skip_layer:
            continue
        t = e.dxftype()
        try:
            if t == "ELLIPSE" and abs(e.dxf.major_axis[1]) < 1e-6:
                # axis-aligned ellipse → keep as a true QET ellipse
                cx, cy = e.dxf.center.x, e.dxf.center.y
                a = abs(e.dxf.major_axis[0])
                b = a * e.dxf.ratio
                ellipses.append((cx, cy, a, b))
                continue
            p = ezpath.make_path(e)
            pts = [(round(v.x, 3), round(v.y, 3)) for v in p.flattening(0.25)]
            if len(pts) >= 2:
                polys.append((pts, bool(getattr(e.dxf, "flags", 0) & 1)
                              or getattr(e, "closed", False)))
        except Exception:
            pass
    return polys, ellipses


def _texts(msp):
    """(x, y, string) for every TEXT / MTEXT — used to name pins."""
    out = []
    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            p = e.dxf.insert
            out.append((p.x, p.y, e.dxf.text.strip()))
        elif t == "MTEXT":
            p = e.dxf.insert
            out.append((p.x, p.y, e.plain_text().strip()))
    return out


def terminals_from_layer(msp, layer="pin"):
    """Terminals from a dedicated layer. POINT → its location, CIRCLE →
    centre, short LINE → both ends. Each is named by the nearest TEXT."""
    pts = []
    for e in msp:
        if e.dxf.layer != layer:
            continue
        t = e.dxftype()
        if t == "POINT":
            pts.append((e.dxf.location.x, e.dxf.location.y))
        elif t == "CIRCLE":
            pts.append((e.dxf.center.x, e.dxf.center.y))
        elif t == "LINE":
            pts.append((e.dxf.start.x, e.dxf.start.y))
            pts.append((e.dxf.end.x, e.dxf.end.y))
        else:
            try:
                p = ezpath.make_path(e)
                fl = list(p.flattening(0.25))
                if fl:
                    pts.append((fl[0].x, fl[0].y))
            except Exception:
                pass
    texts = _texts(msp)

    def nearest_text(x, y):
        best, bd = "", 1e18
        for tx_, ty_, s in texts:
            d = (tx_ - x) ** 2 + (ty_ - y) ** 2
            if d < bd:
                bd, best = d, s
        return best
    return [(x, y, nearest_text(x, y)) for x, y in pts]


def _drawable_blocks(doc):
    """Real block definitions (skip *Model_Space/*Paper_Space/anonymous)
    that actually contain geometry. Each becomes one element."""
    out = []
    for b in doc.blocks:
        if b.name.startswith("*"):
            continue
        if any(e.dxftype() not in ("ATTDEF",) for e in b):
            out.append(b)
    return out


def _safe_filename(s):
    s = re.sub(r'[\\/:*?"<>|]+', "", s).strip()
    return re.sub(r"\s+", "_", s) or "element"


def _bbox(e):
    """Axis-aligned bounding box (minx, miny, maxx, maxy) of an entity."""
    try:
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            return (min(s.x, en.x), min(s.y, en.y),
                    max(s.x, en.x), max(s.y, en.y))
        if e.dxftype() == "CIRCLE":
            c, r = e.dxf.center, e.dxf.radius
            return (c.x - r, c.y - r, c.x + r, c.y + r)
        pts = [(v.x, v.y) for v in ezpath.make_path(e).flattening(1.0)]
        if not pts:
            return None
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    except Exception:
        return None


def cluster_entities(entities, gap, min_ents=5):
    """Group entities into spatially-separate clusters: two entities join
    the same cluster if their bounding boxes are within `gap` of each other
    (union-find). Used to split a flat DXF (no blocks) of several parts laid
    out with whitespace between them. Clusters are returned left-to-right;
    groups smaller than `min_ents` (stray notes/dims) are dropped."""
    boxes = [(b, e) for b, e in ((_bbox(e), e) for e in entities) if b]
    boxes.sort(key=lambda be: be[0][0])          # by minx for the sweep
    n = len(boxes)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        ax0, ay0, ax1, ay1 = boxes[i][0]
        for j in range(i + 1, n):
            bx0, by0, bx1, by1 = boxes[j][0]
            if bx0 - gap > ax1:      # sorted by minx → no later box can touch
                break
            if ay0 - gap <= by1 and by0 - gap <= ay1:
                parent[find(i)] = find(j)

    from collections import defaultdict
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(boxes[i])
    out = [[e for _, e in g] for g in groups.values() if len(g) >= min_ents]
    out.sort(key=lambda g: min(_bbox(e)[0] for e in g if _bbox(e)))
    return out


def _build_element(entities, out_path, name, scale, pin_layer, name_en,
                   label, origin=None):
    """Build one .elmt from an iterable of DXF entities. `origin` (DXF
    coords) is the hotspot; if None the bounding-box centre is used."""
    entities = list(entities)
    polys, ellipses = load_polylines(entities, skip_layer=pin_layer)
    has_pin = any(e.dxf.layer == pin_layer for e in entities)
    term_pts = terminals_from_layer(entities, pin_layer) if has_pin else []
    if not polys and not ellipses:
        raise ValueError(f"no drawable geometry for '{name}'")

    if origin is None:
        pts = [p for pl, _ in polys for p in pl]
        pts += [(cx - a, cy - b) for cx, cy, a, b in ellipses]
        pts += [(cx + a, cy + b) for cx, cy, a, b in ellipses]
        ox = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
        oy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    else:
        ox, oy = origin

    def tx(x):
        return round((x - ox) * scale, 2)

    def ty(y):
        return round(-(y - oy) * scale, 2)   # flip Y (DXF up → QET down)

    # element-coord extents → size + hotspot (hotspot sits at 0,0)
    exs, eys = [], []
    for pl, _ in polys:
        exs += [tx(x) for x, _ in pl]
        eys += [ty(y) for _, y in pl]
    for ecx, ecy, a, b in ellipses:
        exs += [tx(ecx - a), tx(ecx + a)]
        eys += [ty(ecy + b), ty(ecy - b)]
    minx, maxx, miny, maxy = min(exs), max(exs), min(eys), max(eys)
    w, h = round(maxx - minx), round(maxy - miny)
    midx, midy = (minx + maxx) / 2, (miny + maxy) / 2

    root = ET.Element("definition", {
        "type": "element", "link_type": "simple", "version": "0.100.0",
        "width": str(w), "height": str(h),
        "hotspot_x": str(round(-minx)), "hotspot_y": str(round(-miny))})
    ET.SubElement(root, "uuid", {"uuid": "{" + str(uuid.uuid4()) + "}"})
    names = ET.SubElement(root, "names")
    ET.SubElement(names, "name", {"lang": "zh"}).text = name
    ET.SubElement(names, "name", {"lang": "en"}).text = name_en or name
    desc = ET.SubElement(root, "description")

    # dynamic label text so the designation (-Z1…) shows on the folio
    if label:
        dt = ET.SubElement(desc, "dynamic_text", {
            "x": str(round(minx)), "y": str(round(miny) - 14), "z": "1",
            "rotation": "0", "font": FONT, "text_width": "-1",
            "Halignment": "AlignLeft", "Valignment": "AlignVCenter",
            "frame": "false", "text_from": "ElementInfo",
            "keep_visual_rotation": "false",
            "uuid": "{" + str(uuid.uuid4()) + "}"})
        ET.SubElement(dt, "text").text = ""
        ET.SubElement(dt, "info_name").text = "label"

    for pl, closed in polys:
        attrs = {}
        for i, (x, y) in enumerate(pl, 1):
            attrs[f"x{i}"] = str(tx(x))
            attrs[f"y{i}"] = str(ty(y))
        attrs["closed"] = "true" if closed else "false"
        attrs["antialias"] = "true"
        attrs["style"] = STYLE
        ET.SubElement(desc, "polygon", attrs)

    for ecx, ecy, a, b in ellipses:
        ET.SubElement(desc, "ellipse", {
            "x": str(tx(ecx - a)), "y": str(ty(ecy + b)),
            "width": str(round(2 * a * scale, 2)),
            "height": str(round(2 * b * scale, 2)),
            "antialias": "true", "style": STYLE})

    # terminals from the pin layer (snapped to 10px grid so conductors
    # route cleanly); orientation from which side of the box it sits on;
    # name = the pin number picked up from the nearest TEXT
    def snap(v):
        return round(v / 10.0) * 10
    for ex, ey, pin in term_pts:
        px, py = tx(ex), ty(ey)
        ddx, ddy = px - midx, py - midy
        ori = ("n" if ddy < 0 else "s") if abs(ddy) >= abs(ddx) \
            else ("e" if ddx > 0 else "w")
        ET.SubElement(desc, "terminal", {
            "uuid": "{" + str(uuid.uuid4()) + "}", "name": pin,
            "x": str(snap(px)), "y": str(snap(py)),
            "orientation": ori, "type": "Generic"})

    ET.indent(tree := ET.ElementTree(root))
    tree.write(out_path, encoding="utf-8", xml_declaration=False)
    return {"name": name, "path": str(out_path),
            "polygons": len(polys), "ellipses": len(ellipses),
            "terminals": len(term_pts), "pin_layer_found": has_pin,
            "width": w, "height": h}


def convert(dxf_path, out_path, name="imported", scale=4.0,
            pin_layer="pin", name_en=None, label=True, split="block",
            cluster_gap=None):
    """DXF → .elmt. `split` chooses how many elements to emit:
      "block"   — one per block definition (named by block, hotspot at its
                  base point); if the DXF has no blocks, the whole drawing
                  is a single element. [default]
      "cluster" — no blocks needed: split the flat modelspace into
                  spatially-separate parts (whitespace gaps) → one element
                  each, named <name>_1.. left-to-right. `cluster_gap` (DXF
                  units) is the min gap that separates parts; None = 3% of
                  the drawing's larger side.
      "none"    — force the whole drawing into a single element.
    Multi-element modes write <stem>_n.elmt / <block>.elmt into out_path's
    directory."""
    doc = ezdxf.readfile(dxf_path)
    out_dir = Path(out_path).parent
    stem = Path(out_path).stem

    if split == "block":
        blocks = _drawable_blocks(doc)
        if blocks:
            elements = []
            for b in blocks:
                bp = b.block.dxf.base_point
                dest = out_dir / (_safe_filename(b.name) + ".elmt")
                try:
                    elements.append(_build_element(
                        list(b), dest, b.name, scale, pin_layer,
                        name_en=None, label=label, origin=(bp.x, bp.y)))
                except ValueError:
                    pass    # empty/degenerate block — skip
            return {"mode": "blocks", "count": len(elements),
                    "elements": elements}

    if split == "cluster":
        ents = list(doc.modelspace())
        boxes = [_bbox(e) for e in ents]
        boxes = [b for b in boxes if b]
        span = max(max(b[2] for b in boxes) - min(b[0] for b in boxes),
                   max(b[3] for b in boxes) - min(b[1] for b in boxes))
        gap = cluster_gap if cluster_gap else round(0.03 * span, 2)
        groups = cluster_entities(ents, gap)
        elements = []
        for i, g in enumerate(groups, 1):
            dest = out_dir / f"{stem}_{i}.elmt"
            try:
                elements.append(_build_element(
                    g, dest, f"{name}_{i}", scale, pin_layer,
                    name_en=None, label=label))
            except ValueError:
                pass
        return {"mode": "clusters", "count": len(elements),
                "gap": gap, "elements": elements}

    st = _build_element(list(doc.modelspace()), out_path, name, scale,
                        pin_layer, name_en, label)
    return {"mode": "single", "count": 1, "elements": [st]}


if __name__ == "__main__":
    a = sys.argv
    print(convert(a[1], a[2],
                  a[3] if len(a) > 3 else "imported",
                  float(a[4]) if len(a) > 4 else 4.0,
                  pin_layer=a[5] if len(a) > 5 else "pin",
                  split=a[6] if len(a) > 6 else "block"))
