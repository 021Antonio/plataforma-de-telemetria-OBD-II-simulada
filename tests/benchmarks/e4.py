"""E4: perda de 0, 1, 5 e 10% dos quadros de requisição (timeouts, recuperação, taxa efetiva)."""

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

NAME = "E4"
DURATION_S = 30.0  # a spec não fixa a duração: mesma do E2
LOSSES = (0.0, 0.01, 0.05, 0.10)


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    results = []
    for p in LOSSES:
        sc = Scenario(label=f"{round(p * 100)}%", duration_s=duration or DURATION_S, frame_loss=p)
        results.append(await run_scenario(sc, out_dir, db_name=f"e4_{round(p * 100)}pct.db"))
    doc = write_outputs(NAME, out_dir, results, config={"perdas": list(LOSSES)})
    if plot:
        plots.plot_e4(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(
        asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    )


if __name__ == "__main__":
    main()
