"""M1 round-trip tests against the QET-saved golden file (see M0 docs).

Semantic-core comparison only: attribute order, derived attributes
(element1_label, terminalname1, ...) and default sections added by QET
are non-semantic per docs/qet-xml-schema.md §6.
"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from qet_xml import ElementDefinition, QetProject  # noqa: E402

GOLDEN = REPO / "skeleton" / "golden" / "min_qet_saved.qet"
QET_REPO = Path(os.environ.get(
    "QET_REPO", REPO.parent / "QET-qeletrotech"))
CPI = QET_REPO / "elements/10_electric/99_miscellaneous_unsorted/cpi.elmt"

CPI_TERM_1 = "{fdc849e2-24c2-4da0-8749-c89aab1818c9}"  # name="1", top
CPI_TERM_2 = "{b94d18f8-9ad7-4c6a-a10c-1edd09d97b4f}"  # name="2", bottom


def snapshot(prj: QetProject):
    """Order-independent semantic core of a project."""
    d = prj.diagram(0)
    return {
        "elements": {(e.uuid, e.definition.embed_path, e.x, e.y,
                      e.orientation, e.label) for e in d.elements},
        "conductors": {(c.element1, c.terminal1, c.element2, c.terminal2,
                        c.props.get("num", "")) for c in d.conductors},
        "collection": {path: {t.uuid for t in defn.terminals}
                       for path, defn in prj.collection.items()},
    }


class GoldenRoundTrip(unittest.TestCase):
    def test_open_save_reopen_preserves_semantics(self):
        original = QetProject.open(GOLDEN)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "roundtrip.qet"
            original.save(out)
            reopened = QetProject.open(out)
        self.assertEqual(snapshot(original), snapshot(reopened))

    def test_golden_content_is_what_m0_established(self):
        prj = QetProject.open(GOLDEN)
        snap = snapshot(prj)
        self.assertEqual(len(snap["elements"]), 2)
        self.assertEqual(len(snap["conductors"]), 1)
        (c,) = snap["conductors"]
        self.assertEqual(c[4], "101")                       # wire number kept
        self.assertEqual({c[1], c[3]}, {CPI_TERM_1, CPI_TERM_2})
        self.assertIn("import/cpi.elmt", snap["collection"])


class BuildFromScratch(unittest.TestCase):
    def build(self) -> QetProject:
        prj = QetProject.new("api test")
        d = prj.diagram(0)
        b1 = d.place_element(CPI, x=200, y=200, label="-B1", prefix="B")
        b2 = d.place_element(CPI, x=200, y=320, label="-B2", prefix="B")
        d.connect(b1.terminal("2"), b2.terminal("1"), num="101")
        return prj

    def test_dual_key_linking_and_wrappers(self):
        prj = self.build()
        root = prj.to_xml()
        diagram = root.find("diagram")
        self.assertIsNotNone(diagram.find("elements"))      # wrappers required
        self.assertIsNotNone(diagram.find("conductors"))    # (diagram.cpp:1367)
        cond = diagram.find("conductors/conductor")
        self.assertEqual(cond.get("terminal1"), CPI_TERM_2)
        self.assertEqual(cond.get("terminal2"), CPI_TERM_1)
        insts = {e.get("uuid") for e in diagram.iter("element")}
        self.assertIn(cond.get("element1"), insts)
        self.assertIn(cond.get("element2"), insts)
        # no <segment>: QET autoroutes on load (conductor.cpp:1147)
        self.assertIsNone(cond.find("segment"))

    def test_collection_embedding_and_dedup(self):
        prj = self.build()
        self.assertEqual(list(prj.collection), ["import/cpi.elmt"])  # dedup
        holder = prj.to_xml().find("collection/category[@name='import']"
                                   "/element[@name='cpi.elmt']/definition")
        self.assertIsNotNone(holder)

    def test_save_reopen_matches(self):
        prj = self.build()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "api.qet"
            prj.save(out)
            self.assertEqual(snapshot(prj), snapshot(QetProject.open(out)))

    def test_terminal_lookup(self):
        defn = ElementDefinition.load(CPI)
        self.assertEqual(defn.terminal("1").uuid, CPI_TERM_1)
        self.assertEqual(defn.terminal(0).uuid,
                         defn.terminals[0].uuid)
        with self.assertRaises(KeyError):
            defn.terminal("nope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
