"""
merge_datasets.py — Merge multiple robomimic HDF5 demo files into one training set.

Used to build a GENERALIST grasp dataset across FactorySorting scenes
(L1 containers + L3/L5 totes + L4 rotated containers), so the retrained BC policy
stops overfitting the L1 layout. Demos are copied verbatim and renumbered;
`num_samples`/`total` attrs are ensured; `env_args` is taken from the first file
(harmless — training runs with rollouts disabled).

Usage:
  python pipeline\\merge_datasets.py --out pipeline\\collected\\merged_grasp.hdf5 <in1.hdf5> <in2.hdf5> ...
  python pipeline\\merge_datasets.py --out ... --auto   # newest file per level tag under collected/raw + L1 set
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py

APP_DIR = Path(__file__).resolve().parents[1]


def merge(inputs: list[Path], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    total = 0
    with h5py.File(str(out), "w") as fo:
        data_out = fo.create_group("data")
        for idx, src in enumerate(inputs):
            with h5py.File(str(src), "r") as fi:
                di = fi["data"]
                if idx == 0:
                    for k, v in di.attrs.items():
                        data_out.attrs[k] = v
                for ep in list(di.keys()):
                    g = di[ep]
                    name = f"demo_{n}"
                    fi.copy(g, data_out, name=name)
                    if "num_samples" not in data_out[name].attrs:
                        data_out[name].attrs["num_samples"] = int(g["actions"].shape[0])
                    total += int(data_out[name].attrs["num_samples"])
                    n += 1
            print(f"  + {src.name}: merged (running demos={n})")
        data_out.attrs["total"] = total
    print(f"\nWrote {out}  demos={n}  total_samples={total}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("inputs", nargs="*", type=Path)
    args = ap.parse_args()
    if not args.inputs:
        print("no input files given")
        return 2
    for p in args.inputs:
        if not p.exists():
            print(f"missing: {p}")
            return 2
    merge(list(args.inputs), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
