from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.matching import screen

DATA = ROOT / "benchmark" / "public_people.json"


def run(threshold: float = 80.0) -> dict:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    entities = payload["entities"]
    positives = []
    for case in payload["positive_cases"]:
        matches = screen(case["name"], entities, case.get("dob"), case.get("country"), threshold, 5)
        top = matches[0] if matches else None
        passed = bool(top and top["source_id"] == case["expected_source_id"])
        positives.append({**case, "passed": passed, "top": top})

    negatives = []
    for case in payload["negative_controls"]:
        matches = screen(case["name"], entities, threshold=threshold, limit=5)
        negatives.append({**case, "passed": len(matches) == 0, "matches": matches})

    return {
        "as_of": payload["as_of"],
        "threshold": threshold,
        "positive_total": len(positives),
        "positive_passed": sum(x["passed"] for x in positives),
        "negative_total": len(negatives),
        "negative_passed": sum(x["passed"] for x in negatives),
        "positive_cases": positives,
        "negative_controls": negatives,
    }


def markdown(result: dict, language: str = "en") -> str:
    zh = language == "zh"
    title = "# 公開人物 Matching Benchmark" if zh else "# Public-Person Matching Benchmark"
    note = (
        "本測試只驗證 matching regression。Positive control 來源為官方政府頁面；negative control 只表示不在本 fixture，並非全球制裁狀態結論。"
        if zh else
        "This benchmark tests matching regression only. Positive controls are grounded in official government pages; negative controls mean only that the name is absent from this fixture and are not global sanctions-status conclusions."
    )
    lines = [title, "", note, "", f"- As of: {result['as_of']}", f"- Threshold: {result['threshold']}",
             f"- Positive: {result['positive_passed']}/{result['positive_total']}",
             f"- Negative controls: {result['negative_passed']}/{result['negative_total']}", ""]
    lines.append("## Positive cases" if not zh else "## Positive cases（應命中）")
    lines.append("")
    lines.append("| Input | Expected | Name score | Final score | Matched name | Result |")
    lines.append("|---|---|---:|---:|---|---|")
    for x in result["positive_cases"]:
        top = x.get("top") or {}
        lines.append(f"| {x['name']} | {x['expected_source_id']} | {top.get('name_score','-')} | {top.get('score','-')} | {top.get('matched_name','-')} | {'PASS' if x['passed'] else 'FAIL'} |")
    lines.extend(["", "## Negative controls" if not zh else "## Negative controls（fixture 內應無命中）", "",
                  "| Input | Matches >= threshold | Result |", "|---|---:|---|"])
    for x in result["negative_controls"]:
        lines.append(f"| {x['name']} | {len(x['matches'])} | {'PASS' if x['passed'] else 'FAIL'} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    result = run()
    (ROOT / "BENCHMARK-RESULTS.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "BENCHMARK-EN.md").write_text(markdown(result, "en"), encoding="utf-8")
    (ROOT / "BENCHMARK-ZH.md").write_text(markdown(result, "zh"), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("positive_total","positive_passed","negative_total","negative_passed")}, indent=2))
