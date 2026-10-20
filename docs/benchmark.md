# Benchmark (RTX 4060 Laptop 8 GB, faster-whisper / CTranslate2 4.8.3, GPU int8_float16)
Clips: Windows TTS (clean, synthetic) with known reference text: short 7.1 s, long 340.8 s (5.7 min). Language forced to en. Script: `scripts/bench_one.py` (one process per model). Raw: `data/bench_raw.txt`.

| Model | Cached load | Short (7 s) | Long (5.7 min) | Long WER | VRAM (+) | RAM |
|---|---|---|---|---|---|---|
| small | 1.5 s | 0.23 s (31x) | 8.3 s (41x) | 5.8% | ~420 MB | 783 MB |
| medium | n/m* | 0.48 s (15x) | 17.9 s (19x) | 1.9% | ~1125 MB | 805 MB |
| large-v3-turbo | 3.3 s | 0.30 s (24x) | 8.4 s (41x) | 1.9% | ~1190 MB | 805 MB |

*medium's first load (44 s) included the download; cached load not re-measured. Large-v3-turbo first load (47.5 s) included download.
Short-clip WER was 0% for all. Download sizes (approx, not measured here): small ~0.5 GB, medium ~1.5 GB, turbo ~1.6 GB.

## Decision
Default **large-v3-turbo** (same speed as small on the long clip, accuracy of medium, ~1.2 GB VRAM of 8 GB). Offer **small** as the fast/low-resource option.

## Caveats (honest)
- TTS audio is much cleaner than a real microphone. WER on real speech, accents, noise will be worse; these numbers rank models, they don't predict real-world accuracy.
- The 5.8% small WER is mostly TTS-specific terms (e.g. "PySide six", "PostgreSQL"); not investigated further.
- VRAM is the nvidia-smi delta over a 759 MB baseline (desktop use), not a per-process figure.
- Not yet tested: noise, accents, auto language detection (item 2.7).
