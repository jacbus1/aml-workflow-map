# 公開人物 Matching Benchmark

本測試只驗證 matching regression。Positive control 來源為官方政府頁面；negative control 只表示不在本 fixture，並非全球制裁狀態結論。

- As of: 2026-09-18
- Threshold: 80.0
- Positive: 11/11
- Negative controls: 3/3

## Positive cases（應命中）

| Input | Expected | Name score | Final score | Matched name | Result |
|---|---|---:|---:|---|---|
| Oleg Deripaska | CA-RUSSIA-2022-03-06-DERIPASKA | 100.0 | 100.0 | Oleg Deripaska | PASS |
| Deripaska Oleg | CA-RUSSIA-2022-03-06-DERIPASKA | 100.0 | 100.0 | Oleg Deripaska | PASS |
| Oleg Vladimirovich Deripaska | CA-RUSSIA-2022-03-06-DERIPASKA | 100.0 | 100.0 | Oleg Vladimirovich DERIPASKA | PASS |
| Roman Abramovich | RUS0270 | 100.0 | 100.0 | Roman ABRAMOVICH | PASS |
| Abramovich Roman Arkadyevich | RUS0270 | 100.0 | 100.0 | Roman Arkadyevich ABRAMOVICH | PASS |
| Roman Abramovitch | RUS0270 | 96.97 | 96.97 | Roman ABRAMOVICH | PASS |
| Igor Sechin | OFAC-2022-SECHIN | 100.0 | 100.0 | Igor Sechin | PASS |
| Sechin Igor Ivanovich | OFAC-2022-SECHIN | 100.0 | 100.0 | SECHIN Igor Ivanovich | PASS |
| Viktor Vekselberg | OFAC-2022-VEKSELBERG | 100.0 | 100.0 | Viktor Vekselberg | PASS |
| Victor Vekselberg | OFAC-2022-VEKSELBERG | 100.0 | 100.0 | VEKSELBERG Victor | PASS |
| Viktor Vekselburg | OFAC-2022-VEKSELBERG | 94.12 | 94.12 | Viktor Vekselberg | PASS |

## Negative controls（fixture 內應無命中）

| Input | Matches >= threshold | Result |
|---|---:|---|
| Taylor Swift | 0 | PASS |
| Cristiano Ronaldo | 0 | PASS |
| Jackie Chan | 0 | PASS |
