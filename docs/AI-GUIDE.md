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

**設備完整圖面架構**(未指定交付範圍時的預設,依繪圖規範 §11.1 頁序 +
§5.2 交付組合):封面/目錄 → 動力迴路 → 控制電源 → 安全迴路 → 控制迴路 →
PLC I/O → 端子(&EMB)→ 佈置圖(&ELD)→ 零件清單(&EPB),共 9 頁。
建法:`qet_new_project(title=設備名)` 設**圖名/專案標題** → `qet_add_diagram`
逐頁(title=**分頁圖名**)→ `qet_set_folio_title(folio, doc_type=DCC)` 標每頁
**文件類別**(封面留空;&EFS/&EMB/&ELD/&EPB)→ `qet_auto_docid(專案編號)`
**自動長出全部文件識別號**(改 DCC 後重跑即重整)→ `qet_apply_titleblock`
(套圖框;不帶 doc_type/doc_id 就**不會蓋掉逐頁的 DCC/識別號**)→
`qet_set_revisions`。頁次 %folio 自動 x/總數;doc-id = PROJ-DCC-nn(見 §5.2)。

## 2. 工具目錄(28 個)

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
| `qet_set_label(element, label)` | 改元件代號(element 用現 label 或 uuid) |
| `qet_move_element(element, x, y)` | 移動元件 |
| `qet_rotate_element(element, orientation)` | 旋轉(0/1/2/3=0/90/180/270°) |
| `qet_delete_element(element)` | 刪元件 + 其相連導線 |
| `qet_set_wire(from_element, from_terminal, to_element, to_terminal, num, color)` | 改既有導線的線號/顏色(IEC 60204-1:AC紅/DC藍/PE綠) |
| `qet_delete_wire(...)` | 刪一條導線(以兩端子識別) |
| `qet_add_diagram(title)` | 加一頁 A3 folio(title = 該頁分頁圖名) |
| `qet_set_folio_title(folio, title, doc_type, doc_id)` | 設**單一** folio 的分頁圖名(%title)、文件類別/DCC(%doc-type,如 `&EFS 電路圖`)、文件識別號(%doc-id)。多頁包每頁不同時用;通常設 title+doc_type,doc-id 交給 `qet_auto_docid` |
| `qet_auto_docid(project_no)` | 從專案編號 + 每頁 DCC(doc-type)**自動產生所有 doc-id**:`PROJ-DCC-nn`,nn 依 folio 序在同 DCC 內遞增;封面(無 DCC)只給 PROJ。**冪等**,改了任何頁 DCC 或重套圖框後重跑即重整編號 |
| `qet_auto_designate(prefix_map, only_unlabelled)` | 依類別字母(元件 prefix)自動配 IEC 81346 代號;預設只編無代號者,不破壞交互參照 |
| `qet_auto_xref()` | 交互參照(IEC 61082):同代號的觸點(slave)自動連到線圈(master),QET 顯示觸點位置表。放完該設備所有部件後執行 |
| `qet_render(folio, width)` | 回傳圖片,**畫完必自檢** |
| `qet_netlist()` | 端子級連線 JSON,查線用 |
| `qet_validate()` | 真 QET 引擎載入檢查 |
| `qet_apply_titleblock(title, doc_id, subtitle, author, …, template)` | **畫完套圖框**(logo/底色/A3),一次套所有 folio。範本預設取 **QET 公司圖框集**(使用者在 QET 維護的正本),`template` 可指定名稱或檔案路徑。`title`=圖名(專案標題 %projecttitle,每頁一致);`subtitle`=補充圖名(每頁標題 %title) |
| `qet_set_revisions(revisions)` | 填修訂歷史(累積);每筆 `{idx,date,desc,zone,by,appd}`,zone=修改座標 |
| `qet_check_iec_compliance(folio)` | 依公司 IEC 規範稽核(81346 代號/60204-1 線號顏色/連通性),回 MUST/SHOULD findings |
| `qet_generate_bom(all_folios, folio)` | 物料表:依代號分組(交互參照共代號者算一台) |
| `qet_import_dxf(dxf_path, name, category, name_en, filename, pin_layer, scale)` | DXF→.elmt 存進公司元件庫;幾何完整重現;端子讀自 `pin` 圖層;多圖塊(BLOCK)自動一顆一顆拆(見 §9) |

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

