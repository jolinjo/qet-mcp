# qet-mcp — 用 AI 控制 QElectroTech 畫電路圖

讓 Claude(或任何 MCP client)透過工具鏈操控 [QElectroTech](https://qelectrotech.org/)(QET)
產生與編輯電氣圖(.qet 專案檔)。

> **🤖 給 AI:開始任何繪圖工作前,先讀 [docs/AI-GUIDE.md](docs/AI-GUIDE.md)。**
> 那裡有工具目錄、黃金工作流、佈局規範與實戰驗證過的陷阱清單;
> 照著做可省下大量工具往返。新增功能或驗證新元件時,須同步更新該文件
> (維護規約見文件開頭)。

## 核心原則

**QET 本體改得越少越好,智慧全部放在外部工具鏈** —— QET fork 只「開洞」,
可維護性優先。互動模式為**檔案優先**:AI 產出/更新 .qet,GUI 只負責刷新顯示。

## 架構

```text
Claude Code / Claude Desktop
        │  (MCP, stdio)
        ▼
  qet-mcp  (Python MCP server ── 規則引擎、IEC 語意層)
        │
        ├──► qet-xml  (Python 函式庫:讀寫 .qet/.elmt,不碰 QET 程式)
        ├──► qet-cli  (headless 渲染/驗證/netlist,QET fork 新增的 CLI)
        └──► QET GUI  (使用者開著看結果,檔案更新後 reload)
```

## 里程碑

| 階段 | 內容 | 狀態 |
| --- | --- | --- |
| M0 | 讀懂 QET 核心類別與 XML 序列化,產出 schema 規格書 + walking skeleton | ✅ 完成 |
| M1 | qet-xml:Python 物件模型,round-trip golden 測試 | ✅ 完成 |
| M2 | qet-cli:headless render / validate / netlist(QET fork 0.100.6 內建 `--cli-*`) | ✅ 初版完成 |
| M3 | MCP server:26 個工具(stdio,零相依)—— 建案/放件/佈線/自動編號/交互參照/IEC 稽核/BOM/圖框/DXF 匯入 | ✅ 完成 |
| M4 | QET GUI 薄 RPC(reload / gotoElement),可延後 | — |

## M0 主要成果(實證,非紙上分析)

1. **導線不用算路徑**:`<conductor>` 省略 `<segment>` 時 QET 載入自動佈線
   (conductor.cpp:1147);QET 自己存檔也不寫 segment。Python 永遠不碰 autorouter。
2. **連結模型**:導線以「元件實例 uuid + 定義層端子 uuid」雙鍵定位;
   元件定義內嵌於專案 `<collection>`(自包含,跨機器不缺符號)。
3. **wrapper 必要**:`<element>`/`<conductor>` 必須包在 `<elements>`/`<conductors>`
   內,直接放 `<diagram>` 下會被靜默忽略(diagram.cpp:1367, 1489)。

詳見 [docs/qet-xml-schema.md](docs/qet-xml-schema.md) 與
[docs/qet-integration-points.md](docs/qet-integration-points.md)。

## 目錄結構

```text
docs/       M0 規格書與整合點評估
skeleton/   walking skeleton:gen_min.py 生成最小 .qet(2 元件 + 1 導線)
            golden/ 內含 QET 重存的黃金參考檔(round-trip 基準)
```

## 相關 repo

- QET fork(macOS/Qt6 可建置,分支 `QT6-MCP`):
  [jolinjo/QET](https://github.com/jolinjo/QET)
- 上游:[qelectrotech-source-mirror](https://github.com/qelectrotech/qelectrotech-source-mirror)

## 授權

QElectroTech 為 GPL v2+;本工具鏈的授權待定(目前僅供個人開發使用)。
