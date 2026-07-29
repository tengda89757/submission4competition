"""
train_bc.py — Retrain the BC grasp policy on GPU and install it as model_epoch_500.pth.

Why: the official only ships model_epoch_150.pth and its robustness is weak; the
code loads `grasp_policy.checkpoint_path` (model_epoch_500.pth) first and falls
back to 150. Participants must train their own replacement. This wrapper:

  1. Reads the robomimic config + algo embedded INSIDE model_epoch_150.pth, so the
     retrained network is architecturally identical (same obs keys / action space)
     and will load in load_factory_sorting_evalization.py unchanged.
  2. Overrides dataset path, output dir, num_epochs (chat: ~3000 works, 2000 did
     not), save cadence, workers=0 (Windows), CUDA device.
  3. Trains via the vendored robomimic scripts/train.py.
  4. Copies the newest resulting model_epoch_*.pth to
     robosuite/robosuite/model_epoch_500.pth so app.py picks it up automatically.

Examples:
  # quick end-to-end smoke test (2 epochs, no rollout) — validates the pipeline
  .venv\\Scripts\\python pipeline\\train_bc.py --debug

  # full retrain
  .venv\\Scripts\\python pipeline\\train_bc.py --epochs 3000 --save-every 150 --device cuda:0
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]          # JCIIOT
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# The bundled table_setup_from_dishwasher_sample.hdf5 is a robomimic FORMAT SAMPLE
# from an unrelated iGibson task (env_name=SemanticOrganizeAndFetch) — it is NOT
# factory-sorting demo data. Real training data must be COLLECTED first with
# pipeline/collect_demos.ps1 (scripted expert grasps in the FactorySorting scene).
SAMPLE_HDF5 = APP_DIR / "robosuite" / "dataset" / "table_setup_from_dishwasher_sample.hdf5"
DEFAULT_DATASET = APP_DIR / "pipeline" / "collected" / "factory_sorting_l1_grasp.hdf5"
DEFAULT_BASE_CKPT = APP_DIR / "robosuite" / "robosuite" / "model_epoch_150.pth"
DEFAULT_OUTPUT = APP_DIR / "pipeline" / "train_output"
INSTALL_TARGET = APP_DIR / "robosuite" / "robosuite" / "model_epoch_500.pth"


def _dataset_env_name(path: Path) -> str:
    """Return the env_name recorded in a robomimic hdf5 (data.attrs['env_args'])."""
    try:
        import h5py
        with h5py.File(str(path), "r") as f:
            ea = f["data"].attrs.get("env_args")
        if isinstance(ea, bytes):
            ea = ea.decode()
        return json.loads(ea).get("env_name", "") if isinstance(ea, str) else ""
    except Exception:
        return ""


def ensure_robomimic_attrs(path: Path) -> None:
    """The collector omits per-demo `num_samples` (and `data.total`) that robomimic's
    SequenceDataset requires. Add them idempotently from each demo's action length."""
    import h5py
    with h5py.File(str(path), "a") as f:
        data = f["data"]
        total = 0
        for ep in list(data.keys()):
            g = data[ep]
            if "num_samples" not in g.attrs:
                g.attrs["num_samples"] = int(g["actions"].shape[0])
            total += int(g.attrs["num_samples"])
        if "total" not in data.attrs:
            data.attrs["total"] = total


def _import_train_module():
    """Import robomimic/scripts/train.py by file path (avoids name clashes)."""
    path = APP_DIR / "robomimic" / "scripts" / "train.py"
    spec = importlib.util.spec_from_file_location("rm_train_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_config(base_ckpt: Path, dataset: Path, output_dir: Path,
                 epochs: int, save_every: int, rollout: bool, debug: bool):
    import torch
    from robomimic.config import config_factory

    ckpt = torch.load(str(base_ckpt), map_location="cpu", weights_only=False)
    algo_name = ckpt.get("algo_name", "bc")
    cfg_json = ckpt.get("config")
    if cfg_json is None:
        raise RuntimeError(
            f"{base_ckpt.name} has no embedded 'config'; cannot reproduce its architecture."
        )
    dic = json.loads(cfg_json) if isinstance(cfg_json, str) else cfg_json
    config = config_factory(algo_name, dic=dic)

    with config.values_unlocked():
        config.train.data = str(dataset)
        config.train.output_dir = str(output_dir)
        config.train.num_data_workers = 0          # Windows-safe (no fork)
        config.train.hdf5_filter_key = None        # use all demos (collected data has no train/valid mask)
        config.train.hdf5_validation_filter_key = None
        config.experiment.name = f"jciiot_bc_retrain_{time.strftime('%Y%m%d_%H%M%S')}"
        config.experiment.save.enabled = True
        config.experiment.save.every_n_epochs = save_every
        config.experiment.logging.terminal_output_to_txt = False
        # Rollouts during training spin up a MuJoCo env each eval — expensive.
        config.experiment.rollout.enabled = bool(rollout)
        if not rollout:
            config.experiment.validate = False
        if debug:
            config.train.num_epochs = 2
            config.train.batch_size = min(int(config.train.batch_size), 16)
            config.experiment.save.every_n_epochs = 1
            config.experiment.epoch_every_n_steps = 5
            config.experiment.rollout.enabled = False
            config.experiment.validate = False
        else:
            config.train.num_epochs = epochs
    return config, algo_name


