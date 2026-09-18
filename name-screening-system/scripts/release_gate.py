from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Agent:
    name: str
    targets: list[str]


AGENTS = [
    Agent("SourceAgent", ["tests/test_importers.py", "tests/test_importers_v2.py", "tests/test_db_v2.py"]),
    Agent("MatchingDataScientistAgent", ["tests/test_matching.py", "tests/test_matching_v2.py", "tests/test_benchmark.py"]),
    Agent("SecurityQAAgent", ["tests/test_api.py", "tests/test_api_v2.py"]),
]


def run_agent(agent: Agent) -> bool:
    print(f"\n=== {agent.name} ===")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", *agent.targets], cwd=ROOT)
    return proc.returncode == 0


def main() -> int:
    results = [(a.name, run_agent(a)) for a in AGENTS]
    print("\n=== ManagerAgent release decision ===")
    for name, ok in results:
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
    ok = all(x[1] for x in results)
    print(f"RELEASE_GATE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
