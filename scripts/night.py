#!/usr/bin/env python3
"""Lançador isolado: cria .venv na raiz do projeto e roda run_night.py por ele.

Uso:  python scripts/night.py [--only 03] [--skip 11] [--dry-run]

Nada é instalado fora de .venv/. O PATH do processo (e das sessões do Claude
que ele abre) aponta primeiro para .venv, então pip, python, ruff, mypy e pytest
ficam todos lá dentro. Para desfazer tudo: apague a pasta .venv.
"""
import os, subprocess, sys, venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
BIN = VENV / ("Scripts" if os.name == "nt" else "bin")
PY = BIN / ("python.exe" if os.name == "nt" else "python")

if not PY.exists():
    print("Criando .venv ...", flush=True)
    venv.create(VENV, with_pip=True)
    subprocess.run([str(PY), "-m", "pip", "install", "-q", "pyyaml"], check=True)

env = os.environ.copy()
env["VIRTUAL_ENV"] = str(VENV)
env["PATH"] = str(BIN) + os.pathsep + env["PATH"]
env["PIP_REQUIRE_VIRTUALENV"] = "1"                       # pip recusa instalar fora do venv
env["PLAYWRIGHT_BROWSERS_PATH"] = str(VENV / "playwright")  # navegadores também ficam no venv
env["PYTHONDONTWRITEBYTECODE"] = "1"

sys.exit(subprocess.run([str(PY), str(ROOT / "scripts" / "run_night.py"), *sys.argv[1:]],
                        cwd=ROOT, env=env).returncode)