def install_best_checkpoint(output_dir: Path) -> Path | None:
    models = sorted(output_dir.rglob("model_epoch_*.pth"), key=lambda p: p.stat().st_mtime)
    if not models:
        models = sorted(output_dir.rglob("*.pth"), key=lambda p: p.stat().st_mtime)
    if not models:
        return None
    newest = models[-1]
    INSTALL_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(newest, INSTALL_TARGET)
    return newest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Retrain BC grasp policy -> model_epoch_500.pth")
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--base-ckpt", type=Path, default=DEFAULT_BASE_CKPT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--epochs", type=int, default=3000)
    ap.add_argument("--save-every", type=int, default=150)
    ap.add_argument("--device", type=str, default="cuda:0")
    ap.add_argument("--rollout", action="store_true", help="run MuJoCo eval rollouts during training (slow)")
    ap.add_argument("--debug", action="store_true", help="2-epoch smoke test to validate the pipeline")
    ap.add_argument("--no-install", action="store_true", help="do not copy result to model_epoch_500.pth")
    args = ap.parse_args(argv)

    if not args.dataset.exists():
        print(f"ERROR: dataset not found: {args.dataset}\n"
              f"Run: powershell -ExecutionPolicy Bypass -File pipeline\\fetch_assets.ps1 -Only hdf5")
        return 2
    if not args.base_ckpt.exists():
        print(f"ERROR: base checkpoint not found: {args.base_ckpt}\n"
              f"Run: powershell -ExecutionPolicy Bypass -File pipeline\\fetch_assets.ps1 -Only pth")
        return 2

    env_name = _dataset_env_name(args.dataset)
    if env_name and "factorysorting" not in env_name.replace("_", "").lower():
        print(f"ERROR: dataset '{args.dataset.name}' was collected from env '{env_name}', not a\n"
              f"FactorySorting scene. The bundled table_setup_from_dishwasher_sample.hdf5 is only a\n"
              f"robomimic FORMAT SAMPLE (iGibson SemanticOrganizeAndFetch) and CANNOT train the grasp\n"
              f"policy. Collect real demos first:\n"
              f"  powershell -ExecutionPolicy Bypass -File pipeline\\collect_demos.ps1 -NumRollouts 50")
        return 2

    ensure_robomimic_attrs(args.dataset)

    import torch
    import robomimic.utils.torch_utils as TorchUtils

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        print("WARNING: CUDA not available; falling back to CPU (training will be very slow).")
        device = TorchUtils.get_torch_device(try_to_use_cuda=False)
    else:
        device = torch.device(args.device) if args.device != "auto" else \
            TorchUtils.get_torch_device(try_to_use_cuda=True)

    print(f"Device: {device}")
    print(f"Base checkpoint: {args.base_ckpt}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output}")

    config, algo_name = build_config(
        args.base_ckpt, args.dataset, args.output,
        args.epochs, args.save_every, args.rollout, args.debug,
    )
    print(f"algo={algo_name}  num_epochs={config.train.num_epochs}  "
          f"batch={config.train.batch_size}  save_every={config.experiment.save.every_n_epochs}  "
          f"rollout={config.experiment.rollout.enabled}")

    start = time.time()
    rm_train = _import_train_module()
    rm_train.train(config, device=device)
    print(f"\nTraining finished in {time.time() - start:.1f}s")

    if not args.no_install:
        installed = install_best_checkpoint(args.output)
        if installed:
            print(f"Installed newest checkpoint:\n  {installed}\n  -> {INSTALL_TARGET}")
        else:
            print("WARNING: no .pth produced; nothing installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