- **範本正本 = QET 公司圖框集**
  `~/Library/Application Support/QElectroTech/QElectroTech/titleblocks-company/`
  (使用者在 QET 範本編輯器維護)。
- **版控與版號(2026-07)**:公司元件庫與公司圖框集版控於
  `ClaudeCodeDev/QET-Lib/` repo(push 到 jolinjo/QET-Lib)。各區**版號
  各自獨立**,顯示在:元件庫各庫 `qet_directory` 的名稱、圖框**檔名**
  (name 屬性同步)。**改動任一處後**:顯示版號 +1 → 中文 commit 記
  「動了什麼→到什麼版本」→ push。**分工鐵則(2026-07-06 起):AI 不改
  QET 端**(Application Support 公司集合正本)。同步只有單向:QET 端 →
  repo → GitHub,且**只在使用者明確提示時**才做(讀 QET 端 → rsync 進
  QET-Lib → 版號 +1 → commit → push);**絕不做** repo → QET 端反向
  部署。平時一律改 QET-Lib repo,動工前先 `git pull`。會寫 QET 端的
  工具(qet_import_dxf 等)使用前先與使用者確認輸出位置。
  **例外(2026-07-08)**:版號顯示處 AI 可自行累加,含 QET 端圖框檔名/
  name 屬性的跳版改名;內容有動版號沒跳→兩邊一起 +1,不必再問。`_resolve_titleblock`
  預設取含 "A3" 的檔名,改名不影響;指名時要含版號。`qet_apply_titleblock` 預設從這裡取範本
  (`template` 參數可指定名稱/路徑),qet-mcp **不自帶權威版本**;
  `data/titleblocks/huchen_iso7200_a3.titleblock` 只是初始版/無公司集時的
  fallback(由 `tools/gen_titleblock.py` 從 docs/ISO7200_A3_….xlsx 生成)。
- **陷阱:套圖框 = 無條件覆蓋專案內嵌範本**——所以使用者改圖框文字要改
  「公司圖框集」那份(QET 範本編輯器),不要只改專案裡內嵌的副本,
  否則下次 `qet_apply_titleblock` 會用公司集版本蓋回去。
  2026-07:已移除三個 ISO 7200 必填星號(發行日期/文件識別號/頁次)。
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

## 9. DXF → 元件(qet_import_dxf)

把 CAD 圖轉成公司元件庫裡的 .elmt,**幾何一模一樣**。需要 `ezdxf`
(`pip install ezdxf`)。

- **幾何**:LWPOLYLINE/LINE/ARC/CIRCLE→`<polygon>`(曲線 flatten),
  軸對齊 ELLIPSE 保留為 `<ellipse>`;Y 軸翻轉、以 hotspot 置中、預設 4 px/mm。
- **端子讀自 `pin` 圖層**(關鍵):純幾何無法分辨「接線端子」與「裝飾線末端」
  (接地符號、安裝耳都會誤判)。所以端子**只**從指定圖層抓 —— 使用者在
  DXF 開一個 `pin` 圖層,在每個真端子位置放一個 **POINT/小圓**;旁邊的
  **TEXT** 就是腳位號(自動配給最近端子的 `name`)。方向依所在邊自動判 n/s/e/w,
  座標 snap 到 10px 格。**沒有 `pin` 圖層 → 建成 0 端子**(乾淨,之後在
  QET 元件編輯器補,或補圖層重跑)。
- **名稱與編號**:`name`(+`name_en`)寫進 `<names>`(元件庫顯示);另自動加一個
  `dynamic_text`(text_from=ElementInfo/label),放上 folio 時顯示代號(-Z1…)。
