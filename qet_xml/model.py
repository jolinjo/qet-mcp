"""qet-xml — pure-Python object model for QElectroTech .qet project files.

Grounded in docs/qet-xml-schema.md (M0). Key format facts relied upon:
- <element>/<conductor> must live inside <elements>/<conductors> wrappers.
- Conductors link via dual key: element instance uuid + definition-level
  terminal uuid. <segment> children are omitted -> QET autoroutes on load.
- Element definitions are embedded in the project <collection> under
  "import/", making projects self-contained (type="embed://import/...").
"""
from __future__ import annotations

import copy
import uuid as _uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

QET_VERSION = "0.100.0"


def _new_uuid() -> str:
    return "{" + str(_uuid.uuid4()) + "}"


# --------------------------------------------------------------------------- #
# Definitions (element library side)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Terminal:
    """Definition-level terminal (shared by every instance of the element)."""
    uuid: str
    name: str
    x: float
    y: float
    orientation: str  # n / s / e / w


class ElementDefinition:
    """An .elmt definition, kept as raw XML plus parsed terminals."""

    def __init__(self, embed_path: str, dom: ET.Element):
        if dom.tag != "definition":
            raise ValueError(f"not an element definition: <{dom.tag}>")
        self.embed_path = embed_path          # e.g. "import/cpi.elmt"
        self.dom = dom
        self.terminals: list[Terminal] = [
            Terminal(
                uuid=t.get("uuid", ""),
                name=t.get("name", ""),
                x=float(t.get("x", "0")),
                y=float(t.get("y", "0")),
                orientation=t.get("orientation", "n"),
            )
            for t in dom.iter("terminal")
            if t.get("uuid")  # definition-level terminals carry uuids
        ]
        # dynamic text templates (e.g. the label placeholder); QET only
        # renders instance-level <dynamic_texts>, so instances must
        # materialize these (see ElementInstance.to_xml)
        self.dynamic_texts: list[ET.Element] = list(dom.iter("dynamic_text"))

    @classmethod
    def load(cls, path: str | Path, embed_path: str | None = None) -> "ElementDefinition":
        path = Path(path)
        dom = ET.fromstring(path.read_text(encoding="utf-8"))
        return cls(embed_path or f"import/{path.name}", dom)

    def terminal(self, key: str | int) -> Terminal:
        if isinstance(key, int):
            return self.terminals[key]
        for t in self.terminals:
            if t.name == key and t.name:
                return t
        # fallback for unnamed terminals: numeric string = index
        if key.isdigit() and int(key) < len(self.terminals):
            return self.terminals[int(key)]
        raise KeyError(f"no terminal named {key!r} in {self.embed_path} "
                       f"(have: {[t.name for t in self.terminals]})")


# --------------------------------------------------------------------------- #
# Diagram content
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class TerminalRef:
    """A connectable endpoint: instance uuid + definition terminal."""
    element_uuid: str
    terminal: Terminal


class ElementInstance:
    def __init__(self, definition: ElementDefinition, x: float, y: float,
                 label: str = "", orientation: int = 0, prefix: str = "",
                 uuid: str | None = None,
                 dynamic_texts_dom: ET.Element | None = None):
        self.definition = definition
        self.uuid = uuid or _new_uuid()
        self.x, self.y = x, y
        self.label = label
        self.orientation = orientation
        self.prefix = prefix
        # raw <dynamic_texts> read from an existing file (preserved verbatim
        # so user-moved texts survive a round-trip); None = generate from
        # the definition's templates
        self.dynamic_texts_dom = dynamic_texts_dom

    def terminal(self, key: str | int) -> TerminalRef:
        return TerminalRef(self.uuid, self.definition.terminal(key))

    def _materialize_dynamic_texts(self) -> ET.Element:
        """Instantiate the definition's dynamic_text templates.

        QET only renders instance-level <dynamic_texts>; without this the
        label would be stored but never displayed.
        """
        wrapper = ET.Element("dynamic_texts")
        for template in self.definition.dynamic_texts:
            t = ET.SubElement(wrapper, "dynamic_elmt_text",
                              dict(template.attrib))
            t.set("uuid", _new_uuid())
            info_name = template.findtext("info_name", "")
            text = ET.SubElement(t, "text")
            text.text = self.label if info_name == "label" else \
                template.findtext("text", "")
            if info_name:
                ET.SubElement(t, "info_name").text = info_name
        return wrapper

    def to_xml(self) -> ET.Element:
        e = ET.Element("element", {
            "uuid": self.uuid,
            "type": f"embed://{self.definition.embed_path}",
            "x": _num(self.x), "y": _num(self.y),
            "orientation": str(self.orientation), "z": "10",
            "prefix": self.prefix, "freezeLabel": "false",
        })
        infos = ET.SubElement(e, "elementInformations")
        if self.label:
            info = ET.SubElement(infos, "elementInformation",
                                 {"show": "1", "name": "label"})
            info.text = self.label
        if self.dynamic_texts_dom is not None:
            e.append(copy.deepcopy(self.dynamic_texts_dom))
        else:
            e.append(self._materialize_dynamic_texts())
        return e


