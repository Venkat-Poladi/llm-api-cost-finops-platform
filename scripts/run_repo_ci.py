from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    compiled = compileall.compile_dir(
        PROJECT_ROOT / "src",
        quiet=1,
        force=True,
    )
    compiled = (
        compileall.compile_dir(
            PROJECT_ROOT / "scripts",
            quiet=1,
            force=True,
        )
        and compiled
    )
    compiled = (
        compileall.compile_dir(
            PROJECT_ROOT / "tests",
            quiet=1,
            force=True,
        )
        and compiled
    )
    if not compiled:
        raise RuntimeError("Python compilation failed.")

    run([sys.executable, "-m", "pytest"])
    run([sys.executable, "-m", "ruff", "check", "."])
    print("REPOSITORY CI PASSED")


if __name__ == "__main__":
    main()