- **一張 DXF 多顆元件**,用 `split` 參數:
  - `split="block"`(預設):CAD **BLOCK(圖塊)**優先 —— 一個 block = 一顆 .elmt
    (檔名=圖塊名、hotspot=基準點);沒有圖塊則整張=一顆。
  - `split="cluster"`:**沒有圖塊也能拆** —— 把攤平的圖形依「空白間隙」切成
    數個空間分離的區塊,一區一顆(命名 `<name>_1..`,由左至右)。適合 CAD
    匯出成一堆線、多個零件並排的圖。間隙門檻預設為圖面較長邊的 3%。
  - `split="none"`:強制整張=一顆。
  - 回傳 `mode`(`blocks`/`clusters`/`single`)、`count`、`elements[]`。
- **輸出位置**:預設 `elements-company/<category>/<filename>.elmt`
  (category 預設 `control`,filename 預設 DXF 檔名;block 模式檔名取自圖塊名)。
  存完提醒使用者在 QET **重新整理元件面板**才看得到。
- **公司元件庫結構(2026-07)**:分兩個獨立庫,版號各自獨立(顯示在
  qet_directory 名稱,如「虎氶-示意圖v0.1」):
  - `schematic/`(**虎氶-示意圖**):IEC 電路符號,下分 10 個一層大分類
    `01_protection`(保護開關)/`02_relay_contactor`/`03_buttons`/
    `04_signaling`/`05_sensors`/`06_power`/`07_motor_actuator`/
    `08_terminal_earth`/`09_controller`/`10_misc`(每分類有 qet_directory
    中文名)。常用 IEC 標準元件已複製在庫內,優先取用。
  - `outline/`(**虎氶-外型圖**):DXF 轉入的實體外型(servo_1/2、plc、
    noise_filter…)。`qet_import_dxf` 預設 category=`outline`。
  改動任一庫後該庫版號 +1 並 rsync 到 QET-Lib push(見 QET-Lib README)。
  反向散布:QET fork ≥0.100.65 在元件庫面板右鍵「從 GitHub 更新元件庫」,
  即可從 QET-Lib 一鍵拉取(自動備份舊內容為 library-backup-*.tar.gz)。

## 10. 原始 .qet XML 與導線模型(改外部專案必讀)

**qet_xml 只適合「我們自建」的圖,不可 round-trip 外部/現成 .qet。** qet_xml
的導線模型是「元件 uuid + 端子 uuid」,但 QET 實檔的導線是用**整數端子 id**;
qet_xml 讀不進 → 存檔寫成 `element1=""`(空),**所有導線斷掉**。改現成專案
(換圖框、改標題、加中文…)一律用 **ElementTree 原始 XML 手術**,只動要改的
節點,`<element>`/`<conductor>` 原封不動。

**⚠ `<collection>` 必須含 `<category name="import">` 根分類**——空的 collection
會讓 QET 端所有元件整合(跨專案貼上、拖放入專案)失敗(QET ≤0.100.95 甚至
無窮迴圈卡死)。qet_xml 已無條件寫出;手工組 XML 時也要記得。

**.qet 接線模型(改導線/重接的關鍵):**
- 結構:`<diagram><elements><element>…<conductors><conductor…>`。
- **端子 id = 整張 diagram 的流水號**:走訪 `<elements>` 內每個 `<element>` 的
  `<terminals>/<terminal id="n">`,**依文件順序從 0 連續編**(element0 的端子先、
  再 element1…)。`id` 屬性已寫在檔內,直接讀即可。
- **導線靠端子 id 連接**:`<conductor terminal1="A" terminal2="B" num="…"
  …style…/>`,**不需**記元件。省略 `<segment>` 子節點 → QET 載入時自動佈線。
- **加/重接導線**:讀兩端子的 `id`;新增或改 `<conductor>` 的 terminal1/terminal2
  (style 屬性從既有 conductor 複製最省事)。一端可多接(接點合法)。
  已驗證:對 industrial.qet 加一條 `<conductor terminal1=4 terminal2=7>`,QET
  正常載入渲染。
- **⚠ 加/刪/重排 `<element>` 時 id 會位移**:必須把**所有** `<terminal id>`
  重新連續編號 **並**同步更新所有 `<conductor>` 的 terminal1/terminal2,否則接線
  全亂。這正是 qet_xml round-trip 出錯的根因。純改屬性(不動元件增刪)則 id 不變、
  最安全。

