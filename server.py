#!/usr/bin/env python3
"""qet-mcp — MCP stdio server letting an AI draw QElectroTech schematics.

Zero-dependency implementation of the MCP stdio transport (newline-delimited
JSON-RPC 2.0), so it runs on the system Python 3.9. Tools are thin adapters
over qet_xml (file authoring) and the QET fork's --cli-* commands
(render / validate / netlist).

Configuration (env):
  QET_BINARY        path to qelectrotech executable (with --cli support)
  QET_ELEMENTS_DIR  root of the .elmt library used by qet_search_elements
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qet_xml import ElementDefinition, QetProject  # noqa: E402
from qet_xml import index as elmt_index  # noqa: E402
from qet_xml.model import FOLIO_A3_LANDSCAPE  # noqa: E402

ROOT = Path(__file__).resolve().parent
TITLEBLOCK_FILE = ROOT / "data" / "titleblocks" / "huchen_iso7200_a3.titleblock"
QET_BINARY = Path(os.environ.get(
    "QET_BINARY", ROOT.parent / "QET-qeletrotech/build/qelectrotech.app/Contents/MacOS/qelectrotech"))
ELEMENTS_DIR = Path(os.environ.get(
    "QET_ELEMENTS_DIR", ROOT.parent / "QET-qeletrotech/elements"))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "qet-mcp", "version": "0.1.0"}

_current_project: "Path | None" = None  # file-first: state lives on disk


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _project() -> QetProject:
    if _current_project is None:
        raise RuntimeError("no project open — call qet_new_project or "
                           "qet_open_project first")
    return QetProject.open(_current_project)


def _save(prj: QetProject) -> None:
    prj.save(_current_project)


def _find_instance(diagram, ref: str):
    """Resolve an element instance by label (e.g. '-B1') or uuid."""
    for inst in diagram.elements:
        if ref in (inst.label, inst.uuid):
            return inst
    raise KeyError(f"no element with label/uuid {ref!r} "
                   f"(have: {[e.label or e.uuid for e in diagram.elements]})")


def _terminals_info(definition: ElementDefinition):
    return [{"index": i, "name": t.name, "uuid": t.uuid, "x": t.x, "y": t.y,
             "orientation": t.orientation}
            for i, t in enumerate(definition.terminals)]


def _run_cli(*args: str) -> dict:
    proc = subprocess.run(
        [str(QET_BINARY), *args],
        capture_output=True, text=True, timeout=180)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"qet-cli produced no JSON (exit {proc.returncode}): "
            f"{proc.stdout[:400]} / stderr: {proc.stderr[-400:]}")


def _element_names(path: Path) -> "dict[str, str]":
    try:
        import xml.etree.ElementTree as ET
        dom = ET.fromstring(path.read_text(encoding="utf-8"))
        return {n.get("lang", "?"): n.text or ""
                for n in dom.iter("name") if n.tag == "name"}
    except Exception:
        return {}


_index_cache: "dict | None" = None
_synonyms: "dict | None" = None
_aliases: "dict | None" = None


def _index() -> dict:
    global _index_cache
    if _index_cache is None:
        _index_cache = elmt_index.load_index(
            ELEMENTS_DIR, ROOT / ".cache" / "elements_index.json")
    return _index_cache


def _load_data(name: str) -> dict:
    try:
        return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_synonyms() -> dict:
    global _synonyms
    if _synonyms is None:
        _synonyms = _load_data("synonyms.json")
    return _synonyms


def _get_aliases() -> dict:
    global _aliases
    if _aliases is None:
        _aliases = {k: v for k, v in _load_data("aliases.json").items()
                    if not k.startswith("_")}
    return _aliases


def _alias_hits(query: str) -> "list[dict]":
    q = query.lower()
    hits = []
    for role, info in _get_aliases().items():
        haystack = (role + " " + info.get("zh", "")).lower()
        if all(tok in haystack for tok in q.split()):
            hits.append({"alias": role, "path": info["path"],
                         "terminals_note": info.get("terminals", ""),
                         "verified": info.get("verified", False)})
    return hits


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #

def tool_new_project(path: str, title: str = "") -> dict:
    global _current_project
    prj = QetProject.new(title or Path(path).stem)
    _current_project = Path(path).expanduser().resolve()
    _current_project.parent.mkdir(parents=True, exist_ok=True)
    prj.save(_current_project)
    return {"project": str(_current_project), "title": prj.title}


def tool_open_project(path: str) -> dict:
    global _current_project
    p = Path(path).expanduser().resolve()
    prj = QetProject.open(p)          # raises if unreadable
    _current_project = p
    return {
        "project": str(p), "title": prj.title,
        "folios": [{"index": i, "title": d.attrs.get("title", ""),
                    "elements": len(d.elements),
                    "conductors": len(d.conductors)}
                   for i, d in enumerate(prj.diagrams)],
    }


def tool_search_elements(query: str, limit: int = 12,
                         min_terminals: int = 0) -> dict:
    records = elmt_index.search(_index(), query, _get_synonyms(),
                                limit=limit, min_terminals=min_terminals)
    hits = [{
        "path": r["path"],
        "name_en": r["names"].get("en", ""),
        "name_zh": r["names"].get("zh", ""),
        "terminals": [{"index": i, "name": t["name"], "x": t["x"],
                       "y": t["y"], "orientation": t["orientation"]}
                      for i, t in enumerate(r["terminals"])],
        "pitch": r["pitch"],
    } for r in records]
    return {"query": query,
            "aliases": _alias_hits(query),   # curated, verified roles first
            "hits": hits}


def tool_list_categories(prefix: str = "") -> dict:
    return elmt_index.categories(_index(), prefix)


def tool_list_aliases() -> dict:
    return {"aliases": [{"role": k, **v} for k, v in _get_aliases().items()]}


def tool_describe_element(elmt_path: str) -> dict:
    path = (ELEMENTS_DIR / elmt_path) if not Path(elmt_path).is_absolute() \
        else Path(elmt_path)
    definition = ElementDefinition.load(path)
    dom = definition.dom
    return {
        "path": elmt_path,
        "names": _element_names(path),
        "size": {"width": int(dom.get("width", "0")),
                 "height": int(dom.get("height", "0")),
                 "hotspot_x": int(dom.get("hotspot_x", "0")),
                 "hotspot_y": int(dom.get("hotspot_y", "0"))},
        "terminals": _terminals_info(definition),
    }


def tool_place_element(elmt_path: str, x: float, y: float, label: str = "",
                       orientation: int = 0, folio: int = 0) -> dict:
    path = (ELEMENTS_DIR / elmt_path) if not Path(elmt_path).is_absolute() \
        else Path(elmt_path)
    prj = _project()
    inst = prj.diagram(folio).place_element(
        path, x=x, y=y, label=label, orientation=orientation)
    _save(prj)
    return {"uuid": inst.uuid, "label": inst.label,
            "terminals": _terminals_info(inst.definition)}


def tool_draw_conductor(from_element: str, from_terminal: str,
                        to_element: str, to_terminal: str, num: str = "",
                        color: str = "", path: "list | None" = None,
                        folio: int = 0) -> dict:
    prj = _project()
    d = prj.diagram(folio)
    a = _find_instance(d, from_element).terminal(from_terminal)
    b = _find_instance(d, to_element).terminal(to_terminal)
    props = {"num": num}
    if color:
        props["color"] = color
    route = [(seg[0], float(seg[1])) for seg in path] if path else None
    d.connect(a, b, path=route, **props)
    _save(prj)
    return {"from": {"element": a.element_uuid, "terminal": a.terminal.uuid},
            "to": {"element": b.element_uuid, "terminal": b.terminal.uuid},
            "num": num}


def tool_set_label(element: str, label: str, folio: int = 0) -> dict:
    prj = _project()
    inst = _find_instance(prj.diagram(folio), element)
    old = inst.label
    inst.set_label(label)
    _save(prj)
    return {"uuid": inst.uuid, "old_label": old, "label": label}


def tool_move_element(element: str, x: float, y: float,
                      folio: int = 0) -> dict:
    prj = _project()
    inst = _find_instance(prj.diagram(folio), element)
    inst.x, inst.y = x, y
    _save(prj)
    return {"uuid": inst.uuid, "label": inst.label, "x": x, "y": y}


def tool_rotate_element(element: str, orientation: int,
                        folio: int = 0) -> dict:
    prj = _project()
    inst = _find_instance(prj.diagram(folio), element)
    inst.orientation = orientation % 4
    _save(prj)
    return {"uuid": inst.uuid, "label": inst.label,
            "orientation": inst.orientation}


def tool_delete_element(element: str, folio: int = 0) -> dict:
    prj = _project()
    d = prj.diagram(folio)
    inst = _find_instance(d, element)
    removed = d.remove_element(inst)
    _save(prj)
    return {"deleted": inst.label or inst.uuid,
            "conductors_removed": removed}


def tool_add_diagram(title: str = "") -> dict:
    prj = _project()
    d = prj.add_diagram(title)
    from qet_xml.model import FOLIO_A3_LANDSCAPE
    d.attrs.update(FOLIO_A3_LANDSCAPE)
    _save(prj)
    return {"folio_index": len(prj.diagrams) - 1, "title": title,
            "folios": len(prj.diagrams)}


def tool_auto_designate(prefix_map: "dict | None" = None,
                        only_unlabelled: bool = True,
                        folio: int = 0) -> dict:
    """Assign IEC 81346 designations (-<letter><seq>) by category.

    Conservative by default: only numbers un-labelled elements, so existing
    cross-references (parts already sharing -KM1) are never broken. The
    class letter comes from the element's prefix (or prefix_map override
    keyed by embed path). Sequence continues past designations already in
    use for that letter.
    """
    prefix_map = prefix_map or {}
    prj = _project()
    d = prj.diagram(folio)
    counters: "dict[str, int]" = {}
    for e in d.elements:
        m = re.match(r"^-([A-Z]+)(\d+)", e.label or "")
        if m:
            counters[m.group(1)] = max(counters.get(m.group(1), 0),
                                       int(m.group(2)))
    assigned = []
    for e in d.elements:
        if only_unlabelled and e.label:
            continue
        letter = prefix_map.get(e.definition.embed_path) or e.prefix or "E"
        letter = letter.upper()
        counters[letter] = counters.get(letter, 0) + 1
        new = f"-{letter}{counters[letter]}"
        e.set_label(new)
        assigned.append({"uuid": e.uuid, "label": new,
                         "type": e.definition.embed_path})
    _save(prj)
    return {"assigned": assigned, "count": len(assigned)}


def tool_auto_xref(folio: int = 0) -> dict:
    """Cross-reference parts sharing a designation (link each contact to
    its coil of the same label). QET then shows the coil's contact table
    and each contact's parent reference. Run after placing all parts."""
    prj = _project()
    result = prj.diagram(folio).auto_xref()
    _save(prj)
    return result


