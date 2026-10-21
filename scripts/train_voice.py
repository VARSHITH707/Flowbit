"""Fine-tune whisper-large-v3-turbo on your voice (step 2 of 3), then convert it for VoiceType.

  .\\.venv-train\\Scripts\\python.exe scripts\\train_voice.py
  options: --epochs 4 --lr 1e-4 --rank 32 --language en --name my-voice --max-steps N (quick pipeline test)

Reads the clips you recorded (userdata\\voice\\dataset.jsonl). Every 10th clip is held out and never trained on,
so scripts\\eval_voice.py can measure the result honestly. LoRA (small adapter layers) keeps it inside 8 GB of
GPU memory; quit VoiceType and the recorder first so the GPU is free.

Writes models\\<name>\\ (CTranslate2, what VoiceType loads) with adapter\\ (the trained LoRA weights) and
training.json (settings, which clips were held out, losses).
"""
import argparse
import json
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import _projtmp  # noqa: E402,F401  (temp files stay in the project)
import torch  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402
from transformers import WhisperForConditionalGeneration, WhisperProcessor  # noqa: E402

from voicetype import voicedata as vd  # noqa: E402
from voicetype.config import MODELS_DIR  # noqa: E402

BASE, BASE_REV = "openai/whisper-large-v3-turbo", "41f01f3fe87f28c78e2fbf8b568835947dd65ed9"
HOLDOUT_EVERY = 10


def split(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Every 10th clip (by recording order) is held out; with fewer than 10 clips, the last one is."""
    held = [e for i, e in enumerate(entries) if i % HOLDOUT_EVERY == HOLDOUT_EVERY - 1] or entries[-1:]
    return [e for e in entries if e not in held], held


def encode(entries, processor) -> list[tuple[torch.Tensor, list[int]]]:
    out, sot = [], processor.tokenizer.convert_tokens_to_ids("<|startoftranscript|>")
    for e in entries:
        feats = processor.feature_extractor(vd.read_audio(e), sampling_rate=vd.SAMPLE_RATE,
                                            return_tensors="pt").input_features[0]
        ids = processor.tokenizer(" " + e["text"]).input_ids  # <|sot|><|lang|><|transcribe|><|notimestamps|> text <|eot|>
        out.append((feats, ids[1:] if ids[0] == sot else ids))  # the model adds <|sot|> itself when shifting labels
    return out


def batches(data, size: int, shuffle: bool):
    order = list(range(len(data)))
    if shuffle:
        random.shuffle(order)
    for i in range(0, len(order), size):
        chunk = [data[j] for j in order[i:i + size]]
        n = max(len(ids) for _, ids in chunk)
        labels = torch.tensor([ids + [-100] * (n - len(ids)) for _, ids in chunk])
        yield torch.stack([f for f, _ in chunk]), labels


def mean_loss(model, data, dev) -> float:
    model.eval()
    total = 0.0
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
        for feats, labels in batches(data, 4, False):
            total += model(input_features=feats.to(dev, torch.bfloat16), labels=labels.to(dev)).loss.item() * len(labels)
    model.train()
    return total / max(1, len(data))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="my-voice")
    ap.add_argument("--language", default="en")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=8, help="batches per optimizer step (effective batch = batch x accum)")
    ap.add_argument("--max-steps", type=int, default=0, help="stop after N optimizer steps (pipeline test)")
    a = ap.parse_args()

    if not torch.cuda.is_available():
        sys.exit("No CUDA GPU visible to PyTorch; training on the CPU would take days.")
    entries = vd.load()
    if len(entries) < 2:
        sys.exit("Record some clips first: .venv\\Scripts\\python.exe scripts\\record_voice.py")
    train, held = split(entries)
    mins = sum(e["seconds"] for e in train) / 60
    print(f"{len(train)} training clips ({mins:.1f} min), {len(held)} held out for evaluation")
    if mins < 20:
        print("Note: under 20 minutes of audio; the result may not beat the base model. More recordings help.")

    random.seed(0)
    torch.manual_seed(0)
    dev = "cuda"
    kw = {"revision": BASE_REV, "cache_dir": MODELS_DIR, "local_files_only": True}
    processor = WhisperProcessor.from_pretrained(BASE, **kw)
    processor.tokenizer.set_prefix_tokens(language=a.language, task="transcribe", predict_timestamps=False)
    model = WhisperForConditionalGeneration.from_pretrained(BASE, torch_dtype=torch.bfloat16, **kw)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    lora = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05,
                      target_modules=["q_proj", "k_proj", "v_proj", "out_proj"])
    model = get_peft_model(model, lora).to(dev)
    model.print_trainable_parameters()

    t0 = time.time()
    tr, ho = encode(train, processor), encode(held, processor)
    print(f"Prepared audio in {time.time() - t0:.0f} s")
    steps_per_epoch = max(1, -(-len(tr) // (a.batch * a.accum)))
    total = steps_per_epoch * a.epochs if not a.max_steps else a.max_steps
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.01)
    warm = max(1, total // 10)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / warm) * max(0.0, 1 - s / total))
    log = {"held_loss_before": mean_loss(model, ho, dev)}
    print(f"Held-out loss before: {log['held_loss_before']:.3f}")

    step, done = 0, False
    model.train()
    for epoch in range(a.epochs):
        for i, (feats, labels) in enumerate(batches(tr, a.batch, True)):
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = model(input_features=feats.to(dev, torch.bfloat16), labels=labels.to(dev)).loss / a.accum
            loss.backward()
            if (i + 1) % a.accum == 0 or (i + 1) * a.batch >= len(tr):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                step += 1
                print(f"epoch {epoch + 1} step {step}/{total} loss {loss.item() * a.accum:.3f} "
                      f"({time.time() - t0:.0f} s, GPU {torch.cuda.max_memory_allocated() / 2**30:.1f} GB peak)")
                if step >= total:
                    done = True
                    break
        log[f"held_loss_epoch{epoch + 1}"] = mean_loss(model, ho, dev)
        print(f"Held-out loss after epoch {epoch + 1}: {log[f'held_loss_epoch{epoch + 1}']:.3f}")
        if done:
            break

    out = MODELS_DIR / a.name
    tmp = MODELS_DIR / f"{a.name}-hf"
    if out.exists():
        shutil.rmtree(out)
    model.save_pretrained(str(out / "adapter"))
    merged = model.merge_and_unload()
    merged.config.use_cache = True
    merged.to(torch.float16).save_pretrained(str(tmp))
    processor.save_pretrained(str(tmp))
    del model, merged
    torch.cuda.empty_cache()

    import ctranslate2
    ctranslate2.converters.TransformersConverter(str(tmp), copy_files=["tokenizer.json", "preprocessor_config.json"]
                                                 ).convert(str(out), quantization="float16", force=True)
    shutil.rmtree(tmp)
    (out / "training.json").write_text(json.dumps({
        "base": BASE, "base_revision": BASE_REV, "language": a.language, "epochs": a.epochs, "lr": a.lr,
        "rank": a.rank, "batch": a.batch * a.accum, "steps": step, "train_clips": len(train),
        "train_minutes": round(mins, 1), "held_out": [e["audio"] for e in held], "losses": log,
        "seconds": round(time.time() - t0), "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2), encoding="utf-8")
    print(f"Done in {(time.time() - t0) / 60:.1f} min -> {out}\nNext: .venv\\Scripts\\python.exe scripts\\eval_voice.py")


if __name__ == "__main__":
    main()
