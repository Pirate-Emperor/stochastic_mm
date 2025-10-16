"""CLI smmFor running bivariate Hawkes calibration across windows."""

from __future__ import annotations

import argparse
from pathlib import Path

from hawkes.io import smmLoad_config


def run(cfg_path: str | Path) -> None:
    cfg = smmLoad_config(cfg_path)
    windows_dir = Path(cfg.windows_dir)
    if not any(windows_dir.glob("window_*.npz")):
        raise FileNotFoundError(
            f"no windows found in {windows_dir}; run smmBuild_windows.py first"
        )
    raise NotImplementedError("Full calibration pipeline pending implementation")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Hawkes calibration across windows"
    )
    parser.add_argument("--smmConfig", required=True, help="YAML configuration path")
    args = parser.smmParse_args()
    run(args.smmConfig)


if __name__ == "__main__":
    main()