def tool_list_content(folio: int = 0) -> dict:
    d = _project().diagram(folio)
    return {
        "elements": [{"uuid": e.uuid, "label": e.label,
                      "type": e.definition.embed_path,
                      "x": e.x, "y": e.y, "orientation": e.orientation}
                     for e in d.elements],
        "conductors": [{"element1": c.element1, "terminal1": c.terminal1,
                        "element2": c.element2, "terminal2": c.terminal2,
                        "num": c.props.get("num", "")}
                       for c in d.conductors],
    }


def tool_render(folio: int = 0, width: int = 1200) -> "list":
    out = Path(tempfile.mkstemp(suffix=".png", prefix="qet_render_")[1])
    result = _run_cli("--cli-render", str(_current_project),
                      "--out", str(out), "--folio", str(folio),
                      "--width", str(width))
    if not result.get("ok"):
        raise RuntimeError(f"render failed: {result}")
    data = base64.b64encode(out.read_bytes()).decode("ascii")
    out.unlink(missing_ok=True)
    return [
        {"type": "text", "text": json.dumps(result["rendered"])},
        {"type": "image", "data": data, "mimeType": "image/png"},
    ]


def tool_netlist() -> dict:
    return _run_cli("--cli-netlist", str(_current_project))


def tool_validate() -> dict:
    return _run_cli("--cli-validate", str(_current_project))


