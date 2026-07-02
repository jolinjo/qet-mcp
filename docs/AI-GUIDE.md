# qet-mcp AI 操作指南

**讀者是 AI(Claude 等 MCP client)。** 開始任何 QET 繪圖工作前先讀完本文,
可避免已知的坑並大幅減少工具往返。人類讀者請看 [README](../README.md)。

> **維護規約**:凡新增/修改工具、驗證新元件、發現新陷阱,**必須同步更新
> 本文件**(以及 README 里程碑、data/aliases.json),不需使用者提醒。

---

> **畫正式電路圖前,必讀
> [QET繪圖規範_IEC_AI執行版.md](QET繪圖規範_IEC_AI執行版.md)**:
> 元件代號(IEC 81346)、導線顏色/線號(IEC 60204-1)、交互參照、
> 安全迴路、文件識別號、圖框規範 —— 公司內規,MUST 級遵守。

## 1. 黃金工作流

```text
qet_list_aliases                    ← 標準元件 90% 在這,零搜尋
   ↓ 缺的才
qet_search_elements("中文即可")      ← 索引化,~20ms,結果直附端子明細
   ↓ 只有 verified:false 或搜尋來的才需要
qet_describe_element                ← 確認端子 index/name/座標
   ↓
qet_new_project / qet_open_project
qet_place_element ×N                ← 座標規則見 §3
qet_draw_conductor ×N               ← 交叉線用 path,見 §4
   ↓
qet_render                          ← 必做!自檢圖面再交付
qet_netlist / qet_validate          ← 用資料驗線,不靠肉眼
```

大型迴路(≥10 元件)可改用 `qet_xml` Python 腳本一次建圖
(`from qet_xml import QetProject`,API 與 MCP 工具一一對應),
再用 `qet_open_project` + `qet_render` 檢視 —— 檔案優先架構,兩者可混用。

## 2. 工具目錄(12 個)

| 工具 | 要點 |
| --- | --- |
| `qet_new_project(path, title)` | 建案並設為當前專案 |
| `qet_open_project(path)` | 開檔;回 folio 摘要 |
| `qet_list_aliases()` | **優先用**。已驗證角色→元件對照,含端子備註 |
| `qet_search_elements(query, limit, min_terminals)` | 中/英/法皆可、CJK 免空格;`min_terminals=2` 濾掉裝飾符號;hits 直附端子與節距,**通常免 describe** |
| `qet_list_categories(prefix)` | 關鍵字失敗時按目錄樹導覽 |
| `qet_describe_element(elmt_path)` | 端子 index/name/座標/方向 + 尺寸 hotspot |
| `qet_place_element(elmt_path, x, y, label, orientation, folio)` | 回實例 uuid + 端子表 |
| `qet_draw_conductor(from_element, from_terminal, to_element, to_terminal, num, color, path, folio)` | 元件用 label 或 uuid;端子用名字,**無名端子用數字索引字串**("0"/"1");`path` 見 §4 |
| `qet_list_content(folio)` | 列出實例與導線 |
| `qet_render(folio, width)` | 回傳圖片,**畫完必自檢** |
| `qet_netlist()` | 端子級連線 JSON,查線用 |
| `qet_validate()` | 真 QET 引擎載入檢查 |
| `qet_apply_titleblock(title, doc_id, subtitle, author, …)` | **畫完套公司 ISO 7200 圖框**(logo/底色/A3),一次套所有 folio |
| `qet_set_revisions(revisions)` | 填修訂歷史(累積);每筆 `{idx,date,desc,zone,by,appd}`,zone=修改座標 |
| `qet_check_iec_compliance(folio)` | 依公司 IEC 規範稽核(81346 代號/60204-1 線號顏色/連通性),回 MUST/SHOULD findings |

**收尾流程**:畫完電路 → `qet_apply_titleblock(...)` 套圖框 →
`qet_check_iec_compliance()` 稽核(修掉 MUST)→ `qet_render` 目視 →
`qet_set_revisions` 記錄版次。IEC 檢查要點:代號須 `-<類別字母><序號>`
(禁 JIS 縮寫 MC/THRY/CR);同代號多部件(接觸器主觸點+線圈共用 -KM1)
是**正常交互參照、非重複錯誤**;控制迴路導線應依類型上色(見 IEC 規範 §2)。

