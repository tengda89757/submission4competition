"""diff_ckpt.py — Compare structure/normalization between two robomimic checkpoints."""
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
for _p in (APP_DIR / "src", APP_DIR, APP_DIR / "robomimic", APP_DIR / "robosuite" / "robosuite"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import json
import numpy as np
import torch

a_path = Path(sys.argv[1])
b_path = Path(sys.argv[2])


def load(p):
    return torch.load(str(p), map_location="cpu", weights_only=False)


def summarize(tag, ck):
    print(f"\n===== {tag}: {Path(str(tag)).name} =====")
    print("keys:", sorted(ck.keys()))
    cfg = json.loads(ck["config"]) if isinstance(ck.get("config"), str) else ck.get("config", {})
    tr = cfg.get("train", {})
    al = cfg.get("algo", {})
    print("algo_name:", ck.get("algo_name"))
    print("train.action_keys:", tr.get("action_keys"))
    print("train.action_config keys:", list((tr.get("action_config") or {}).keys()))
    for k, v in (tr.get("action_config") or {}).items():
        print(f"   action_config[{k}] = {v}")
    print("train.seq_length:", tr.get("seq_length"), " frame_stack:", tr.get("frame_stack"))
    print("train.hdf5_normalize_obs:", tr.get("hdf5_normalize_obs"))
    print("algo.gmm/rnn/transformer flags:",
          {k: al.get(k) for k in ("gmm", "rnn", "transformer") if k in al})
    ans = ck.get("action_normalization_stats")
    if ans is None:
        print("action_normalization_stats: None")
    else:
        for key, st in ans.items():
            for name, arr in st.items():
                arr = np.asarray(arr).reshape(-1)
                print(f"  ANS[{key}][{name}] shape={arr.shape} min={arr.min():.4f} max={arr.max():.4f} mean={arr.mean():.4f}")
    on = ck.get("obs_normalization_stats")
    print("obs_normalization_stats:", "None" if on is None else "present")
    env_meta = ck.get("env_metadata")
    if env_meta:
        em = env_meta if isinstance(env_meta, dict) else {}
        print("env_metadata.env_name:", em.get("env_name"))


A = load(a_path)
B = load(b_path)
summarize(a_path, A)
summarize(b_path, B)
