#!/usr/bin/env python3
"""Walking skeleton: generate a minimal .qet proving the file-first pipeline.

- Embeds a real element definition (cpi.elmt) into the project collection.
- Places two instances, connects them with ONE conductor in modern uuid
  format, deliberately WITHOUT <segment> children -> QET must autoroute
  on load (conductor.cpp:1147).
"""
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

QET_REPO = Path(__file__).resolve().parents[2] / "QET-qeletrotech"
ELMT_SRC = QET_REPO / "elements/10_electric/99_miscellaneous_unsorted/cpi.elmt"
OUT = Path(__file__).resolve().parent / "out" / "min.qet"

# Terminal uuids inside cpi.elmt (definition-level, shared by all instances)
TERM_1 = "{fdc849e2-24c2-4da0-8749-c89aab1818c9}"  # name="1", top (y=-20)
TERM_2 = "{b94d18f8-9ad7-4c6a-a10c-1edd09d97b4f}"  # name="2", bottom (y=20)


def new_uuid() -> str:
    return "{" + str(uuid.uuid4()) + "}"


def element_instance(inst_uuid: str, x: int, y: int, label: str) -> ET.Element:
    e = ET.Element("element", {
        "uuid": inst_uuid,
        "type": "embed://import/cpi.elmt",
        "x": str(x), "y": str(y),
        "orientation": "0", "z": "10",
        "prefix": "B", "freezeLabel": "false",
    })
    infos = ET.SubElement(e, "elementInformations")
    info = ET.SubElement(infos, "elementInformation",
                         {"show": "1", "name": "label"})
    info.text = label
    return e


def conductor(el1: str, t1: str, el2: str, t2: str) -> ET.Element:
    # Modern uuid linking; NO <segment> children on purpose (autoroute on load)
    return ET.Element("conductor", {
        "element1": el1, "terminal1": t1,
        "element2": el2, "terminal2": t2,
        "type": "multi", "num": "101",
        "color": "#000000", "condsize": "1", "displaytext": "1",
        "x": "0", "y": "0", "freezeLabel": "false",
    })


def main() -> None:
    project = ET.Element("project", {"title": "MCP walking skeleton",
                                     "version": "0.100.0"})

    diagram = ET.SubElement(project, "diagram", {
        "title": "skeleton", "order": "1",
        "cols": "17", "colsize": "60", "rows": "8", "rowsize": "80",
        "author": "qet-mcp", "date": "null",
    })

    a, b = new_uuid(), new_uuid()
    # Diagram children must live inside wrapper nodes <elements>/<conductors>,
    # direct children are silently ignored (diagram.cpp:1367, 1489).
    elements = ET.SubElement(diagram, "elements")
    conductors = ET.SubElement(diagram, "conductors")
    # A bottom terminal (y=20) -> (200, 220); B top terminal (y=-20) -> (200, 300)
    elements.append(element_instance(a, 200, 200, "-B1"))
    elements.append(element_instance(b, 200, 320, "-B2"))
    conductors.append(conductor(a, TERM_2, b, TERM_1))

    collection = ET.SubElement(project, "collection")
    imp = ET.SubElement(collection, "category", {"name": "import"})
    holder = ET.SubElement(imp, "element", {"name": "cpi.elmt"})
    holder.append(ET.fromstring(ELMT_SRC.read_text(encoding="utf-8")))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree := ET.ElementTree(project))
    tree.write(OUT, encoding="utf-8", xml_declaration=True)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