# --------------------------------------------------------------------------- #
# titleblock
# --------------------------------------------------------------------------- #

def tool_apply_titleblock(title: str = "", doc_id: str = "",
                          subtitle: str = "", doc_type: str = "&EFS 電路圖",
                          doc_status: str = "正式發行 Released",
                          author: str = "", indexrev: str = "A",
                          date: str = "", techref: str = "",
                          checked_by: str = "", approved_by: str = "",
                          remarks: str = "", a3: bool = True) -> dict:
    """Embed the Huchen ISO 7200 titleblock into every folio and fill it."""
    prj = _project()
    prj.embed_titleblock(ET.fromstring(
        TITLEBLOCK_FILE.read_text(encoding="utf-8")))
    attrs = {"author": author, "title": title, "indexrev": indexrev,
             "date": date, "folio": "%id / %total"}
    # all custom fields written (blanks too) so QET shows no %{...} literals
    props = {"techref": techref, "checked-by": checked_by,
             "approved-by": approved_by, "doc-type": doc_type,
             "doc-status": doc_status, "subtitle": subtitle,
             "doc-id": doc_id, "remarks": remarks}
    for d in prj.diagrams:
        if a3:
            d.attrs.update(FOLIO_A3_LANDSCAPE)
        d.attrs.update({k: v for k, v in attrs.items() if v})
        d.properties.update(props)
        if not any(k.startswith("rev1-") for k in d.properties):
            d.set_revisions([])   # blank out rev1..6 placeholders
    _save(prj)
    return {"applied_to_folios": len(prj.diagrams), "title": title}


