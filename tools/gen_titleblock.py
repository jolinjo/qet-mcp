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

標題語意(ISO 7200 主標題 + 補充標題):圖名 = %{projecttitle}(專案標題,
全專案每頁一致);補充圖名 = %{title}(每頁自己的標題)。兩者皆 QET 內建。

Variables — built-ins: %{projecttitle} %{title} %{author} %{date} %{indexrev}
%{folio}; custom via diagram <properties>: %{techref} %{checked-by}
%{approved-by} %{doc-type} %{doc-status} %{doc-id} %{remarks} %{rev-desc}
%{rev-by} %{rev-appd}.
"""
import base64
import xml.etree.ElementTree as ET
from pathlib import Path

NAME = "huchen_iso7200_a3"
ROOT_DIR = Path(__file__).resolve().parents[1]
OUT = ROOT_DIR / "data" / "titleblocks" / f"{NAME}.titleblock"
# 同步安裝到 QET 的「公司圖框」集合,讓 GUI 手動繪圖也能選到同一設計;
# 內部名 = 檔名 = QET 清單顯示名。以後改設計重跑本腳本即可更新這裡。
COMPANY_TB_DIR = (Path.home() / "Library/Application Support/QElectroTech"
                  "/QElectroTech/titleblocks-company")
COMPANY_NAME = "虎氶科技-A3-橫式"
# 法定所有者格放一張含 logo + 公司名的圖片(QET 一格只能圖或字,無法
# 圖字並存;QtSvg 又不支援 data-URI image / CJK text,故用單張點陣圖)。
# huchen_logo.png 由 docs/logo.png(公司完整商標)置中補透明邊至格子比例
# (240:64=3.75:1)而成:QET 會把圖拉滿格子,先補到相同比例才不會變形,
# 且四周留白 → 視覺置中。要換 logo 就更新 docs/logo.png 後重跑本腳本。
LOGO_FILE = ROOT_DIR / "data" / "logos" / "huchen_logo.png"
LOGO_NAME = "huchen_logo"

# 左區修訂記錄表 6 欄:版次40|日期50|座標50|修改內容r100%(吃掉剩餘寬)
# |修改80|核准80。右側 8 個欄位一律 120px(上下兩層共用格線)。
COLS = "40;50;50;r100%;80;80;" + ";".join(["120"] * 8)
REV_ROWS = 6   # 修訂記錄表的資料列數(版次 A~F)
# 列高 16px:上層 48px(標籤16+值32)+ 下層 64px = 112px
# = 表頭+6 列修訂記錄(7 x 16)
ROWS = ";".join(["16"] * 7)   # 7 x 16 px = 112 px

LBL = 8   # label font


LBL_BG = "#d9d9d9"     # 欄位標籤底色(淺灰)


def field(row, col, rowspan, colspan, text, fontsize=10, align="center",
          valign="center", name="", bgcolor=""):
    return (row, col, rowspan, colspan, text, fontsize, align, valign,
            name, bgcolor)


CELLS = [
    # ── 左區:修訂記錄表(表頭 + 6 資料列),col 0-5 ──────────────
    # 每列綁「不同」變數 rev{n}-*,可累積完整修訂歷史(而非只顯示當前
    # 版次的單一組值);位置欄記錄本次修改在圖面的座標/區域。
    field(0, 0, 1, 1, "版次 Rev.", LBL, bgcolor=LBL_BG),
    field(0, 1, 1, 1, "日期 Date", LBL, bgcolor=LBL_BG),
    field(0, 2, 1, 1, "座標 Coord.", LBL, bgcolor=LBL_BG),
    field(0, 3, 1, 1, "修改內容 Description of revision", LBL, bgcolor=LBL_BG),
    field(0, 4, 1, 1, "修改 By", LBL, bgcolor=LBL_BG),
    field(0, 5, 1, 1, "核准 Appd", LBL, bgcolor=LBL_BG),
    *[f for n in range(1, REV_ROWS + 1) for f in (
        field(n, 0, 1, 1, f"%{{rev{n}-idx}}", 8),
        field(n, 1, 1, 1, f"%{{rev{n}-date}}", 8),
        field(n, 2, 1, 1, f"%{{rev{n}-zone}}", 8),
        field(n, 3, 1, 1, f"%{{rev{n}-desc}}", 8, "left"),
        field(n, 4, 1, 1, f"%{{rev{n}-by}}", 8),
        field(n, 5, 1, 1, f"%{{rev{n}-appd}}", 8))],

    # ── 上層 8 欄位(每欄 120px),col 6-13 ─────────────────────
    field(0, 6, 1, 1, "修訂索引 Revision index", LBL, "center", bgcolor=LBL_BG),
    field(0, 7, 1, 1, "文件類別 Document type", LBL, "center", bgcolor=LBL_BG),
    field(0, 8, 1, 1, "技術參考 Technical reference", LBL, "center", bgcolor=LBL_BG),
    field(0, 9, 1, 1, "繪製 Created by", LBL, "center", bgcolor=LBL_BG),
    field(0, 10, 1, 1, "審核 Checked by", LBL, "center", bgcolor=LBL_BG),
    field(0, 11, 1, 1, "核准 Approved by", LBL, "center", bgcolor=LBL_BG),
    field(0, 12, 1, 1, "文件狀態 Document status", LBL, "center", bgcolor=LBL_BG),
    field(0, 13, 1, 1, "發行日期 Date of issue *", LBL, "center", bgcolor=LBL_BG),
    field(1, 6, 2, 1, "%{indexrev}", 10),
    field(1, 7, 2, 1, "%{doc-type}", 10),
    field(1, 8, 2, 1, "%{techref}", 10),
    field(1, 9, 2, 1, "%{author}", 10, "center", "center", "author"),
    field(1, 10, 2, 1, "%{checked-by}", 10),
    field(1, 11, 2, 1, "%{approved-by}", 10),
    field(1, 12, 2, 1, "%{doc-status}", 10),
    field(1, 13, 2, 1, "%{date}", 10, "center", "center", "date"),

    # ── 下層,col 6-13 ────────────────────────────────────────
    field(3, 8, 1, 2, "文件識別號 Identification number *", LBL, "center", bgcolor=LBL_BG),
    field(3, 10, 1, 2, "圖名 Title", LBL, "center", bgcolor=LBL_BG),
    field(3, 12, 1, 1, "圖幅 Size", LBL, "center", bgcolor=LBL_BG),
    field(3, 13, 1, 1, "頁次 Sheet *", LBL, "center", bgcolor=LBL_BG),
    # 法定所有者:無標題列,單一大格(跨兩欄 240px × 4 列高),放公司商標
    field(3, 6, 4, 2, f"LOGO:{LOGO_NAME}"),
    field(4, 8, 3, 2, "%{doc-id}", 11),
    field(4, 10, 1, 2, "%{projecttitle}", 10, "center", "center", "projecttitle"),
    field(4, 12, 1, 1, "A3", 10),
    field(4, 13, 1, 1, "%{folio}", 10, "center", "center", "folio"),
    field(5, 10, 1, 2, "補充圖名 Supplementary title", LBL, "center", bgcolor=LBL_BG),
    field(6, 10, 1, 2, "%{title}", 10, "center", "center", "title"),
    field(5, 12, 1, 2, "備註 Remarks", LBL, "center", bgcolor=LBL_BG),
    field(6, 12, 1, 2, "%{remarks}", 10),
]


def build_tree(template_name: str) -> ET.Element:
    root = ET.Element("titleblocktemplate", {"name": template_name})
    ET.SubElement(root, "information").text = (
        "Huchen ISO 7200 A3 full-width title block, generated from "
        "docs/ISO7200_A3_圖框標題欄範本_4.xlsx by tools/gen_titleblock.py")
    logos = ET.SubElement(root, "logos")
    logo = ET.SubElement(logos, "logo", {
        "name": LOGO_NAME, "type": "png", "storage": "base64"})
    logo.text = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    grid = ET.SubElement(root, "grid", {"cols": COLS, "rows": ROWS})

    for (row, col, rowspan, colspan, text, fontsize, align, valign,
         name, bgcolor) in CELLS:
        if text.startswith("LOGO:"):
            f = ET.SubElement(grid, "logo", {
                "row": str(row), "col": str(col),
                "resource": text[len("LOGO:"):],
            })
        else:
            f = ET.SubElement(grid, "field", {
                "row": str(row), "col": str(col),
                "fontsize": str(fontsize), "align": align, "valign": valign,
                "displaylabel": "false", "hadjust": "true", "name": name,
            })
        if bgcolor:
            f.set("bgcolor", bgcolor)
        # QET span semantics: number of EXTRA cells covered
        if rowspan > 1:
            f.set("rowspan", str(rowspan - 1))
        if colspan > 1:
            f.set("colspan", str(colspan - 1))
        if f.tag == "logo":
            continue
        value = ET.SubElement(f, "value")
        ET.SubElement(value, "translation", {"lang": "en"}).text = text
        label = ET.SubElement(f, "label")
        ET.SubElement(label, "translation", {"lang": "en"}).text = ""
    return root


def write_tree(root: ET.Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree := ET.ElementTree(root))
    tree.write(path, encoding="utf-8", xml_declaration=False)
    print(f"wrote {path}")


def main() -> None:
    # tracked repo copy (used by the MCP qet_apply_titleblock tool)
    write_tree(build_tree(NAME), OUT)
    # company-collection copy so it shows under QET's「公司圖框」
    if COMPANY_TB_DIR.exists():
        write_tree(build_tree(COMPANY_NAME),
                   COMPANY_TB_DIR / f"{COMPANY_NAME}.titleblock")


if __name__ == "__main__":
    main()
