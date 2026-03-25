from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infra.config import render_default_config_yaml


BUILD_ROOT = Path(__file__).resolve().parent
OUT_DIR = BUILD_ROOT / "out"
WORK_DIR = BUILD_ROOT / "work"
SPEC_DIR = BUILD_ROOT / "spec"
ENTRYPOINT = PROJECT_ROOT / "src" / "cli" / "main.py"
EXE_NAME = "mdtx"


def _run_pyinstaller() -> int:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        EXE_NAME,
        "--distpath",
        str(OUT_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(PROJECT_ROOT),
        "--collect-submodules",
        "openai",
        "--collect-submodules",
        "markdown_it",
        "--hidden-import",
        "tqdm",
        "--hidden-import",
        "yaml",
        str(ENTRYPOINT),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    return completed.returncode


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "PyInstaller is not installed. Run `pip install -r src/buildtool/requirements-build.txt` first.",
            file=sys.stderr,
        )
        return 1

    exit_code = _run_pyinstaller()
    if exit_code != 0:
        return exit_code

    config_template = OUT_DIR / "config.template.yaml"
    config_template.write_text(render_default_config_yaml(), encoding="utf-8")

    print(f"Build finished: {OUT_DIR / (EXE_NAME + '.exe')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
