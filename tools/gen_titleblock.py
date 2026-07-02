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

# rev table: 版次12mm 日期25mm 內容=flex 修改16mm 核准17mm
# title block (180mm): boundaries at 0,49,65,98,115,139,148,180 mm
COLS = "48;100;r100%;64;68;196;64;132;68;96;36;128"
# label rows 12px (3mm) / value rows 20px (5mm) / title row 28px (7mm);
# total 200px = 50mm — mirrors the xlsx (label rows short, values tall)
ROWS = "12;20;12;20;12;28;12;20;12;20;12;20"

LBL, VAL = 5, 9   # font sizes


def field(row, col, rowspan, colspan, text, fontsize=VAL, align="center",
          valign="center", name=""):
    return (row, col, rowspan, colspan, text, fontsize, align, valign, name)


CELLS = [
    # ── 修訂記錄表(左,cols 0-4;每格跨 2 列 = 標籤列+值列)────
    field(0, 0, 2, 1, "版次 Rev.", LBL),
    field(0, 1, 2, 1, "日期 Date", LBL),
    field(0, 2, 2, 1, "修改內容 Description of revision", LBL),
    field(0, 3, 2, 1, "修改 By", LBL),
    field(0, 4, 2, 1, "核准 Appd", LBL),
    # 第一列修訂 = 目前版次(變數);其餘留白待手填
    field(2, 0, 2, 1, "%{indexrev}", 8),
    field(2, 1, 2, 1, "%{date}", 8),
    field(2, 2, 2, 1, "%{rev-desc}", 8, "left"),
    field(2, 3, 2, 1, "%{rev-by}", 8),
    field(2, 4, 2, 1, "%{rev-appd}", 8),
    *[field(r, c, 2, 1, "", 8)
      for r in (4, 6, 8, 10) for c in range(5)],

    # ── ISO 7200 標題欄(右,cols 5-11)────────────────────────
    # 帶 1:簽核(49|49|41|41 mm)
    field(0, 5, 1, 1, "技術參考 Technical reference", LBL, "left"),
    field(0, 6, 1, 2, "繪製 Created by", LBL, "left"),
    field(0, 8, 1, 2, "審核 Checked by", LBL, "left"),
    field(0, 10, 1, 2, "核准 Approved by", LBL, "left"),
    field(1, 5, 1, 1, "%{techref}"),
    field(1, 6, 1, 2, "%{author}", VAL, "center", "center", "author"),
    field(1, 8, 1, 2, "%{checked-by}"),
    field(1, 10, 1, 2, "%{approved-by}"),
    # 帶 2:文件屬性
    field(2, 5, 1, 1, "文件類別 Document type", LBL, "left"),
    field(2, 6, 1, 2, "文件狀態 Document status", LBL, "left"),
    field(2, 8, 1, 2, "發行日期 Date of issue *", LBL, "left"),
    field(2, 10, 1, 2, "修訂索引 Revision index", LBL, "left"),
    field(3, 5, 1, 1, "%{doc-type}"),
    field(3, 6, 1, 2, "%{doc-status}"),
    field(3, 8, 1, 2, "%{date}", VAL, "center", "center", "date"),
    field(3, 10, 1, 2, "%{indexrev}"),
    # 帶 3:所有者(65)+ 圖名(115);圖名列特高(28px)
    field(4, 5, 1, 2, "法定所有者 Legal owner *", LBL, "left"),
    field(4, 7, 1, 5, "圖名 Title", LBL, "left"),
    field(5, 5, 3, 2, "虎承科技 Huchen Technology", 11),
    field(5, 7, 1, 5, "%{title}", 12, "center", "center", "title"),
    field(6, 7, 1, 5, "補充圖名 Supplementary title", LBL, "left"),
    field(7, 7, 1, 5, "%{subtitle}"),
    # 帶 4:識別號(115)+ 頁次(33)+ 圖幅(32)+ 備註
    field(8, 5, 1, 4, "文件識別號 Identification number *", LBL, "left"),
    field(8, 9, 1, 2, "頁次 Sheet *", LBL, "left"),
    field(8, 11, 1, 1, "圖幅 Size", LBL, "left"),
    field(9, 5, 3, 4, "%{doc-id}", 11),
    field(9, 9, 1, 2, "%{folio}", VAL, "center", "center", "folio"),
    field(9, 11, 1, 1, "A3"),
    field(10, 9, 1, 3, "備註 Remarks", LBL, "left"),
    field(11, 9, 1, 3, "%{remarks}", 8),
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