## 3. 座標與佈局規範

- **尺標 4px/mm**;**A3 橫式 folio 用 `qet_xml.model.FOLIO_A3_LANDSCAPE`**
  (16 欄×100px + 9 列×100px)。標題欄是實體 mm 尺寸,folio 不用 A3 預設
  的話比例會失真(QET 預設 17×60 頁面偏小,180mm 標題欄會佔掉 70% 寬)。
- **格點 10px**,所有座標落格點;元件實例 x/y = 定義 hotspot 的場景座標。
- **端子場景座標 = 實例 x/y + 定義端子 x/y**(describe/place 回傳的就是定義座標)。
- **三相動力迴路節距 20px**:選極距 20px 的元件(斷路器 fa4202、
  relais_therm4_**wide**、moteur_tri 都是 20px;窄版熱繼 10px 不要用)。
- 直通的垂直線讓端子 **x 對齊** → autoroute 走直線,最美觀。
- 控制迴路:主鏈一直行(如 x=520),並聯支路 +80px,雙迴路間隔 160px。
- 垂直間距:兩層元件 y 差 80~120px(端子多在 ±20,留出線號空間)。

## 4. 佈線:autoroute 與 path

- **預設不給 path** → QET 載入時自動佈線(端子 x 對齊時=直線,L 型也漂亮)。
- **必須給 path 的情況**:多條「同起訖高度」的導線(如三相換相交叉、
  多條並排饋線)—— autoroute 的水平段全走同一中點高度,
  **不同網路會重疊成一條假匯流排**。
- path 格式:從 terminal1 到 terminal2 的曼哈頓段
  `[["v",20],["h",-130],["v",39]]`(v=+下/−上,h=+右/−左)。
  **總和必須等於兩端子位移(容差 1px)**,否則 QET 靜默改回自動佈線。
- 階梯慣例:相鄰交叉線的水平段高度差 10~20px 分層。

## 5. 元件庫陷阱(實戰驗證)

- **裝飾符號無端子**:IEC 60617 圖示類很多不能接線,搜尋加 `min_terminals=2`。
- **無名端子**:按鈕/觸點類端子常無名 → 用索引字串 "0"/"1"(0=上為慣例,
  但 therm4_wide 例外,見下)。
- **relais_therm4_wide 端子索引不按 x 排序**:idx0/1@x+0、idx4/5@x+20、
  idx2/3@x+40(接 L2 用 4/5、L3 用 2/3)。
- **標籤顯示**:qet-xml 會把定義層 dynamic_text 範本實例化,label 才會上圖;
  交叉參照類觸點(con_simple 等)定義無範本 → 圖上無標籤是 QET 原生行為。
- **上游 zh 翻譯有錯位**(如某些 name_zh 對不上),以 name_en / 路徑為準。
- 元件驗證過就**寫回 data/aliases.json**(含端子備註、verified:true)。

## 6. 常見電路的已驗證做法

- **DOL 啟動**:見 `skeleton/out/motor_dol.qet`(9 元件 14 導線)。
- **正逆轉**:見 `skeleton/out/motor_reversing.qet`(15 元件 26 導線);
  換相交叉放在 **KM2 輸出側**、用 path 階梯分層;控制側互鎖 NC 串對方線圈。
- 自保持:aux NO 與啟動鈕並聯,兩端各自 connect 到同一節點端子
  (同一端子可掛多條導線,QET 自動畫接點)。

## 7. 標題欄圖框(titleblock)

- 公司標準圖框:`data/titleblocks/huchen_iso7200_a3.titleblock`
  (ISO 7200 全寬底欄,由 `tools/gen_titleblock.py` 從
  docs/ISO7200_A3_….xlsx 生成;改版改產生器再重生,勿手改輸出檔)。
