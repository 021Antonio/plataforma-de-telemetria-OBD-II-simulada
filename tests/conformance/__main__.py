"""`python -m tests.conformance --host H --port P [--config perfil.json]`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .executor import Resultado, carregar_perfil, executar


def formatar(r: Resultado) -> str:
    if r.ok:
        return f"{r.indice:02d} {r.comando:<6} OK"
    return f"{r.indice:02d} {r.comando:<6} DIFERENÇA esperado={r.esperado!r} obtido={r.obtido!r}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests.conformance", description=__doc__)
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--config", type=Path, help="perfil JSON: ignorar e esperado por comando")
    ap.add_argument("--timeout", type=float, default=2.0, help="segundos por comando")
    args = ap.parse_args(argv)
    try:
        resultados = asyncio.run(
            executar(
                args.host, args.port, perfil=carregar_perfil(args.config), timeout=args.timeout
            )
        )
    except (OSError, TimeoutError, asyncio.IncompleteReadError) as exc:
        print(f"ERRO de conexão ou tempo esgotado: {exc!r}", file=sys.stderr)
        return 2
    for r in resultados:
        print(formatar(r))
    falhas = [r for r in resultados if not r.ok]
    print(f"{len(resultados) - len(falhas)}/{len(resultados)} OK, {len(falhas)} divergência(s)")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
