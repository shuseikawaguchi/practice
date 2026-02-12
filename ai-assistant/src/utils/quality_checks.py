"""
Quality checks - 簡易品質チェック
"""
import subprocess
from pathlib import Path
from typing import Dict, List
from config import Config


def _run(cmd: List[str], cwd: Path) -> Dict:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    except Exception as e:
        return {"cmd": " ".join(cmd), "returncode": 1, "stderr": str(e)}


def run_quality_checks() -> Dict:
    results = []
    base = Config.BASE_DIR

    # 1) Syntax check
    results.append(_run(["python", "-m", "compileall", str(base)], cwd=base))

    # 2) Pytest if tests exist
    tests_exist = any(p.name.startswith("test_") and p.suffix == ".py" for p in base.rglob("test_*.py"))
    if tests_exist:
        results.append(_run(["python", "-m", "pytest", "-q"], cwd=base))

    ok = all(r.get("returncode", 1) == 0 for r in results)
    return {"ok": ok, "results": results, "tests_found": tests_exist}
