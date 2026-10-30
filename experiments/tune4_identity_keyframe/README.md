# tune4: identity attempts, round 4 (10/30)

Scripts used for round-4 identity experiments. They were run from `data/eval-pd/tune4/` in the main checkout, so the relative paths assume that location. This folder holds no media, weights or outputs.

- `sweep4.py`: eval sweep (tune3 sweep3 + `ref_extra_idx/strength` for extra copies of the reference guide, `keyframe: file` for an external frame-0 keyframe, `ref2` for a second photo of each arm as its own guide).
- `prep4.py`, `paste4.py`: prepare LTX frame-0 crops and paste and score generated keyframes (gate: keyframe SFace > 0.726).
- `summarize4.py`: tables. `runq.sh`, `go.sh`, `chainC.sh`: nohup runners.
- `gpu/ipa_kf.py`: SDXL img2img + IP-Adapter plus-face keyframe (RealVisXL V4.0 openrail++, h94/IP-Adapter Apache-2.0).
- `gpu/iid_kf.py`: InstantID img2img keyframe (InstantX/InstantID Apache-2.0, **insightface antelopev2 is non-commercial**, so this cannot ship).
- `cfg/`: a1–a4 (A), b1 (B), c1–c2 (C).

Measured results, verdicts, licenses and photo sources are in `PROGRESS.md`.
