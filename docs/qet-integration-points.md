# QET 改動點評估 — M0

原則:QET fork(`QT6-MCP` 分支)只「開洞」,智慧在外部 Python 工具鏈。
本文件盤點 M2(qet-cli)/ M4(GUI RPC)要碰的 C++ 復用點與風險。

## 架構(定案)

```
Claude (MCP client)
   │ stdio
   ▼
qet-mcp   Python MCP server(規則引擎 / IEC 語意層)
   ├─► qet-xml   Python 讀寫 .qet/.elmt(不碰 QET 程式)
   ├─► qet-cli   headless 渲染/驗證/netlist(QET fork 新增的 CLI 進入點)
   └─► QET GUI   使用者開著看結果;檔案更新後 reload(M4 才做薄 RPC)
```

UX 決策(使用者已確認):**檔案優先**,不做即時繪圖 RPC;GUI 只負責刷新顯示。

## M2 qet-cli 復用點(已核實)

| 功能 | 復用 API | 位置 |
|---|---|---|
| 開專案 | `QETProject(filepath)` | sources/qetproject.h |
| render PNG | `Diagram::toPaintDevice(QPaintDevice&, w, h, …)` | diagram.h:222 |
| render 參考 | `ExportDialog::generateImage/generateSvg/generateDxf` | exportdialog.h:93-95(UI 耦合,抽邏輯不抽類) |
| validate | 專案載入路徑本身的錯誤偵測(missing element / xml error) | qetproject.cpp fromXml 路徑 |
| netlist | 遍歷 `Diagram::content()` 的 conductors:`terminal1/2` → `Terminal::uuid()`、parent `Element::uuid()` + label | conductor.h:67-68、terminal.cpp:746、element.h:157 |
| 離屏 | `QT_QPA_PLATFORM=offscreen`(本機已驗證可跑) | — |

實作形態:新增 `sources/cli/` 目錄 + main 進入點分流(`qet-cli render|validate|netlist`),
既有程式幾乎不動;以「可提 PR 回上游」品質寫。

### 已知坑
1. `--version` / QCommandLineParser 走 `::exit()` — CLI 模式須避免建 SingleApplication
   (直接 QApplication offscreen),否則觸發單一實例邏輯。
   (macOS 殘留鎖問題已在 0.100.4 以 SysV 修正,但 CLI 本來就不該搶實例。)
2. 翻譯/資源:0.100.2 已改內嵌 `:/lang/`,headless 無障礙。
3. render 尺寸上限:QPainter 2^15-1(exportdialog.h:82),大圖要分頁或限縮。

## M4 GUI RPC(延後)

QLocalServer JSON-RPC,僅四方法:`app.ping` / `project.reload` / `diagram.exportImage` /
`view.gotoElement`(跳頁+置中+高亮)。全部 `QMetaObject::invokeMethod` 回主執行緒。
估計 <300 行,獨立檔案。

## 風險帳本(誠實記)

- **format-tracking**:qet-xml 是第二份序列化實作,上游 schema 演進會漂移。
  對策:鎖 `version="0.100.0"` 生成;golden-file round-trip;canonicalize 工具穩定 diff。
- **fork 維護**:M2 CLI 是主要 rebase 面(新增檔為主,衝突面小);提 PR 上游是歸零策略。
- **導線佈線**:已拆彈 — 省略 `<segment>` 由 QET 載入時自動佈線(conductor.cpp:1147)。

## Walking Skeleton(M0 驗證,下一步)

最小端到端:Python 生成含 2 元件 + 1 導線(無 segment)的 .qet
→ 用本 fork 的 QET 開啟 → 元件正確顯示、導線自動佈線 → 證明檔案優先管線可行。
