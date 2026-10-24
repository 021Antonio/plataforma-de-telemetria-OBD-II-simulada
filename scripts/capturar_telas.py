"""Sobe `python -m obd run` em portas livres, aplica um cenário e salva PNGs do dashboard e do painel."""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _espera(cond, limite_s: float, motivo: str) -> None:  # type: ignore[no-untyped-def]
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        try:
            if cond():
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise SystemExit(f"tempo esgotado: {motivo}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "img")
    ap.add_argument("--largura", type=int, default=1280)
    args = ap.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    srv, pnl, elm = _porta_livre(), _porta_livre(), _porta_livre()
    api, sim = f"http://127.0.0.1:{srv}", f"http://127.0.0.1:{pnl}"
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            [sys.executable, "-m", "obd", "run", "--perfil", "urbano", "--db", f"{tmp}/obd.db",
             "--porta-servidor", str(srv), "--porta-painel", str(pnl), "--porta-elm327", str(elm)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=RAIZ,
        )
        try:
            _espera(lambda: httpx.get(f"{api}/healthz", timeout=1).status_code == 200, 15, "servidor")
            _espera(lambda: httpx.get(f"{sim}/sim/state", timeout=1).status_code == 200, 15, "painel")
            httpx.post(f"{sim}/sim/profile", json={"name": "urbano"}).raise_for_status()
            httpx.put(f"{sim}/sim/override/rpm", json={"value": 3000}).raise_for_status()
            httpx.post(f"{sim}/sim/dtc", json={"code": "P0300", "pending": False}).raise_for_status()
            _espera(lambda: {"coolant", "fuel_level", "voltage", "short_fuel_trim"}
                    <= set(httpx.get(f"{api}/api/latest", timeout=1).json()["values"]), 15, "PIDs lentos")
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": args.largura, "height": 900})
                for url, nome in ((api + "/", "dashboard"), (sim + "/", "painel")):
                    page.goto(url)
                    page.wait_for_timeout(3000)  # deixa os valores lentos e a lista de DTCs chegarem
                    page.screenshot(path=str(args.saida / f"{nome}.png"), full_page=True)
                    print(f"salvo {args.saida / f'{nome}.png'}")
                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
