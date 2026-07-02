#!/usr/bin/env python3
"""Generate the Huchen ISO 7200 A3 title block template for QET.

Implements the full-width bottom-band spec from docs/
ISO7200_A3_圖框標題欄範本_4.xlsx sheet「A3圖框-全寬底欄」(spec text in
its r64 note, dimensions in px at 4 px/mm):

- A3 inner width 400 mm = 1600 px; band height 240 px, two 120 px layers.
- Left: revision table 520 px spanning full height —
  版次80|日期120|修改內容160(flex)|修改80|核准80, header 7pt/entries 8pt,
  row height 30 px (header + 7 entries).
- Upper layer 1080 px: 修訂索引120|文件類別120|技術參考160|繪製160|
  審核120|核准120|文件狀態160|發行日期120 — labels 7pt, values 10pt.
- Lower layer 1080 px: 法定所有者320(14pt,h120)|文件識別號240(11pt,h120)|
  圖名280(10pt,h60)+補充圖名280(10pt,h60)|頁次120+圖幅120(10pt,h60)|
  備註240(10pt,h60).

Variables — built-ins: %{author} %{date} %{title} %{indexrev} %{folio};
custom via diagram <properties>: %{techref} %{checked-by} %{approved-by}
%{doc-type} %{doc-status} %{subtitle} %{doc-id} %{remarks} %{rev-desc}
%{rev-by} %{rev-appd}.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

NAME = "huchen_iso7200_a3"
OUT = Path(__file__).resolve().parents[1] / "data" / "titleblocks" / f"{NAME}.titleblock"

# 右側 8 個欄位一律 120px(上下兩層共用同一組 120px 格線,必然對齊);
# 左區 版次80|日期120|修改內容r100%(吃掉所有剩餘寬)|修改80|核准80
COLS = "80;120;r100%;80;80;" + ";".join(["120"] * 8)
# 列高 20px:上層 60px(標籤20+值40)+ 下層 80px = 140px
# = 表頭+6 列修訂記錄(7 x 20)
ROWS = ";".join(["20"] * 7)   # 7 x 20 px = 140 px

LBL = 7   # label font (spec: 標籤 7 pt)


def field(row, col, rowspan, colspan, text, fontsize=10, align="center",
          valign="center", name=""):
    return (row, col, rowspan, colspan, text, fontsize, align, valign, name)


CELLS = [
    # ── 左區:修訂記錄欄 520px,跨全高(表頭 + 7 列)──────────
    field(0, 0, 1, 1, "版次 Rev.", LBL),
    field(0, 1, 1, 1, "日期 Date", LBL),
    field(0, 2, 1, 1, "修改內容 Description of revision", LBL),
    field(0, 3, 1, 1, "修改 By", LBL),
    field(0, 4, 1, 1, "核准 Appd", LBL),
    field(1, 0, 1, 1, "%{indexrev}", 8),
    field(1, 1, 1, 1, "%{date}", 8),
    field(1, 2, 1, 1, "%{rev-desc}", 8, "left"),
    field(1, 3, 1, 1, "%{rev-by}", 8),
    field(1, 4, 1, 1, "%{rev-appd}", 8),
    *[field(r, c, 1, 1, "", 8) for r in range(2, 7) for c in range(5)],

    # ── 上層 960px:8 個欄位,每欄 120px(標籤 20 + 值 40)──────
    field(0, 5, 1, 1, "修訂索引 Revision index", LBL, "left"),
    field(0, 6, 1, 1, "文件類別 Document type", LBL, "left"),
    field(0, 7, 1, 1, "技術參考 Technical reference", LBL, "left"),
    field(0, 8, 1, 1, "繪製 Created by", LBL, "left"),
    field(0, 9, 1, 1, "審核 Checked by", LBL, "left"),
    field(0, 10, 1, 1, "核准 Approved by", LBL, "left"),
    field(0, 11, 1, 1, "文件狀態 Document status", LBL, "left"),
    field(0, 12, 1, 1, "發行日期 Date of issue *", LBL, "left"),
    field(1, 5, 2, 1, "%{indexrev}", 10),
    field(1, 6, 2, 1, "%{doc-type}", 10),
    field(1, 7, 2, 1, "%{techref}", 10),
    field(1, 8, 2, 1, "%{author}", 10, "center", "center", "author"),
    field(1, 9, 2, 1, "%{checked-by}", 10),
    field(1, 10, 2, 1, "%{approved-by}", 10),
    field(1, 11, 2, 1, "%{doc-status}", 10),
    field(1, 12, 2, 1, "%{date}", 10, "center", "center", "date"),

    # ── 下層 960px:240|240|240|120|120(同一組 120px 格線)────
    field(3, 5, 1, 2, "法定所有者 Legal owner *", LBL, "left"),
    field(3, 7, 1, 2, "文件識別號 Identification number *", LBL, "left"),
    field(3, 9, 1, 2, "圖名 Title", LBL, "left"),
    field(3, 11, 1, 1, "頁次 Sheet *", LBL, "left"),
    field(3, 12, 1, 1, "圖幅 Size", LBL, "left"),
    field(4, 5, 3, 2, "虎承科技 Huchen Technology", 14),
    field(4, 7, 3, 2, "%{doc-id}", 11),
    field(4, 9, 1, 2, "%{title}", 10, "center", "center", "title"),
    field(4, 11, 1, 1, "%{folio}", 10, "center", "center", "folio"),
    field(4, 12, 1, 1, "A3", 10),
    field(5, 9, 1, 2, "補充圖名 Supplementary title", LBL, "left"),
    field(6, 9, 1, 2, "%{subtitle}", 10),
    field(5, 11, 1, 2, "備註 Remarks", LBL, "left"),
    field(6, 11, 1, 2, "%{remarks}", 10),
]


def main() -> None:
    root = ET.Element("titleblocktemplate", {"name": NAME})
    ET.SubElement(root, "information").text = (
        "Huchen ISO 7200 A3 full-width title block, generated from "
        "docs/ISO7200_A3_圖框標題欄範本_4.xlsx by tools/gen_titleblock.py")
    ET.SubElement(root, "logos")
    grid = ET.SubElement(root, "grid", {"cols": COLS, "rows": ROWS})

    for row, col, rowspan, colspan, text, fontsize, align, valign, name in CELLS:
        f = ET.SubElement(grid, "field", {
            "row": str(row), "col": str(col),
            "fontsize": str(fontsize), "align": align, "valign": valign,
            "displaylabel": "false", "hadjust": "true", "name": name,
        })
        # QET span semantics: number of EXTRA cells covered
        if rowspan > 1:
            f.set("rowspan", str(rowspan - 1))
        if colspan > 1:
            f.set("colspan", str(colspan - 1))
        value = ET.SubElement(f, "value")
        ET.SubElement(value, "translation", {"lang": "en"}).text = text
        label = ET.SubElement(f, "label")
        ET.SubElement(label, "translation", {"lang": "en"}).text = ""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree := ET.ElementTree(root))
    tree.write(OUT, encoding="utf-8", xml_declaration=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
