from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from _common import load_publishing_config, run_cli
from ensure_user_resources import ensure_publishing_repository


def main(argv: Sequence[str] | None = None) -> int:
    os.environ["AILERON_PUBLISH_OPERATION"] = "upgrade"
    parser = argparse.ArgumentParser(description="Upgrade the managed Canvas publishing scaffold.")
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.parse_args(argv)
    return run_cli(
        lambda: ensure_publishing_repository(
            load_publishing_config(),
            mutate=True,
            upgrade=True,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
