#!/usr/bin/env python3
"""Generate the Huchen ISO 7200 A3 title block template for QET.

Layout reproduces docs/ISO7200_A3_圖框標題欄範本_4.xlsx (sheet
「A3圖框-全寬底欄」): revision-history table on the left (flexible
width) + the 180 mm ISO 7200 title block on the right.

Scale: 4 px/mm (matches upstream ISO7200_A4_V1 ~3.92 px/mm).
Grid: 12 columns × 14 rows of 16 px (total height 224 px = 56 mm).

Field variables — built-ins: %{author} %{date} %{title} %{indexrev}
%{folio}; custom (fill in QET titleblock properties dialog or diagram
<properties>): %{techref} %{checked-by} %{approved-by} %{doc-type}
%{doc-status} %{subtitle} %{doc-id} %{remarks} %{rev-desc} %{rev-by}
%{rev-appd}.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

NAME = "huchen_iso7200_a3"
OUT = Path(__file__).resolve().parents[1] / "data" / "titleblocks" / f"{NAME}.titleblock"

# Corner layout (xlsx sheet「A3圖框範本」): everything right-aligned in
# 180 mm; revision table stacked ABOVE the ISO 7200 block. Column 0 is an
# r100% spacer with NO fields -> EmptyCell -> QET draws nothing there.
# Unified 10-column set (mm): 16,33,16,33,17,16,8,9,7,25 (sum 180), i.e.
# boundaries 16,49,65,98,115,131,139,148,155 shared by:
#   rev row: 版次16 | 日期33 | 內容82 | 修改24 | 核准25
#   band1/2: 49 | 49 | 41 | 41      band3: 識別號65 | 圖名115
#   band4:   所有者115 | 頁次33 | 圖幅32
COLS = "r100%;64;132;64;132;68;64;32;36;28;100"
# rev: header 24 + 5 entries x16; block: label 12 / value 20 / title 28
ROWS = "24;16;16;16;16;16;12;20;12;20;12;28;12;20;12;20;12;20"

LBL, VAL = 5, 9   # font sizes


def field(row, col, rowspan, colspan, text, fontsize=VAL, align="center",
          valign="center", name=""):
    return (row, col, rowspan, colspan, text, fontsize, align, valign, name)


CELLS = [
    # ── 左側填充:單一空白格跨全高,畫出邊框讓頁框閉合 ──────────
    # (QET 對 EmptyCell 完全不畫線,folio 渲染也沒有帶外框,
    #  故需以實體空 field 收邊)
    field(0, 0, 18, 1, ""),

    # ── 修訂記錄表(r0 表頭 + r1 現行版次 + r2-r5 留白)────────
    field(0, 1, 1, 1, "版次 Rev.", LBL),
    field(0, 2, 1, 1, "日期 Date", LBL),
    field(0, 3, 1, 4, "修改內容 Description of revision", LBL),
    field(0, 7, 1, 3, "修改 By", LBL),
    field(0, 10, 1, 1, "核准 Appd", LBL),
    field(1, 1, 1, 1, "%{indexrev}", 8),
    field(1, 2, 1, 1, "%{date}", 8),
    field(1, 3, 1, 4, "%{rev-desc}", 8, "left"),
    field(1, 7, 1, 3, "%{rev-by}", 8),
    field(1, 10, 1, 1, "%{rev-appd}", 8),
    *[f for r in (2, 3, 4, 5) for f in (
        field(r, 1, 1, 1, "", 8), field(r, 2, 1, 1, "", 8),
        field(r, 3, 1, 4, "", 8), field(r, 7, 1, 3, "", 8),
        field(r, 10, 1, 1, "", 8))],

    # ── 帶 1:簽核(49|49|41|41 mm)────────────────────────────
    field(6, 1, 1, 2, "技術參考 Technical reference", LBL, "left"),
    field(6, 3, 1, 2, "繪製 Created by", LBL, "left"),
    field(6, 5, 1, 3, "審核 Checked by", LBL, "left"),
    field(6, 8, 1, 3, "核准 Approved by", LBL, "left"),
    field(7, 1, 1, 2, "%{techref}"),
    field(7, 3, 1, 2, "%{author}", VAL, "center", "center", "author"),
    field(7, 5, 1, 3, "%{checked-by}"),
    field(7, 8, 1, 3, "%{approved-by}"),
    # ── 帶 2:文件屬性 ─────────────────────────────────────────
    field(8, 1, 1, 2, "文件類別 Document type", LBL, "left"),
    field(8, 3, 1, 2, "文件狀態 Document status", LBL, "left"),
    field(8, 5, 1, 3, "發行日期 Date of issue *", LBL, "left"),
    field(8, 8, 1, 3, "修訂索引 Revision index", LBL, "left"),
    field(9, 1, 1, 2, "%{doc-type}"),
    field(9, 3, 1, 2, "%{doc-status}"),
    field(9, 5, 1, 3, "%{date}", VAL, "center", "center", "date"),
    field(9, 8, 1, 3, "%{indexrev}"),
    # ── 帶 3:識別號(65,高格)+ 圖名(115)───────────────────
    field(10, 1, 1, 3, "文件識別號 Identification number *", LBL, "left"),
    field(10, 4, 1, 7, "圖名 Title", LBL, "left"),
    field(11, 1, 3, 3, "%{doc-id}", 10),
    field(11, 4, 1, 7, "%{title}", 12, "center", "center", "title"),
    field(12, 4, 1, 7, "補充圖名 Supplementary title", LBL, "left"),
    field(13, 4, 1, 7, "%{subtitle}"),
    # ── 帶 4:所有者(115,高格)+ 頁次(33)+ 圖幅(32)+ 備註 ──
    field(14, 1, 1, 5, "法定所有者 Legal owner *", LBL, "left"),
    field(14, 6, 1, 3, "頁次 Sheet *", LBL, "left"),
    field(14, 9, 1, 2, "圖幅 Size", LBL, "left"),
    field(15, 1, 3, 5, "虎承科技 Huchen Technology", 12),
    field(15, 6, 1, 3, "%{folio}", VAL, "center", "center", "folio"),
    field(15, 9, 1, 2, "A3"),
    field(16, 6, 1, 5, "備註 Remarks", LBL, "left"),
    field(17, 6, 1, 5, "%{remarks}", 8),
]


def main() -> None:
    root = ET.Element("titleblocktemplate", {"name": NAME})
    ET.SubElement(root, "information").text = (
        "Huchen ISO 7200 A3 title block, generated from "
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
        # (titleblocktemplate.cpp:1202 "i <= num_col + col_span")
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