def tool_set_revisions(revisions: list, folio: int = 0) -> dict:
    """Fill the revision-history table (accumulates every version).

    Each revision: {idx, date, desc, zone, by, appd}. zone = the drawing
    coordinate of the change (e.g. 'D5').
    """
    prj = _project()
    prj.diagram(folio).set_revisions(
        [{k: str(v) for k, v in r.items()} for r in revisions])
    _save(prj)
    return {"revisions": len(revisions)}


# --------------------------------------------------------------------------- #
# IEC compliance check
# --------------------------------------------------------------------------- #

_LABEL_RE = re.compile(r"^-([A-Z]+)(\d+)$")


def tool_check_iec_compliance(folio: int = 0) -> dict:
    """Check a folio against the company IEC ruleset (81346 / 60204-1).

    Findings carry level MUST/SHOULD; empty findings = compliant.
    """
    rules = _load_data("iec_rules.json")
    valid = set(rules.get("valid_categories", {}))
    forbidden = set(rules.get("forbidden_abbrev", []))
    d = _project().diagram(folio)
    findings = []

    def add(level, rule, target, message):
        findings.append({"level": level, "rule": rule,
                         "target": target, "message": message})

    # R1/R2 — element designations (IEC 81346)
    by_category: "dict[str, list[int]]" = {}
    for e in d.elements:
        label = e.label.strip()
        if not label:
            add("MUST", "81346-label", e.uuid,
                f"元件 {e.definition.embed_path} 無代號")
            continue
        if not label.startswith("-"):
            add("MUST", "81346-prefix", label, f"代號 {label} 缺少產品面前綴 '-'")
        m = _LABEL_RE.match(label)
        if not m:
            add("MUST", "81346-format", label,
                f"代號 {label} 不符 -<類別字母><序號> 格式")
            continue
        letters, num = m.group(1), int(m.group(2))
        if letters in forbidden:
            add("MUST", "81346-abbrev", label,
                f"代號 {label} 使用禁用縮寫(JIS/JIC),應改用 IEC 類別字母")
        elif letters[0] not in valid:
            add("MUST", "81346-category", label,
                f"代號 {label} 類別字母 '{letters[0]}' 不在 IEC 81346 類別表")
        else:
            by_category.setdefault(letters, []).append(num)

    # NB: a repeated designation is NOT an error — one device's parts (a
    # contactor's power poles, coil, aux contacts) legitimately share -KM1
    # via cross-referencing. We only flag sequence gaps.
    for letters, nums in by_category.items():
        expected = set(range(1, max(nums) + 1))
        for gap in sorted(expected - set(nums)):
            add("SHOULD", "81346-sequence", f"-{letters}",
                f"類別 -{letters} 序號跳號(缺 {gap})")

    # R3 — every conductor must carry a wire number (both ends)
    for c in d.conductors:
        if not str(c.props.get("num", "")).strip():
            add("MUST", "60204-wirenum",
                f"{c.props.get('num','')}@{c.element1[:8]}",
                "導線未標線號(等電位編號,兩端皆須)")

    # R4 — dangling terminals (element terminals with no conductor)
    used: "dict[str, set]" = {}
    for c in d.conductors:
        used.setdefault(c.element1, set()).add(c.terminal1)
        used.setdefault(c.element2, set()).add(c.terminal2)
    for e in d.elements:
        total = {t.uuid for t in e.definition.terminals}
        free = total - used.get(e.uuid, set())
        if free:
            add("SHOULD", "connectivity-dangling", e.label or e.uuid,
                f"{e.label or '元件'} 有 {len(free)}/{len(total)} 個端子未接線")

    # R5 — control conductors should not all be plain black
    colors = {str(c.props.get("color", "#000000")).upper()
              for c in d.conductors}
    if d.conductors and colors == {"#000000"}:
        add("SHOULD", "60204-color",
            "(all)", "全部導線為黑色;控制迴路應依迴路類型上色(AC紅/DC藍…)")

    levels = {"MUST": 0, "SHOULD": 0}
    for f in findings:
        levels[f["level"]] = levels.get(f["level"], 0) + 1
    return {"folio": folio, "compliant": levels["MUST"] == 0,
            "counts": levels, "findings": findings}


