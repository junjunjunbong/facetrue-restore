# tune3: restored keyframe (GFPGAN v1.4 / CodeFormer) — negative result

Experiment: replace the tune2 kf_rid keyframe (LTXVAddGuide@frame0) with a photo-free face restoration
(GFPGAN v1.4, CodeFormer w=0.5) of the degraded frame 0, pasted on the no-photo LTX frame 0.
Verdict: do not use (see PROGRESS.md / summary.md).

Layout: scripts expect to live in `data/eval-pd/tune3/` (gitignored) and import `tune2/ridkf.py`.
Pipeline: prep3.py → fr_run.py (on GPU host, ComfyUI venv + spandrel 0.4.2 + spandrel_extra_arches 0.2.0)
→ paste3.py (/colormatch3.py) → runq.sh cfg/*.json (sweep3.py) → summarize3.py.
No media, weights or outputs are committed. Weights: GFPGANv1.4.pth (TencentARC/GFPGAN release v1.3.0),
codeformer.pth (sczhou/CodeFormer release v0.1.0, S-Lab License 1.0, non-commercial).