class Conductor:
    #: attributes QET always writes; provided so our output opens cleanly
    DEFAULTS = {
        "type": "multi", "num": "", "color": "#000000", "condsize": "1",
        "displaytext": "1", "x": "0", "y": "0", "freezeLabel": "false",
    }

    def __init__(self, t1: TerminalRef, t2: TerminalRef,
                 path: "list[tuple[str, float]] | None" = None,
                 **props: str):
        self.element1, self.terminal1 = t1.element_uuid, t1.terminal.uuid
        self.element2, self.terminal2 = t2.element_uuid, t2.terminal.uuid
        # optional explicit manhattan route from t1 to t2:
        # [("v", 20), ("h", -130), ("v", 39)]  (must sum to the terminal
        # delta within 1px, else QET falls back to autorouting)
        self.path = path
        self.props = {**self.DEFAULTS, **{k: str(v) for k, v in props.items()}}

    def to_xml(self) -> ET.Element:
        # Without explicit path we emit NO <segment> children: QET
        # autoroutes on load (conductor.cpp:1147).
        e = ET.Element("conductor", {
            "element1": self.element1, "terminal1": self.terminal1,
            "element2": self.element2, "terminal2": self.terminal2,
            **self.props,
        })
        for orient, length in (self.path or []):
            ET.SubElement(e, "segment", {
                "orientation": ("horizontal" if orient == "h"
                                else "vertical"),
                "length": _num(length),
            })
        return e


class Diagram:
    ATTR_DEFAULTS = {
        "cols": "17", "colsize": "60", "rows": "8", "rowsize": "80",
        "author": "qet-mcp", "date": "null", "order": "1",
    }

    def __init__(self, project: "QetProject", title: str = "",
                 attrs: dict[str, str] | None = None):
        self.project = project
        self.attrs = {**self.ATTR_DEFAULTS, **(attrs or {}), "title": title}
        self.elements: list[ElementInstance] = []
        self.conductors: list[Conductor] = []

    # -- authoring API ------------------------------------------------------
    def place_element(self, elmt: str | Path | ElementDefinition, x: float,
                      y: float, label: str = "", orientation: int = 0,
                      prefix: str = "") -> ElementInstance:
        definition = (elmt if isinstance(elmt, ElementDefinition)
                      else ElementDefinition.load(elmt))
        definition = self.project.embed(definition)
        inst = ElementInstance(definition, x, y, label, orientation, prefix)
        self.elements.append(inst)
        return inst

    def connect(self, t1: TerminalRef, t2: TerminalRef,
                path: "list[tuple[str, float]] | None" = None,
                **props: str) -> Conductor:
        c = Conductor(t1, t2, path=path, **props)
        self.conductors.append(c)
        return c

    # -- serialization ------------------------------------------------------
    def to_xml(self) -> ET.Element:
        d = ET.Element("diagram", self.attrs)
        elements = ET.SubElement(d, "elements")
        for inst in self.elements:
            elements.append(inst.to_xml())
        conductors = ET.SubElement(d, "conductors")
        for c in self.conductors:
            conductors.append(c.to_xml())
        return d


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #

