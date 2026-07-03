"""End-to-end tests for the MCP tool layer (server.py) — pure-Python tools.

Covers project build → edit → IEC audit → BOM → titleblock. Tools that
shell out to the QET binary (render/validate/netlist) are exercised
separately only if the binary exists.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import server  # noqa: E402

QET_REPO = Path(os.environ.get("QET_REPO", REPO.parent / "QET-qeletrotech"))
E = "10_electric/10_allpole/"
CPI = "10_electric/99_miscellaneous_unsorted/cpi.elmt"
COIL = E + "310_relays_contactors_contacts/01_coils/bobine3.elmt"
PB = E + "380_signaling_operating/20_push_buttons/poussoir.elmt"


@unittest.skipUnless(QET_REPO.exists(), "needs QET element library")
class ToolChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.qet"
        server.tool_new_project(str(self.path), title="test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_place_connect_and_content(self):
        server.tool_place_element(CPI, 200, 200, label="-B1")
        server.tool_place_element(CPI, 200, 320, label="-B2")
        server.tool_draw_conductor("-B1", "2", "-B2", "1", num="101")
        c = server.tool_list_content()
        self.assertEqual(len(c["elements"]), 2)
        self.assertEqual(len(c["conductors"]), 1)
        self.assertEqual(c["conductors"][0]["num"], "101")

    def test_edit_move_rotate_relabel_delete(self):
        server.tool_place_element(CPI, 200, 200, label="-B1")
        server.tool_place_element(CPI, 200, 320, label="-B2")
        server.tool_draw_conductor("-B1", "2", "-B2", "1", num="1")
        server.tool_set_label("-B1", "-B9")
        server.tool_move_element("-B9", 300, 300)
        server.tool_rotate_element("-B9", 1)
        c = server.tool_list_content()
        b9 = next(e for e in c["elements"] if e["label"] == "-B9")
        self.assertEqual((b9["x"], b9["y"], b9["orientation"]), (300, 300, 1))
        # deleting an element drops its conductor too
        d = server.tool_delete_element("-B9")
        self.assertEqual(d["conductors_removed"], 1)
        self.assertEqual(len(server.tool_list_content()["conductors"]), 0)

    def test_iec_flags_bad_designations(self):
        server.tool_place_element(CPI, 200, 200, label="-MC1")   # JIS abbrev
        server.tool_place_element(CPI, 200, 320, label="")       # missing
        r = server.tool_check_iec_compliance()
        rules = {f["rule"] for f in r["findings"] if f["level"] == "MUST"}
        self.assertIn("81346-abbrev", rules)
        self.assertIn("81346-label", rules)
        self.assertFalse(r["compliant"])

    def test_iec_shared_designation_is_not_error(self):
        # a device's parts sharing -KM1 (coil + contact) must NOT be flagged
        server.tool_place_element(COIL, 200, 200, label="-KM1")
        server.tool_place_element(PB, 300, 200, label="-KM1")
        r = server.tool_check_iec_compliance()
        self.assertNotIn("81346-duplicate",
                         {f["rule"] for f in r["findings"]})

    def test_bom_groups_by_designation(self):
        server.tool_place_element(COIL, 200, 200, label="-KM1")
        server.tool_place_element(PB, 300, 200, label="-KM1")   # same device
        server.tool_place_element(CPI, 400, 200, label="-B1")
        r = server.tool_generate_bom()
        self.assertEqual(r["devices"], 2)   # -KM1 (2 parts) + -B1
        km1 = next(b for b in r["bom"] if b["designation"] == "-KM1")
        self.assertEqual(km1["qty"], 1)
        self.assertEqual(len(km1["parts"]), 2)

    def test_auto_designate_conservative(self):
        server.tool_place_element(CPI, 200, 200, label="-B1")
        server.tool_place_element(CPI, 300, 200, label="", prefix="B") \
            if False else None
        # place an un-labelled element via qet_xml prefix
        from qet_xml import QetProject
        p = QetProject.open(self.path)
        p.diagram(0).place_element(QET_REPO / "elements" / CPI,
                                   x=300, y=200, label="", prefix="B")
        p.save(self.path)
        server.tool_open_project(str(self.path))
        r = server.tool_auto_designate()
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["assigned"][0]["label"], "-B2")  # continues past B1

    def test_set_and_delete_wire(self):
        server.tool_place_element(CPI, 200, 200, label="-B1")
        server.tool_place_element(CPI, 200, 320, label="-B2")
        server.tool_draw_conductor("-B1", "2", "-B2", "1", num="1")
        server.tool_set_wire("-B1", "2", "-B2", "1", num="101",
                             color="#FF0000")
        c = server.tool_list_content()["conductors"][0]
        self.assertEqual(c["num"], "101")
        with self.assertRaises(KeyError):     # nonexistent conductor
            server.tool_set_wire("-B1", "1", "-B2", "2")
        server.tool_delete_wire("-B1", "2", "-B2", "1")
        self.assertEqual(len(server.tool_list_content()["conductors"]), 0)

    def test_auto_xref_links_contacts_to_coil(self):
        AUX = (E + "310_relays_contactors_contacts/"
               "02_contacts_cross_referencing/01_auxiliary_contacts/"
               "con_simple.elmt")
        server.tool_place_element(COIL, 200, 200, label="-KM1")  # master coil
        server.tool_place_element(AUX, 300, 200, label="-KM1")   # slave contact
        server.tool_place_element(AUX, 400, 200, label="-KM2")   # other device
        r = server.tool_auto_xref()
        self.assertEqual(r["linked"], 1)   # only -KM1 has coil+contact
        from qet_xml import QetProject
        p = QetProject.open(self.path)
        els = p.diagram(0).elements
        coil = next(e for e in els if e.definition.link_type == "master")
        contact = next(e for e in els if e.definition.link_type == "slave"
                       and e.label == "-KM1")
        self.assertIn(coil.uuid, contact.links)

    def test_titleblock_and_revisions(self):
        server.tool_place_element(CPI, 200, 200, label="-B1")
        server.tool_apply_titleblock(title="T", doc_id="HC-1", author="J")
        server.tool_set_revisions([
            {"idx": "A", "date": "2026/7/2", "desc": "first", "by": "J"}])
        from qet_xml import QetProject
        p = QetProject.open(self.path)
        self.assertIn("huchen_iso7200_a3", p.titleblock_templates)
        self.assertEqual(p.diagram(0).attrs.get("titleblocktemplate"),
                         "huchen_iso7200_a3")
        self.assertEqual(p.diagram(0).properties.get("rev1-idx"), "A")
        # unused rows blanked, not left as %{rev3-idx}
        self.assertEqual(p.diagram(0).properties.get("rev3-idx"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
