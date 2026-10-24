#!/usr/bin/env python3
"""Roda as tarefas de tasks/ em ordem, uma sessão headless do Claude por tarefa.

Uso:  python scripts/run_night.py [--only 03 04] [--skip 09 11] [--dry-run]

Por tarefa: sessão nova, modelo do cabeçalho, porta de qualidade (lint + test),
1 nova tentativa, escalada de modelo se falhar, commit e push.
Tarefa que não passa fica "bloqueada" e só os dependentes dela são pulados.
"""
import argparse, json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "runs-night"
STATE = LOGS / "state.json"
ESCALA = {"haiku": "sonnet", "sonnet": "opus"}
GATE = 'pip install -e ".[dev]" -q && make lint && make test'
TOOLS = "Read Write Edit Glob Grep Bash"
MAX_TURNS = "120"
PROBE_EVERY = 15 * 60          # testa a cota a cada 15 min
MAX_ESPERA = 48 * 3600         # desiste após 48 h sem cota


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), cwd=ROOT,
                          text=True, capture_output=True, **kw)


def load_tasks():
    out = []
    for f in sorted((ROOT / "tasks").glob("*.md")):
        head = re.match(r"---\n(.*?)\n---", f.read_text(), re.S)
        meta = yaml.safe_load(head.group(1))
        meta["file"] = f.relative_to(ROOT).as_posix()
        meta["id"] = str(meta["id"]).zfill(2)
        out.append(meta)
    return sorted(out, key=lambda t: t["order"])


def prompt(t, extra=""):
    return (f"Leia apenas {t['file']} e as seções de docs/spec citadas nele (campo spec). "
            "Escreva os testes primeiro, implemente, rode os comandos do critério de pronto "
            "e corrija até passarem. Não pergunte nada: decida pela spec e registre dúvidas "
            "em docs/duvidas.md. Se `git status` mostrar trabalho parcial, continue dele em vez de recomeçar. "
            "Não toque em outras tarefas. Termine com um resumo de até 5 linhas."
            + extra)


LIMIT_KEYS = ("rate limit", "usage limit", "limit reached", "limit will reset",
              "quota", "overloaded", "429")


def limite(r):
    blob = (r.stdout + r.stderr).lower()
    return r.returncode != 0 and any(k in blob for k in LIMIT_KEYS)


def espera_cota():
    """Dorme e testa com uma chamada mínima até a cota voltar."""
    inicio = time.time()
    while time.time() - inicio < MAX_ESPERA:
        print(f"  sem cota ({datetime.now():%d/%m %H:%M}); testo de novo em {PROBE_EVERY // 60} min", flush=True)
        time.sleep(PROBE_EVERY)
        p = sh(["claude", "-p", "responda ok", "--model", "haiku", "--max-turns", "1"])
        if p.returncode == 0 and not limite(p):
            print("  cota voltou; retomando", flush=True)
            return True
    return False


def claude(model, text, log):
    while True:
        r = sh(["claude", "-p", text, "--model", model, "--max-turns", MAX_TURNS,
                "--permission-mode", "acceptEdits", "--allowedTools", TOOLS,
                "--output-format", "json"])
        with log.open("a") as f:
            f.write(f"\n--- {model} ---\n{r.stdout}\n{r.stderr}")
        if limite(r):
            if not espera_cota():
                sys.exit("A cota não voltou a tempo. Rode de novo: ele retoma de onde parou.")
            continue  # mesma tentativa, não conta como falha
        return r.returncode == 0


def gate():
    r = sh(GATE)
    return r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    tasks = [t for t in load_tasks() if (not a.only or t["id"] in a.only)]
    branch = "night/" + datetime.now().strftime("%Y%m%d")
    if not a.dry_run:
        sh(["git", "checkout", "-B", branch])

    for t in tasks:
        tid = t["id"]
        if tid in a.skip or state.get(tid) == "ok":
            continue
        falta = [d for d in t.get("depends_on", []) if state.get(str(d).zfill(2)) != "ok"]
        print(f"[{tid}] {t['title']} ({t['model']})", flush=True)
        if falta:
            state[tid] = "pulada"
            print(f"  pulada: depende de {falta}")
            continue
        if a.dry_run:
            state[tid] = "ok"
            continue

        log = LOGS / f"{tid}.log"
        log.write_text("")
        model, ok, tail = t["model"], False, ""
        plano = [model, model] + ([ESCALA[model]] if model in ESCALA else [])
        for n, m in enumerate(plano):
            extra = f"\n\nA tentativa anterior falhou na porta de qualidade:\n{tail}" if tail else ""
            claude(m, prompt(t, extra), log)
            ok, tail = gate()
            print(f"  tentativa {n + 1} com {m}: {'passou' if ok else 'falhou'}", flush=True)
            if ok:
                break

        state[tid] = "ok" if ok else "bloqueada"
        STATE.write_text(json.dumps(state, indent=1))
        if ok:
            sh(["git", "add", "-A", ":!runs-night"])
            sh(["git", "commit", "-q", "-m", f"Tarefa {tid}: {t['title']}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"])
            if os.environ.get("NIGHT_PUSH", "1") == "1":
                sh(["git", "push", "-q", "-u", "origin", branch])

    print("\nResumo:", json.dumps(state, indent=1))
    (LOGS / "RESUMO.md").write_text(
        "# Resumo da execução\n\n" + "\n".join(f"- {k}: {v}" for k, v in state.items()) + "\n")


if __name__ == "__main__":
    sys.exit(main())