**自動編號規則(QET 原生 autonum,MCP 無工具,用 raw XML 設定):** 規則存在專案
屬性區(`<newdiagrams>` 內,與 border/inset/conductors/xrefs 同層),三個容器:
`<conductors_autonums current_autonum=… freeze_new_conductors=…>` /
`<folio_autonums>` / `<element_autonums current_autonum=… freeze_new_elements=…>`,
各含多個 `<{scope}_autonum title=… formula=…>`,規則體是若干 `<part>`。

- **⚠ 權威來源是 `<part>` 子節點,`formula` 屬性載入時被忽略(QET 自行重算)**
  ——parts 寫對就 100% 正確;formula 只是顯示用,可用下表自算填上。
- part:`type` / `value`(數字型=計數起點;string=字面值;token 型留空)/
  `increase` / `initialvalue`(僅 *folio 型)。13 種 type ＋ formula token:
  `unit→%sequ_N`、`unitfolio→%sequf_N`、`ten→%seqt_N`、`tenfolio→%seqtf_N`、
  `hundred→%seqh_N`、`hundredfolio→%seqhf_N`(N＝該型出現序,1 起)、
  `string→字面`、`idfolio→%id`、`folio→%F`、`elementprefix→%prefix`、
  `elementcolumn→%c`、`elementline→%l`、`plant→%M`、`locmach→%LM`。
- `current_autonum`＝作用中規則的 title(conductor/element 各一;folio 無此屬性)。
- **設規則≠觸發**:規則只在 GUI 建立物件當下套用,不回溯;設 current 只是預選。
  線號要真的顯示還需把導線預設 Text formula 設 `%autonum`(依需求另設)。
- 已用於公司專案範本:元件代號 `%id%prefix%sequ`、圖頁 `%sequ`;線號依
  IEC 60204-1 §2.2 **分號段建多組規則**(AC控制 unit 101 起、DC24V 201、
  DC-0V 字面 `0V`+流水、類比 401),畫不同迴路前於面板切換 current_autonum
  (動力相別 `1L1`、PE 屬非流水,手動)。真 QET 引擎載入 `ok`。**必用 raw
  XML**(qet_xml 不認得這些節點,round-trip 會整組掉)。

## 11. 電路修改／合併 SOP(改電路前必讀)

**鐵律:先讀懂拓樸再動手,不可只搬幾何。** 曾把兩頁機械式上下拼貼還加高頁面,
沒發現兩頁共用同一條母線——使用者指正「你沒去看線路內容」。

**步驟:**
1. **讀拓樸**:先萃取並陳述——這頁在做什麼?哪條是主母線?要動的元件掛在哪個
   net?跨頁箭頭(going/coming)**同線號=同一 net**;兩頁間同號箭頭對=可直接
   接線取代。不確定就先渲染/追線,別猜。
2. **端子 id**:移/併元件跨 diagram 時,整批 `<terminal id>` +offset,並同步
   所有 `<conductor>` 的 terminal1/terminal2(見 §10)。
3. **接線點**:tap 接**離元件最近的母線端子**(如右側元件接右端端子)。**別接
   最遠端**——會沿整條母線疊出平行線與多餘虛接點(踩過這雷)。找法:列出該 net
   所有端子的場景 x,挑最近的。
4. **佈局**:元件掛母線**尾端**、垂直落線(像變壓器/電源那樣 drop);串聯元件
   (如急停雙接觸器)直向堆疊。維持頁面尺寸,能掛進空白處就不要加高頁面。
5. **重佈線**:動完位置後清掉相關 `<conductor>` 的 `<segment>` 子節點 →
   QET autoroute 重畫。
6. **刪冗餘**:合併後兩頁間原本的同號跨頁箭頭對要刪(已同頁、無作用)。
7. **交給 QET 自動**:跨頁參照、頁碼、線號位置由 QET 靠 uuid/net 自動重算;
   刪頁後重編各 diagram 的 `order`,總頁數自動更新。
8. **驗證**:`--cli-validate` + `qet_render` 目視;確認接線沒斷、沒多餘虛接點。
