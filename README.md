# 香港版 K-12 知識圖譜（數學 · 英語 · 物理）

按**香港教育局（EDB）課程指引**編排的知識圖譜：每個知識點掛在一個學習階段、一個範疇、一個學習單元上，
沿先修關係做自適應診斷。

本倉庫由 [`xiaoyang111222/cn-math-taxonomy`](https://github.com/xiaoyang111222/cn-math-taxonomy) 改寫而成，
內地課程的結構（人教版冊章、義務教育／普通高中課程標準編號、內地「語文」學科）已經全部移除。

> **狀態：知識點與題目仍是上游的內容，只有結構換成香港的。**
> 上游 README 自己寫明「這是 AI 生成的初稿，未經任何教師審核」，高中題與英語題也沒有做盲解。
> 這批題目適合當**格式範本**，不適合直接給學生用；要按香港課程重寫。原說明保留在
> [`docs/upstream-readme.md`](docs/upstream-readme.md)。

## 數據

| | 數量 |
| --- | ---: |
| 知識點 | **1,761**（數學 768 · 英語 724 · 物理 269） |
| 題目 | **7,186** |
| 先修邊 | **2,812** |
| 學習單元 | **148** |

### 學習階段

香港的初中、高中學習單元**不指定年級**（由學校編排），所以初中、高中各算一個階段，不硬塞到某一年。

| 階段 | 鍵 | 範疇 | 知識點 |
| --- | --- | --- | ---: |
| 小一至小六 | `P1`–`P6` | 數 · 代數 · 度量 · 圖形與空間 · 數據處理 | 222（數學） |
| 小一至小三 / 小四至小六 | `P1-P3` / `P4-P6` | Interpersonal · Knowledge（英語） | 208 |
| 中一至中三 | `S1-S3` | 數與代數 · 度量、圖形與空間 · 數據處理（數學）／物理 · 科學 | 620 |
| 中四至中六 | `S4-S6` | 同上 + M1／M2 | 711 |

### 知識點的字段

```jsonc
{
  "id": "cnm_p001",
  "name": "1到5各数的认识",
  "subject": "math",
  "stage": "P1",              // 學習階段
  "stageLabel": "小一",
  "keyStage": "KS1",
  "grade": 1,                 // 只用于排序，不代表年级
  "strand": "數",             // 香港課程的範疇
  "domain": "數",
  "unit": "1N1",              // EDB 學習單元編號
  "unitName": "20以內的數",
  "chapter": "1N1 20以內的數",
  "standards": [{ "id": "edb-math:1N1", "confidence": "exact" }],
  "description": "…",
  "mastery_criteria": ["…"],
  "type": "conceptual"
}
```

`data/edb-standards.json` 是學習單元表，取代原來的內地課程標準條目；`data/hk-structure.json`
是「學科 → 階段 → 範疇 → 單元」的層級，給界面用。

## 對照是怎麼做的

| 學科 | 做法 | 結果 |
| --- | --- | --- |
| 數學 | 以人教版**章**為單位人工判斷，再套到章內每個知識點 | exact 438 / inferred 330 / **none 59（已刪）** |
| 物理 | 同上，初中對到科學（中一至中三）14 個單元，高中對到物理必修五單元及其小節 | exact 203 / inferred 66 |
| 英語 | **只能結構對齊**：香港英國語文課程不規定學習單元 | 724 點，按階段 + 範疇 |

英語的限制是硬性的：EDB 的英國語文課程只有三個學習範疇和各階段學習目標，學校自訂
`modules → units → tasks`。要逐點對應，得先選定一套香港教科書（朗文／牛津／培生），
那種表才適合放 `data/mappings/`。

詳細的對照依據、來源文件、把握程度見 [`docs/hk-edb/`](docs/hk-edb/README.md)。

## 重新生成數據

```bash
python3 scripts/fetch_hk_edb.py          # 下載 28 份 EDB 課程文件（PDF 不入庫）
python3 scripts/extract_hk_math_units.py # 抽出數學學習單元
python3 scripts/build_hk_math_mapping.py # 數學知識點 → 學習單元
python3 scripts/build_hk_physics_mapping.py
python3 scripts/build_hk_english_mapping.py
python3 scripts/build_hk_dataset.py      # 生成 data/*.json（會覆蓋）
python3 scripts/build_i18n_hant.py       # 簡→繁（香港字形 s2hk）
```

`build_hk_dataset.py` 以 `docs/hk-edb/*.json` 為準重建 `data/topics.json` 等文件；
它不依賴原有的人教版數據，但**刪掉的 59 個知識點無法從當前數據恢復**（要從 git 歷史取回）。

## 校驗

```bash
python3 scripts/validate.py
```

檢查知識點字段、階段與 `keyStage` 一致、範疇在香港課程白名單內、`standards` 指向存在的學習單元、
先修邊兩端存在且無環、先修不早於本知識點、題目的題型與答案合法、選擇題答案在選項內。
通過時打印 `VALIDATION PASSED`。

## 語言

導航右上角「簡 / 繁 / EN」。預設 **繁體（香港字形）**，`?lang=zh-Hans` 或 `?lang=en` 可指定。

- 繁體由 `assets/i18n-hant.js` 的映射表轉換（OpenCC `s2hk`），知識點名稱、題幹這些內容也會一起轉；
- 英文只翻界面，課程內容沒有英文版；
- 實現上不改業務代碼：`assets/i18n.js` 在渲染後替換文本節點，並用 `MutationObserver` 跟上動態內容。

```bash
node scripts/i18n-scan.js --check en   # 列出還沒翻譯的界面串
```

## 運行

純靜態站，沒有構建步驟：

```bash
python3 -m http.server 8000
```

然後打開 <http://localhost:8000/>。頁面用 `fetch` 讀 `data/*.json`，直接雙擊 html 不行。

線上版本：<https://mattpenny.github.io/study-step/>

## 已知局限

- **題目內容仍是上游的**（內地教材語境、AI 初稿、未經教師審核）。結構換了，題目沒有。
- **英語只有結構對齊**，沒有單元級對應。
- 刪掉了香港課程確實沒有的 59 個數學知識點（集合與邏輯用語、圓錐曲線、迴歸與獨立性檢驗、
  旋轉、超幾何分佈、小學數學廣角等），連同 241 道題、103 條先修邊。
- 另有 **6 條先修邊**因香港的教學順序與內地相反（先修反而更晚）而去掉，例如
  「大數的改寫」（小五 5N1）本來是小四「小數的近似」（4N8）的先修。名單見
  `scripts/build_hk_dataset.py` 的輸出。
- `scripts/build_primary.py`、`enh_build.py`、`enj_build.py`、`build_physics.py` 等是上游生成內地數據的
  一次性腳本，現在已不適用，只作參考保留。`data/mappings/`（人教版以外的教材版本對照）同理。

## 授權

沿用上游的 **CC BY-NC 4.0（署名—非商業性使用）**，見 [LICENSE](LICENSE)。
香港教育局的課程文件由政府發布，只下載不入庫（`docs/hk-edb/pdf/` 已在 `.gitignore`）。
