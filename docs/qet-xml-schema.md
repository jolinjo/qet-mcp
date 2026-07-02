# QET 專案檔 (.qet) XML Schema 筆記 — M0

依據:QET fork `QT6-MCP` 分支(基準 `32b66c94a`,版本 0.100.4)原始碼 + `examples/` 真實專案檔反推。
主要佐證檔:`examples/photovoltaique.qet`(新格式,version 0.100.0)、`examples/741.qet`(舊格式對照)。

## 1. 專案檔整體結構

```xml
<project title="..." version="0.100.0">
    <properties>                    <!-- 專案層屬性 (saveddate 等) -->
    <newdiagrams>                   <!-- 新增 folio 的預設值 -->
    <diagram ...>                   <!-- 每頁一個 folio,可多個 -->
        <defaultconductor .../>
        <elements>                  <!-- wrapper 必要!直接子節點會被靜默忽略 -->
            <element .../>          <!-- 元件「實例」 -->
        </elements>
        <conductors>                <!-- 同上(diagram.cpp:1367, 1489) -->
            <conductor .../>
        </conductors>
        <shapes><shape .../></shapes>
        <independent_texts/> <images/>
    </diagram>
    <collection>                    <!-- 內嵌元件庫(自包含關鍵!) -->
        <category name="import">
            <category name="...">…巢狀分類…
                <element name="xxx.elmt">
                    <definition ...> <!-- 元件「定義」= .elmt 內容 -->
                </element>
```

- **自包含**:實例的 `type="embed://import/..."` 指向 `<collection>` 內路徑。放元件時必須同時把定義塞進 collection(路徑對齊),專案跨機器不缺符號。→ 印證「內嵌 collection」決策。

## 2. diagram(folio)節點

屬性(photovoltaique.qet 實測):`title`、`order`(頁序)、`cols`/`rows`、`colsize`/`rowsize`、`width`/`height`、`author`、`date`、`displaycols`/`displayrows` 等。
座標系:場景座標,**格點 10px**(`Diagram::xGrid/yGrid`),元素 x/y 建議落格點。

## 3. 元件定義 `<definition>`(collection 內 / .elmt)

```xml
<definition hotspot_x="11" hotspot_y="34" width="20" height="60"
            version="0.90" type="element" link_type="master">
    <names><name lang="en">…</name></names>
    <informations/> <description>…圖形原語…</description>
    <terminal uuid="{…}" name="" orientation="n|s|e|w" x="0" y="-2" type="Generic"/>
</definition>
```

- **terminal uuid 定義在「定義層」**(photovoltaique.qet:5105)。同一定義的多個實例共享同組 terminal uuid → 導線需「實例 uuid + 端子 uuid」雙鍵定位。
- `hotspot_x/y`:定義局部原點;實例 x/y 即 hotspot 對齊點的場景座標。
- 端子 `orientation`: n/s/e/w(定義層字母;實例層舊欄位是 0-3 整數)。

## 4. 元件實例 `<element>`(diagram 內)

```xml
<element uuid="{實例uuid}" type="embed://import/...(.elmt)"
         x="330" y="260" orientation="0" prefix="F" z="10" freezeLabel="false">
    <terminals>  <!-- 僅向後相容,新版邏輯不靠它 -->
        <terminal id="0" orientation="0" x="0" y="-17"/>
    </terminals>
    <elementInformations>
        <elementInformation show="1" name="label">-K1</elementInformation>
    </elementInformations>
    <dynamic_texts><dynamic_elmt_text …/></dynamic_texts>
</element>
```

- `uuid` = 實例識別(`Element::uuid()`,element.h:157)。
- `orientation`:0/1/2/3 = 0°/90°/180°/270°。
- 標籤走 `elementInformations` 的 `name="label"` + `dynamic_texts` 顯示。

## 5. 導線 `<conductor>` — 風險最高處,已拆彈

新格式(≥0.7,diagram.cpp:1178-1188):

```xml
<conductor element1="{實例uuid}" terminal1="{端子uuid}"
           element2="{實例uuid}" terminal2="{端子uuid}"
           type="multi" num="201" color="#ff0000" condsize="1" …>
    <segment orientation="horizontal|vertical" length="…"/>  <!-- 可省略! -->
</conductor>
```

**關鍵事實(conductor.cpp:1147-1151)**:`<segment>` 全部省略時,`pathFromXml()` 直接
`generateConductorPath(...)` **自動佈線並回傳成功**;segment 與端子位置不一致(誤差>1px)
也 fallback 自動佈線(1164-1170)。

→ **結論:qet-xml(Python)寫導線只需雙鍵 uuid + 屬性,完全不寫 segment,
QET 載入時自動佈線。Python 永遠不用實作 autorouter。**
canonicalize(headless load→save 回填 segment)降級為「美化/穩定 diff」用途,非正確性必需。

舊格式對照(741.qet):`terminal1="0"` 整數 id,靠 diagram 層 `<terminals>` 註冊表;
**qet-xml 只寫新格式**,讀取時兩者都要認得(retro-compat 見 diagram.cpp:1178 起)。

- `type`:`multi`(一般)/ `single`(單線圖)。常用屬性:`num`(線號)、`color`、
  `condsize`、`formula`、`function`、`tension_protocol`。

## 6. round-trip 注意事項(黃金檔實證,skeleton/golden/min_qet_saved.qet)

黃金檔 = Python 生成的 min.qet 由 QET 0.100.4 開啟後 Cmd+S 重存。實測差異:

- **QET 存檔也不寫 `<segment>`**:未被手動修改的直線導線,QET 自己的輸出同樣無
  segment(只有 `<sequentialNumbers/>` 子節點)。省略 segment 是常態而非 hack。
- **衍生屬性**:QET 補 `element1_label` / `element1_name` / `terminalname1/2`
  (冗餘快取,讀取時不必提供)+ 全套預設屬性(bicolor/cable/formula…)。
- **legacy `<terminals>`**:實例層回填 `id` 為「全 diagram 連號」(元件A: 0,1;
  元件B: 2,3),且 y 是 dock 點(±16)非定義座標(±20)。純相容用,生成時可省。
- **空節點**:`<inputs/>`、`<dynamic_texts/>`、`<texts_groups/>` 會被補上。
- **屬性按字母排序**輸出;`<elements>` 內元件順序可能改變(無語意)。
- 專案層會補 `<newdiagrams>`、`<xrefs>`、autonum 等預設章節。
- diff 策略:canonical 化(屬性排序 + 忽略衍生屬性/預設章節)後比對「語意核心」:
  實例 uuid/type/x/y/orientation/label、導線雙鍵 uuid + num/color、collection 定義。
- 專案 `version` 屬性影響 retro-compat 分支;鎖定生成 `version="0.100.0"`。