# --------------------------------------------------------------------------- #
# BOM
# --------------------------------------------------------------------------- #

def _def_names(definition: ElementDefinition) -> "dict[str, str]":
    return {n.get("lang", "?"): (n.text or "")
            for n in definition.dom.iter("name")}


def tool_generate_bom(all_folios: bool = True, folio: int = 0) -> dict:
    """Bill of materials: one line per designation = one physical device.

    Cross-referenced parts sharing a designation (a contactor's poles +
    coil all -KM1) are the SAME device, so grouping is by designation, not
    by symbol type. 'parts' lists the symbols used for that device.
    Un-labelled elements (annotations) are excluded.
    """
    prj = _project()
    diagrams = prj.diagrams if all_folios else [prj.diagram(folio)]
    by_desig: "dict[str, dict]" = {}
    unlabelled = 0
    for d in diagrams:
        for e in d.elements:
            if not e.label:
                unlabelled += 1
                continue
            names = _def_names(e.definition)
            part = names.get("zh") or names.get("en") \
                or e.definition.embed_path.rsplit("/", 1)[-1]
            g = by_desig.setdefault(e.label, {"designation": e.label,
                                              "parts": []})
            if part not in g["parts"]:
                g["parts"].append(part)

    def sort_key(desig: str):
        m = re.match(r"^-?([A-Z]+)(\d+)", desig)
        return (m.group(1), int(m.group(2))) if m else (desig, 0)

    bom = []
    for i, desig in enumerate(sorted(by_desig, key=sort_key), 1):
        g = by_desig[desig]
        bom.append({
            "item": i, "designation": desig, "qty": 1,
            "name": " / ".join(g["parts"]),   # symbol(s) used; fill spec in &EPB
            "parts": g["parts"],
        })
    return {"bom": bom, "devices": len(bom), "unlabelled": unlabelled}


def _schema(props: dict, required: "list[str]") -> dict:
    return {"type": "object", "properties": props, "required": required}

S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}

