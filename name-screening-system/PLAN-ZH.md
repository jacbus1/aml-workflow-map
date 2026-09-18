# Jac-Name-Screening v2.0 開發計劃（中文）

## 1. 目標

Jac-Name-Screening v2.0 的核心不是「做一個 fuzzy search」，而是建立一套可重現、可解釋、可審計、可量化漏報（false negative）的 sanctions/name-screening 工作台。

優先目標：

1. **降低漏報**：名稱變體、別名、轉寫、名字次序、部分 DOB、國籍差異不應輕易令真正候選人消失。
2. **控制假陽性**：短名、公司後綴、weak alias 不應單憑模糊字串分數產生極高分。
3. **官方來源優先**：OFAC、UK、Canada、UN 各自保留來源、版本、下載時間、SHA-256 及 source ID。
4. **可解釋結果**：顯示命中哪個 name/alias、name score、DOB/country evidence、弱別名 penalty、來源。
5. **可審計**：每次 screening 記錄 threshold、source snapshot、結果數、時間及版本。
6. **可測量**：建立 known-positive benchmark，release 前量度 recall / false negatives。
7. **相片核對獨立化**：官方 watchlist photo 可供人工 side-by-side；本地 face similarity 只作輔助，預設關閉，不自動決定「同一人」。

## 2. v2 架構

```text
Official Sources
OFAC / UK / Canada / UN
        │
        ▼
Source adapters + validation
        │
        ▼
Canonical screening records
primary / strong aliases / weak aliases / native names
DOBs / countries / programs / source IDs
        │
        ▼
Explainable Matching Engine
        │
        ├── exact / normalized
        ├── token/order similarity
        ├── transliteration
        ├── strong vs weak alias weighting
        ├── DOB evidence
        └── country evidence
        │
        ▼
Candidate ranking
        │
        ▼
Analyst review + audit trail
```

## 3. P0 資料來源

### OFAC
- SDN 及後續可加入 Consolidated Non-SDN。
- v2 legacy flat-file importer 同時支援 primary、ALT、ADD、comments。
- strong/weak alias 分開。
- 同一 UID 的資料關聯後才寫入資料庫。

### UK Sanctions List
- 使用 2026 年後的 UK Sanctions List；不再依賴已停止更新的 OFSI Consolidated List。
- CSV parser 以 `Unique ID` 分組。
- `Primary Name`、`Primary Name Variation`、`Alias` 分開處理。
- `Alias strength` 若為 low quality，進 weak alias。

### Canada
- 支援 Consolidated Canadian Autonomous Sanctions List XML adapter。
- 保存 regulation / schedule / item / listing date 等來源 metadata（逐步完善）。

### UN
- 支援 UN Security Council Consolidated List XML。
- Good quality a.k.a. → strong alias。
- Low quality a.k.a. → weak alias。
- 多 DOB、多 nationality、original script 分開保存。

## 4. Matching Engine v2

### 4.1 名稱正規化
- Unicode NFKD
- 大小寫
- punctuation / whitespace
- accents
- transliteration
- tokenization

### 4.2 名稱候選
- primary name
- strong alias
- weak alias
- native script transliteration

### 4.3 False-positive controls
- 單 token query 降權。
- 公司 suffix（LTD/LLC/PLC/HOLDINGS/GROUP 等）造成的 subset match 降權。
- weak alias 有 penalty，不能單憑 weak alias 輕易達到最高 confidence。

### 4.4 DOB / country
- DOB / country 主要作 supporting / contradicting evidence，而非一律 hard filter。
- 支援多 DOB、year-only DOB。
- Country mismatch 只作有限 penalty，避免 source data 不完整造成漏報。

### 4.5 輸出
- `score`
- `name_score`
- `match_kind`
- `matched_name`
- `dob_status`
- `country_status`
- `risk_band`（candidate priority，不代表法律結論）
- `score_breakdown`

## 5. Source refresh / data integrity

所有正式 replace 必須 atomic：

```text
Download / Upload
→ parse
→ validation
→ non-empty / sanity check
→ SHA-256
→ BEGIN TRANSACTION
→ delete old source
→ insert new source
→ write snapshot receipt
→ COMMIT
```

如果 parse 或 validation fail：舊資料不受影響。

## 6. API / 安全

- Upload size limit
- Batch row limit
- 空白 name 拒絕
- CSV formula-injection escaping
- Security headers
- 不保存 production PII 到 repository
- 不把 biometric embedding 當必要持久資料

## 7. Photo Verification（v2 optional）

```text
Candidate hit
→ official photo provenance
→ manual side-by-side
→ optional local face detection/alignment/embedding
→ similarity score
→ Human review required
```

原則：
- 預設 OFF。
- 只做指定 candidate 的 1:1 verification，不做全網反查。
- 顯示 `LOW / REVIEW / HIGH similarity`，不輸出自動「same person = yes」。
- 保存來源 URL、retrieved_at、image SHA-256、model/version；KYC embedding 優先即時計算後丟棄。

## 8. Multi-Agent QA 工作流

### Manager Agent
- 只接受通過 release gates 的版本。
- 彙整其他 agent 結果。

### Source Agent
- 驗證 parser、source IDs、aliases、DOB、atomic refresh、stale deletion。

### Matching/Data Scientist Agent
- known-positive recall、name mutations、false-positive controls、threshold regression。

### Security/QA Agent
- malformed uploads、超大 batch、空名、CSV injection、API headers、錯誤路徑。

### Identity Agent
- alias strength、multiple DOB、native script、entity resolution、photo provenance。

v2 先以**可重現 deterministic QA agents**實作；LLM 不參與最終 sanctions disposition。

## 9. Release Gates

- Unit + integration tests 全部通過
- Runtime smoke test 通過
- Atomic source replacement 通過
- Empty source refresh protection 通過
- stale rows 能刪除
- strong/weak alias 分流通過
- multiple DOB 通過
- subset false-positive regression 通過
- Unicode/transliteration 通過
- batch limits / malformed CSV 通過
- CSV injection protection 通過
- benchmark known positives 全部達目標 threshold
- source snapshot / hash receipt 可重現

## 10. 名人 / 公開人物 Benchmark 原則

- 只使用官方來源可核實的 listed person 作 positive control。
- 每個 benchmark 保存 `source + source_id + as_of + official URL`。
- 測 exact、簡稱、次序變化、輕微拼寫變體。
- Negative control 只代表「此 benchmark fixture 中無該人」，**不延伸成全球 sanctions status 的法律結論**。

## 11. 實作階段

### Phase 1 — 本輪執行
- v2 matching engine
- strong / weak alias
- multiple DOB
- atomic source replacement + source snapshots
- OFAC 4-file importer
- UK CSV adapter
- UN XML adapter
- Canada XML adapter（容錯 schema mapping）
- API hardening
- deterministic multi-agent QA runner
- 公開人物 benchmark

### Phase 2
- OFAC Advanced XML / Consolidated Non-SDN
- canonical cross-source entity resolution
- PostgreSQL production schema
- source diff dashboard

### Phase 3
- official-photo provenance
- manual photo compare UI
- optional local face similarity
- threshold validation dataset

### Phase 4
- PEP/RCA connector
- adverse media（獨立 risk signal，不混成 sanctions hit）
- ownership/network graph