- 套用方式(qet_xml):

  ```python
  tpl = ET.fromstring(open("data/titleblocks/huchen_iso7200_a3.titleblock").read())
  prj.embed_titleblock(tpl)          # 內嵌 + 所有 diagram 引用
  d.attrs.update({"author": "...", "title": "...", "indexrev": "A",
                  "date": "20260702", "folio": "%id / %total"})
  d.properties.update({"doc-id": "...", "doc-type": "&EFS 電路圖", ...})
  ```

- **folio 必用 `FOLIO_A3_LANDSCAPE`**(16×100 + **10×101**):含標題欄後
  總比例 = A3(1.414),GUI/CLI 匯出 PDF 才不會下方留白。旁的 rows 值
  會讓 folio 比例偏離 A3。
- **修訂歷史(累積、每列變數)**:修訂表每列綁 `rev{n}-idx/date/desc/
  zone/by/appd`,用 `diagram.set_revisions([{...}, ...])` 填(未用列自動
  補空,避免顯示 `%{rev3-idx}` 原文)。zone = 本次修改的圖面座標(如 D5)。
- **輸出 PDF**:`--cli-render out.pdf`(QET fork ≥0.100.16)——頁面=folio
  實際尺寸、零邊界,比例正確無空白;GUI「匯出 PDF」到 A3 紙也吻合(因
  folio 已是 A3 比例)。
- 變數:內建 `%{author} %{date} %{title} %{indexrev} %{folio}`;
  自訂(經 `d.properties` / GUI 標題欄屬性自訂表):`%{techref}
  %{checked-by} %{approved-by} %{doc-type} %{doc-status} %{subtitle}
  %{doc-id} %{remarks} %{rev-desc} %{rev-by} %{rev-appd}`。
- **排版為角落式**(xlsx sheet1):整組 180mm 靠右下,修訂表疊於標題欄
  上方;grid col0 為 `r100%` 填充欄,**必須放一個跨全高的空值 field**
  (EmptyCell 完全不畫線會讓頁框破口;folio 渲染沒有帶外框,收邊全靠
  cell 自己的邊框)。左側呈現為封閉空白面板 —— QET「標題欄=整條帶」
  模型的必然取捨,L 型繪圖區不支援。
- **格式陷阱(實戰)**:
  - `rowspan`/`colspan` 是「**額外**跨的格數」(colspan="1"=佔 2 格,
    titleblocktemplate.cpp:1202);產生器 API 用總格數、輸出時 -1。
  - 欄寬語法:`196`(px)/`r100%`(吃剩餘寬,整條 grid 恰一欄用);
    尺標 4px/mm。
  - 有內容的區域需以 field 完整覆蓋避免破洞;**刻意留白的區域則完全
    不放 field**(EmptyCell = 無框線,角落式排版靠這個)。

## 8. 環境與流程注意

- **改了 server.py 要使用者在 /mcp reconnect(或重啟 Claude Code)才生效**;
  qet_xml 的修改則腳本立即可用(server 內建索引/資料快取除外)。
- 檔案優先:MCP 工具每次呼叫 open→mutate→save;GUI 不會自動 reload,
  給使用者看要重開檔。QET 執行檔在
  `build/qelectrotech.app/Contents/MacOS/qelectrotech`(.app bundle,
  0.100.12 起);offscreen 外掛由 CMake POST_BUILD 自動複製進 bundle
  (0.100.14),缺它 --cli-* 會起不來。
- 標題欄 logo:點陣圖會被拉伸填滿格子,嵌入前先用 sips 白邊補到格子
  比例;JPEG 經 sips 轉檔會色偏(粉紫),**來源用 PNG**。
- QET GUI 用 pkill 關閉是安全的(0.100.4 起 SysV 單一實例鎖可自動恢復)。
- 元件索引快取在 `.cache/elements_index.json`,元件庫變動自動重建。
- commit 一律中文說明;QET fork 的 commit 另需 CMakeLists patch 版本 +1。
- **commit 前先確認測試綠燈**(tests/test_roundtrip.py)。
