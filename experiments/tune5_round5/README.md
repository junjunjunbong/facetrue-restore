# Round 5 identity experiments (2026-10-30)

Plan: `PLAN.md`; step-by-step log with measured numbers: `PROGRESS.md`.
Scripts run from `data/eval-pd/tune5/` in the main checkout (data/ is git-ignored); manifests live in `data/eval-pd/`.

- `sweep5.py` — sweep runner (adds: `adv`/`mask` attention-masked photo guide, `att_amp` photo-only attention >1 via `gpu/ft5_attn.py`, `photo_cfg` photo-only guidance, `keyframe: file` for Qwen keyframes).
- `diag_m.py` — Michelle diagnosis (no GPU) → `diag/michelle_diag.json`.
- `qual.py` + `lpips_np.py` — reject-rule metrics: face LPIPS vs clean, motion-compensated temporal error f80–96.
- `qwenkf.py` — Qwen-Image-Edit-2511 pose-matched frame-0 keyframes.
- `gpu/ft5_attn.py` — tiny ComfyUI node (installed as `custom_nodes/ft5_attn.py` on the 5090). `gpu/pdl.sh` — parallel ranged download.
