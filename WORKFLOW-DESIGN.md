# AML 大量案件工作流設計

> 本文件是營運與產品設計範本，不是法律意見。SAR/STR 的門檻、時限、名稱與資料保存要求須由合規與法律團隊按你的司法管轄區確認。

## 1. 核心模型：Case Portfolio 而不是 Alert Inbox

大量 alert 的失控通常源於「每一個 alert 都成為一張獨立工作單」。建議以關聯關係聚合後才產生 case：

```text
Source alerts / referrals
        ↓ 去重、關聯帳戶與實體、規則版本記錄
Investigation case（客戶／實體／網絡／期間）
        ↓ 風險、時限、專長、產能路由
Priority queue（P1 / P2 / P3）
        ↓
Investigation → QA → MLRO decision → Filing / Close → Monitoring feedback
```

每個 case 應有不可變更的 audit trail：alert 來源與規則版本、路由理由、負責人、所有證據索引、調查結論、覆核決定及時間戳。

## 2. 建議狀態機

| 狀態 | 目的 | 離開條件 | 服務水準／控制 |
| --- | --- | --- | --- |
| `INTAKE` | 完整性、去重、關聯與 jurisdiction 檢查 | 有完整 case package 或退回補件 | 自動化；記錄規則版本 |
| `TRIAGE` | 決定風險、時限、專長及優先度 | 已指派 queue / owner | P1 立即升級；禁止自行降級高風險案 |
| `INVESTIGATE` | 研究 CDD/EDD、交易、關聯方與公開資訊 | 證據清單完成、結論草稿完成 | analyst 與 investigator 分工；WIP limit |
| `QA_REVIEW` | 獨立檢查敘事、證據與理由 | 通過或退回補正 | 四眼原則與缺失分類 |
| `MLRO_DECISION` | 決定提交、持續監控、限制或結案 | 已簽核 disposition | 對重大／重複／高風險案強制升級 |
| `FILE_OR_CLOSE` | 提交、保留、通知內部治理或結案 | 文件索引與後續監控到位 | 時限、保存期限、tipping-off 控制 |
| `POST_CASE_MONITORING` | 將已結案例外回饋給監控規則及客戶風險 | 已更新 scenario / risk profile | 量化 false-positive 與 recurrence |

## 3. 大量案件時的路由規則

1. **先聚合再分派**：以 customer / beneficial owner / counterparty / typology / time window 建立 investigation bundle，避免同一網絡被數十名 analyst 重複處理。
2. **用風險分數決定 SLA，而非 FIFO**：分數應包含客戶、產品、地域、交易模式、制裁/負面消息、執法查詢、重複性與監控模型信心；分數構成需可解釋及版本化。
3. **以 skill-based queue 指派**：例如 trade finance、crypto、cash-intensive business、sanctions、correspondent banking；queue 設 WIP 上限，接近 SLA 的案件自動升級。
4. **將「決定不提交」當成正式結果**：必須有理由、證據和 QA，而非單純關閉 alert。
5. **把質量與產能分開量度**：不要只以結案件數衡量 analyst。至少追蹤 backlog age、SLA breach、reopen rate、QA reject rate、case merge rate、SAR decision cycle time、rule-level false-positive rate。

## 4. 圖的資料結構

互動圖應呈現四個層級：

```text
Portfolio → Priority Queue → Investigation Case / Bundle → Workflow Step
```

因此主管可在第一層看 queue 健康度，在第二層看 backlog 與 aging，在第三層找出個案，在第四層稽核流程與決策。真正的 production version 應只顯示必要的去識別化欄位；完整 case 資料保留在受權限控管的案件系統。

## 5. 為何採用這個設計

FFIEC 的現行 BSA/AML 手冊要求機構有從初始偵測至處置的清楚升級流程，且考慮風險概況、交易量、適當人手與 CDD/EDD 資訊；也明確關注不提交 SAR 的決定、重複 SAR 的升級及提交文件保存。FATF 的風險為本原則則支持以機構規模、複雜度及 ML/TF 風險調整控制強度。

參考資料：

- [FFIEC：Suspicious Activity Reporting — Examination Procedures](https://bsaaml.ffiec.gov/manual/AssessingComplianceWithBSARegulatoryRequirements/04_ep)
- [FFIEC：Suspicious Activity Reporting](https://bsaaml.ffiec.gov/manual/AssessingComplianceWithBSARegulatoryRequirements/04)
- [FFIEC：SAR Quality Guidance](https://bsaaml.ffiec.gov/manual/Appendices/13)
- [FATF：Risk-based supervision and enforcement guidance](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Rba-effective-supervision-and-enforcement.html)