TOOLS = {
    "qet_new_project": (
        tool_new_project, "Create a new empty QET project file and make it "
        "the current project.",
        _schema({"path": S, "title": S}, ["path"])),
    "qet_open_project": (
        tool_open_project, "Open an existing .qet project file and make it "
        "the current project. Returns folio summaries.",
        _schema({"path": S}, ["path"])),
    "qet_search_elements": (
        tool_search_elements, "Search the QET element library (indexed; "
        "zh/en/fr synonyms understood). Hits include full terminal info and "
        "pole pitch, so qet_describe_element is usually unnecessary. "
        "'aliases' lists curated, verified role matches — prefer them. "
        "Use min_terminals=2 to exclude decorative symbols.",
        _schema({"query": S, "limit": I, "min_terminals": I}, ["query"])),
    "qet_list_categories": (
        tool_list_categories, "Browse the element library taxonomy: list "
        "sub-categories and element counts under a path prefix (empty = "
        "root). Useful when keyword search misses.",
        _schema({"prefix": S}, [])),
    "qet_list_aliases": (
        tool_list_aliases, "List curated element aliases: verified "
        "role-to-element mappings (motor_3ph, contactor_coil, "
        "pushbutton_no, ...) with terminal notes. Fastest way to pick "
        "elements for standard circuits.",
        _schema({}, [])),
    "qet_describe_element": (
        tool_describe_element, "Describe one .elmt element definition: "
        "localized names, size/hotspot, and its terminals (name, uuid, "
        "position, orientation).",
        _schema({"elmt_path": S}, ["elmt_path"])),
    "qet_place_element": (
        tool_place_element, "Place an element instance on a folio of the "
        "current project at scene coordinates (10px grid). Returns the "
        "instance uuid and its terminals.",
        _schema({"elmt_path": S, "x": N, "y": N, "label": S,
                 "orientation": I, "folio": I}, ["elmt_path", "x", "y"])),
    "qet_draw_conductor": (
        tool_draw_conductor, "Connect two element terminals with a "
        "conductor. Elements are referenced by label (e.g. '-K1') or uuid; "
        "terminals by name, or by numeric index for unnamed terminals "
        "(see qet_describe_element). Routing is automatic unless 'path' "
        "gives explicit manhattan segments from terminal1, e.g. "
        "[[\"v\",20],[\"h\",-130],[\"v\",39]] — segments must sum to the "
        "terminal offset (1px tolerance) or QET falls back to autoroute. "
        "Use paths when several same-height conductors would overlap "
        "(phase swaps, parallel feeders).",
        _schema({"from_element": S, "from_terminal": S, "to_element": S,
                 "to_terminal": S, "num": S, "color": S,
                 "path": {"type": "array",
                          "items": {"type": "array",
                                    "prefixItems": [S, N]}},
                 "folio": I},
                ["from_element", "from_terminal", "to_element",
                 "to_terminal"])),
    "qet_set_label": (
        tool_set_label, "Change an element's designation (label). Element "
        "referenced by current label or uuid.",
        _schema({"element": S, "label": S, "folio": I},
                ["element", "label"])),
    "qet_move_element": (
        tool_move_element, "Move an element to new scene coordinates "
        "(10px grid).",
        _schema({"element": S, "x": N, "y": N, "folio": I},
                ["element", "x", "y"])),
    "qet_rotate_element": (
        tool_rotate_element, "Rotate an element: orientation 0/1/2/3 = "
        "0°/90°/180°/270°.",
        _schema({"element": S, "orientation": I, "folio": I},
                ["element", "orientation"])),
    "qet_delete_element": (
        tool_delete_element, "Delete an element and any conductor attached "
        "to it.",
        _schema({"element": S, "folio": I}, ["element"])),
    "qet_add_diagram": (
        tool_add_diagram, "Add a new (A3 landscape) folio to the current "
        "project; returns its index.",
        _schema({"title": S}, [])),
    "qet_auto_designate": (
        tool_auto_designate, "Auto-assign IEC 81346 designations "
        "(-<letter><seq>) by category letter (from each element's prefix). "
        "Conservative: only labels un-labelled elements by default, never "
        "breaking existing cross-references.",
        _schema({"prefix_map": {"type": "object"},
                 "only_unlabelled": {"type": "boolean"}, "folio": I}, [])),
    "qet_auto_xref": (
        tool_auto_xref, "Cross-reference (IEC 61082) parts sharing a "
        "designation: link each slave contact to its master coil of the "
        "same label. QET then renders the coil's contact-location table. "
        "Run once all of a device's parts are placed.",
        _schema({"folio": I}, [])),
    "qet_list_content": (
        tool_list_content, "List all element instances and conductors on a "
        "folio of the current project.",
        _schema({"folio": I}, [])),
    "qet_render": (
        tool_render, "Render a folio of the current project to an image and "
        "return it, so you can visually inspect what you have drawn.",
        _schema({"folio": I, "width": I}, [])),
    "qet_netlist": (
        tool_netlist, "Terminal-level connection list (JSON) of the current "
        "project — check wiring by data instead of by image.",
        _schema({}, [])),
    "qet_validate": (
        tool_validate, "Load-check the current project with the real QET "
        "engine; returns per-folio element/conductor counts.",
        _schema({}, [])),
    "qet_apply_titleblock": (
        tool_apply_titleblock, "Embed the company ISO 7200 titleblock into "
        "every folio (A3 landscape) and fill its fields. Use once a project "
        "is drawn to give it a proper drawing frame.",
        _schema({"title": S, "doc_id": S, "subtitle": S, "doc_type": S,
                 "doc_status": S, "author": S, "indexrev": S, "date": S,
                 "techref": S, "checked_by": S, "approved_by": S,
                 "remarks": S, "a3": {"type": "boolean"}}, [])),
    "qet_set_revisions": (
        tool_set_revisions, "Fill the revision-history table (accumulates "
        "every version, not just the current one). Each revision: "
        "{idx,date,desc,zone,by,appd}; zone = drawing coordinate of the "
        "change (e.g. 'D5'). Unused rows auto-blank.",
        _schema({"revisions": {"type": "array", "items": {"type": "object"}},
                 "folio": I}, ["revisions"])),
    "qet_check_iec_compliance": (
        tool_check_iec_compliance, "Audit a folio against the company IEC "
        "ruleset (81346 designations, 60204-1 wire numbers/colours, "
        "connectivity). Returns findings with level MUST/SHOULD; check "
        "wiring by rules instead of by eye.",
        _schema({"folio": I}, [])),
    "qet_generate_bom": (
        tool_generate_bom, "Bill of materials: group placed elements by "
        "type with their designations and quantity (cross-referenced parts "
        "sharing a designation count as one device). Spans all folios by "
        "default.",
        _schema({"all_folios": {"type": "boolean"}, "folio": I}, [])),
}