class QetProject:
    def __init__(self, title: str = "", version: str = QET_VERSION):
        self.title = title
        self.version = version
        self.diagrams: list[Diagram] = []
        self.collection: dict[str, ElementDefinition] = {}  # embed_path -> def

    # -- construction -------------------------------------------------------
    @classmethod
    def new(cls, title: str = "") -> "QetProject":
        prj = cls(title)
        prj.add_diagram(title or "folio 1")
        return prj

    def add_diagram(self, title: str = "") -> Diagram:
        d = Diagram(self, title)
        d.attrs["order"] = str(len(self.diagrams) + 1)
        self.diagrams.append(d)
        return d

    def diagram(self, index: int = 0) -> Diagram:
        return self.diagrams[index]

    def embed(self, definition: ElementDefinition) -> ElementDefinition:
        """Register a definition in the embedded collection (dedup by path)."""
        existing = self.collection.get(definition.embed_path)
        if existing is not None:
            return existing
        self.collection[definition.embed_path] = definition
        return definition

    # -- open / save --------------------------------------------------------
    @classmethod
    def open(cls, path: str | Path) -> "QetProject":
        root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
        if root.tag != "project":
            raise ValueError(f"not a QET project: <{root.tag}>")
        prj = cls(root.get("title", ""), root.get("version", QET_VERSION))

        collection = root.find("collection")
        if collection is not None:
            prj._read_collection(collection, prefix="")

        for ddom in root.findall("diagram"):
            prj._read_diagram(ddom)
        return prj

    def _read_collection(self, node: ET.Element, prefix: str) -> None:
        for cat in node.findall("category"):
            self._read_collection(cat, f"{prefix}{cat.get('name', '')}/")
        for holder in node.findall("element"):
            ddom = holder.find("definition")
            if ddom is None:
                continue
            embed_path = f"{prefix}{holder.get('name', '')}"
            self.collection[embed_path] = ElementDefinition(
                embed_path, copy.deepcopy(ddom))

    def _read_diagram(self, ddom: ET.Element) -> None:
        d = Diagram(self, ddom.get("title", ""),
                    {k: v for k, v in ddom.attrib.items() if k != "title"})
        self.diagrams.append(d)

        elements = ddom.find("elements")
        for edom in ([] if elements is None else elements.findall("element")):
            etype = edom.get("type", "")
            embed_path = etype.removeprefix("embed://")
            definition = self.collection.get(embed_path)
            if definition is None:
                continue  # non-embedded or missing definition: skip in M1
            label = ""
            for info in edom.iter("elementInformation"):
                if info.get("name") == "label":
                    label = info.text or ""
            dtexts = edom.find("dynamic_texts")
            d.elements.append(ElementInstance(
                definition,
                x=float(edom.get("x", "0")), y=float(edom.get("y", "0")),
                label=label,
                orientation=int(edom.get("orientation", "0")),
                prefix=edom.get("prefix", ""),
                uuid=edom.get("uuid"),
                dynamic_texts_dom=(copy.deepcopy(dtexts)
                                   if dtexts is not None else None),
            ))

        conductors = ddom.find("conductors")
        for cdom in ([] if conductors is None else conductors.findall("conductor")):
            c = object.__new__(Conductor)
            c.element1 = cdom.get("element1", "")
            c.terminal1 = cdom.get("terminal1", "")
            c.element2 = cdom.get("element2", "")
            c.terminal2 = cdom.get("terminal2", "")
            segs = [("h" if s.get("orientation") == "horizontal" else "v",
                     float(s.get("length", "0")))
                    for s in cdom.findall("segment")]
            c.path = segs or None            # preserve explicit routing
            c.props = {k: v for k, v in cdom.attrib.items()
                       if k not in ("element1", "terminal1",
                                    "element2", "terminal2")}
            d.conductors.append(c)

    def to_xml(self) -> ET.Element:
        root = ET.Element("project", {"title": self.title,
                                      "version": self.version})
        for d in self.diagrams:
            root.append(d.to_xml())

        collection = ET.SubElement(root, "collection")
        for embed_path in sorted(self.collection):
            node = collection
            *dirs, filename = embed_path.split("/")
            for name in dirs:  # build/reuse category chain
                nxt = next((c for c in node.findall("category")
                            if c.get("name") == name), None)
                if nxt is None:
                    nxt = ET.SubElement(node, "category", {"name": name})
                node = nxt
            holder = ET.SubElement(node, "element", {"name": filename})
            holder.append(copy.deepcopy(self.collection[embed_path].dom))
        return root

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        tree = ET.ElementTree(self.to_xml())
        ET.indent(tree)
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)
