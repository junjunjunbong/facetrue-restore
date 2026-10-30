# Round 5 identity experiments (2026-10-30)

Plan: `PLAN.md`; step-by-step log with measured numbers: `PROGRESS.md`.
Scripts run from `data/eval-pd/tune5/` in the main checkout (data/ is git-ignored); manifests live in `data/eval-pd/`.

- `sweep5.py` — sweep runner (adds: `adv`/`mask` attention-masked photo guide, `att_amp` photo-only attention >1 via `gpu/ft5_attn.py`, `photo_cfg` photo-only guidance, `keyframe: file` for Qwen keyframes).
- `diag_m.py` — Michelle diagnosis (no GPU) → `diag/michelle_diag.json`.
- `qual.py` + `lpips_np.py` — reject-rule metrics: face LPIPS vs clean, motion-compensated temporal error f80–96.
- `qwenkf.py` — Qwen-Image-Edit-2511 pose-matched frame-0 keyframes.
- `gpu/ft5_attn.py` — tiny ComfyUI node (installed as `custom_nodes/ft5_attn.py` on the 5090). `gpu/pdl.sh` — parallel ranged download.

## Results, seed 42, Obama + Michelle (SFace cosine to clean, mean over f0,8,…,96)

| run | O correct | O wrong | O none | M correct | M wrong | M none | mean c−none | c−w (O / M) | LPIPS O / M | terr O / M |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline run-97-strong | 0.8607 | 0.6937 | 0.7277 | 0.8038 | 0.7834 | 0.7728 | +0.082 | +0.167 / +0.020 | 0.1586 / 0.2267 | 2.069 / 1.210 |
| A1 adv+mask | 0.8629 | – | (reused) | 0.8068 | – | (reused) | – | – | – | – |
| A2 mask grow 1.5 / feather 0.1 | 0.8618 | – | (reused) | 0.8105 | – | (reused) | – | +0.155 / +0.020 | 0.1604 / 0.2268 | 2.042 / 1.193 |
| C α=0.25 (all 8 steps) | 0.8609 | – | (reused) | 0.7885 | – | (reused) | – | +0.195 / +0.045 | 0.1606 / 0.2304 | 2.104 / 1.266 |
| amp 1.25 (photo-only attention) | 0.8525 | – | (reused) | 0.8171 | – | (reused) | +0.0025 vs base | +0.159 / +0.050 | 0.1590 / 0.2323 | 2.034 / 1.177 |
| amp 1.5 | 0.8486 | – | (reused) | 0.8121 | – | (reused) | −0.002 vs base | – | 0.1586 / 0.2288 | 1.997 / 1.167 |
| B Qwen kf 0.8 | 0.8457 | 0.6772 | 0.8073 | 0.8005 | 0.7747 | 0.7325 | +0.053 | +0.168 / +0.026 | 0.1491 / 0.2290 | 1.762 / 1.012 |
| B Qwen kf 0.6 (pop retry) | 0.8461 | 0.6844 | 0.8208 | 0.8021 | 0.7899 | 0.7705 | +0.028 | +0.162 / +0.012 | 0.1445 / 0.2342 | 1.784 / 1.051 |

Clean terr: O 1.223, M 0.753. Bar: mean c−none ≥ +0.12 (s42 & s7), correct > wrong everywhere, no pop, absolute correct rises, LPIPS +<0.02, terr +<10%.

**Verdict: everything fails on identity gain; nothing is expanded to s7, 2x2, or videos.** B: the kf 0.8 run pops at f0 (O correct 0.69 vs base 0.82); at 0.6 the pop is gone, but correct drops vs baseline (O −0.015, M −0.002). Qwen also lifts the none arm (O none +0.09), and its correct keyframe is only 0.741 (O) / 0.580 (M) vs clean f0 (`kfcos.py`).
