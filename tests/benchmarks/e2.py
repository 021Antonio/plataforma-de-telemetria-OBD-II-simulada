"""E2: 4 execuções de 30 s com a ECU em 0, 10, 25 e 50 ms (ciclo e taxa em função do atraso)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import plots
from .runner import (
    Scenario,
    default_out_dir,
    parse_args,
    print_table,
    run_scenario,
    write_outputs,
)

NAME = "E2"
DURATION_S = 30.0
DELAYS_MS = (0, 10, 25, 50)  # atraso fixo (mín = máx)


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    results = []
    for d in DELAYS_MS:
        sc = Scenario(label=f"{d}ms", duration_s=duration or DURATION_S, delay_ms=(d, d))
        results.append(await run_scenario(sc, out_dir, db_name=f"e2_{d}ms.db"))
    doc = write_outputs(NAME, out_dir, results, config={"atrasos_ms": list(DELAYS_MS)})
    if plot:
        plots.plot_e2(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(
        asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    )


if __name__ == "__main__":
    main()
