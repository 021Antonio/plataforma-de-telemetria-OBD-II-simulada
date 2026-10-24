"""E7: 2 execuções de 60 s, uma por HTTP e outra por MQTT (latência e perdas por canal)."""

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

NAME = "E7"
DURATION_S = 60.0
CHANNELS = ("http", "mqtt")


async def run(
    out_dir: Path, duration: float | None = None, *, plot: bool = False
) -> dict[str, Any]:
    results = []
    for ch in CHANNELS:
        sc = Scenario(label=ch, duration_s=duration or DURATION_S, channel=ch)
        results.append(await run_scenario(sc, out_dir, db_name=f"e7_{ch}.db"))
    doc = write_outputs(NAME, out_dir, results, config={"canais": list(CHANNELS)})
    if plot:
        plots.plot_e7(out_dir)
    return doc


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(__doc__ or NAME, argv)
    print_table(
        asyncio.run(run(args.out or default_out_dir(), args.duration, plot=not args.no_plots))
    )


if __name__ == "__main__":
    main()
