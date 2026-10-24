"""E3: 4 execuções de 20 s com 1, 3, 5 e 10 PIDs (taxa por PID e leituras por segundo)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import plots
from .runner import (
    TEN_PIDS,
    Scenario,
    default_out_dir,
    parse_args,
    print_table,
    run_scenario,
    write_outputs,
)

NAME = "E3"
DURATION_S = 20.0
PID_COUNTS = (1, 3, 5, 10)


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    results = []
    for n in PID_COUNTS:
        sc = Scenario(label=f"{n}pids", duration_s=duration or DURATION_S, pids=TEN_PIDS[:n])
        results.append(await run_scenario(sc, out_dir, db_name=f"e3_{n}pids.db"))
    doc = write_outputs(NAME, out_dir, results, config={"quantidades": list(PID_COUNTS)})
    if plot:
        plots.plot_e3(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(
        asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    )


if __name__ == "__main__":
    main()