# --------------------------------------------------------------------------- #
# MCP stdio transport (newline-delimited JSON-RPC 2.0)
# --------------------------------------------------------------------------- #

def _reply(msg_id, result=None, error=None) -> None:
    msg = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _handle(request: dict) -> None:
    method = request.get("method", "")
    msg_id = request.get("id")
    params = request.get("params") or {}

    if msg_id is None:          # notification — nothing to answer
        return
    if method == "initialize":
        _reply(msg_id, {
            "protocolVersion": params.get("protocolVersion",
                                          PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    elif method == "ping":
        _reply(msg_id, {})
    elif method == "tools/list":
        _reply(msg_id, {"tools": [
            {"name": name, "description": desc, "inputSchema": schema}
            for name, (_, desc, schema) in TOOLS.items()]})
    elif method == "tools/call":
        name = params.get("name", "")
        if name not in TOOLS:
            _reply(msg_id, error={"code": -32601,
                                  "message": f"unknown tool {name}"})
            return
        func = TOOLS[name][0]
        try:
            result = func(**(params.get("arguments") or {}))
            content = (result if isinstance(result, list) else
                       [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False,
                                            indent=1)}])
            _reply(msg_id, {"content": content, "isError": False})
        except Exception as exc:  # tool errors go back in-band
            _reply(msg_id, {"content": [{"type": "text", "text": str(exc)}],
                            "isError": True})
    else:
        _reply(msg_id, error={"code": -32601,
                              "message": f"unknown method {method}"})


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            _handle(json.loads(line))
        except json.JSONDecodeError as exc:
            sys.stderr.write(f"bad json: {exc}\n")


if __name__ == "__main__":
    main()
