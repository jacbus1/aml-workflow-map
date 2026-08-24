# High-Volume AML Case Workflow Design

> This is an operating and product-design template, not legal advice. Compliance and legal teams must confirm the applicable SAR/STR thresholds, time limits, terminology, and retention requirements for their jurisdiction.

## 1. Core model: a case portfolio, not an alert inbox

High alert volumes become unmanageable when every alert is treated as an independent work item. Aggregate related activity before creating a case:

```text
Source alerts / referrals
        ↓ De-duplication, account/entity relationship mapping, rule-version capture
Investigation case (customer / entity / network / period)
        ↓ Routing by risk, deadline, specialist skill and capacity
Priority queue (P1 / P2 / P3)
        ↓
Investigation → QA → MLRO decision → Filing / close → Monitoring feedback
```

Every case should retain an immutable audit trail: alert source and rule version, routing rationale, assigned owner, evidence index, investigation conclusion, review decision, and timestamps.

## 2. Recommended case state machine

| State | Purpose | Exit condition | Service level / control |
| --- | --- | --- | --- |
| `INTAKE` | Check completeness, duplicates, relationships, and jurisdiction | A complete case package exists or the item is returned for remediation | Automated where possible; capture the rule version |
| `TRIAGE` | Set risk, deadline, specialist skill, and priority | Queue and owner are assigned | Immediately escalate P1; prohibit unilateral downgrade of high-risk cases |
| `INVESTIGATE` | Research CDD/EDD, transactions, counterparties, and public information | Evidence checklist and draft conclusion are complete | Separate analyst and investigator duties; set WIP limits |
| `QA_REVIEW` | Independently test the narrative, evidence, and rationale | Approved or returned for remediation | Four-eyes review and defect classification |
| `MLRO_DECISION` | Decide filing, continued monitoring, restriction, or closure | Disposition is approved | Require escalation for material, recurring, or high-risk cases |
| `FILE_OR_CLOSE` | File, retain, inform internal governance, or close | Evidence index and follow-up monitoring are in place | Time limits, retention period, and tipping-off controls |
| `POST_CASE_MONITORING` | Feed completed-case findings into monitoring rules and customer risk | Scenario or risk profile is updated | Measure false positives and recurrence |

## 3. Routing rules for high-volume operations

1. **Aggregate before assignment.** Use customer, beneficial owner, counterparty, typology, and time window to create investigation bundles so that several analysts do not investigate the same network independently.
2. **Set SLA by risk score, not FIFO.** Include customer, product, geography, transaction pattern, sanctions or adverse media, law-enforcement inquiry, recurrence, and monitoring-model confidence. The score composition must be explainable and versioned.
3. **Use skill-based queues.** Examples include trade finance, crypto, cash-intensive business, sanctions, and correspondent banking. Apply WIP limits and automatically escalate cases approaching their SLA.
4. **Treat a no-file decision as a formal outcome.** It needs a rationale, evidence, and QA review; it should not be a simple alert closure.
5. **Measure quality separately from throughput.** Do not judge analysts only by case count. Track backlog age, SLA breaches, reopen rate, QA reject rate, case-merge rate, SAR decision cycle time, and rule-level false-positive rate.

## 4. Data structure for the map

The interactive map should represent four levels:

```text
Portfolio → Priority Queue → Investigation Case / Bundle → Workflow Step
```

This lets leadership view queue health at level one, backlog and ageing at level two, a specific case at level three, and auditable workflow decisions at level four. A production implementation should show only necessary de-identified data; complete case details should remain in an access-controlled case-management system.

## 5. Why this design is appropriate

The current FFIEC BSA/AML Manual expects a clear escalation process from initial detection to disposition and considers the risk profile, transaction volume, appropriate staffing, and CDD/EDD information. It also addresses no-file decisions, escalation for repeat SARs, and filing-document retention. FATF's risk-based approach supports calibrating control strength to an institution's size, complexity, and ML/TF risk.

References:

- [FFIEC: Suspicious Activity Reporting — Examination Procedures](https://bsaaml.ffiec.gov/manual/AssessingComplianceWithBSARegulatoryRequirements/04_ep)
- [FFIEC: Suspicious Activity Reporting](https://bsaaml.ffiec.gov/manual/AssessingComplianceWithBSARegulatoryRequirements/04)
- [FFIEC: SAR Quality Guidance](https://bsaaml.ffiec.gov/manual/Appendices/13)
- [FATF: Risk-based supervision and enforcement guidance](https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Rba-effective-supervision-and-enforcement.html)
