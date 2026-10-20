"""Model availability + download with progress (Hugging Face cache).

Each selectable model is pinned to one commit of its repository, so a later change to the repo's
`main` branch cannot swap the weights we load. Update REVISIONS deliberately (and re-run the benchmark)
when you want a newer model build.
"""
from pathlib import Path

import huggingface_hub
from faster_whisper.utils import _MODELS  # size -> HF repo id

MODELS = {"small": "~0.5 GB", "medium": "~1.5 GB", "large-v3-turbo": "~1.6 GB"}
DEFAULT_MODEL = "large-v3-turbo"
REVISIONS = {  # the commits that were benchmarked (docs/benchmark.md)
    "small": "536b0662742c02347bc0e980a01041f333bce120",
    "medium": "08e178d48790749d25932bbc082711ddcfdfbc4f",
    "large-v3-turbo": "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
}
_FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]


def _fetch(model: str, **kw) -> str:
    if model not in _MODELS:
        raise ValueError(f"Unknown model {model!r}")
    return huggingface_hub.snapshot_download(_MODELS[model], revision=REVISIONS.get(model), allow_patterns=_FILES, **kw)


def local_path(model: str) -> Path:
    """Folder of the downloaded, pinned model. Raises if it is not on disk."""
    return Path(_fetch(model, local_files_only=True))


def is_available(model: str) -> bool:
    try:
        return (local_path(model) / "model.bin").exists()
    except Exception:
        return False


def model_ref(model: str) -> str:
    """What to hand to WhisperModel: the pinned local folder if present, else the plain name."""
    try:
        return str(local_path(model))
    except Exception:
        return model


def download(model: str, on_progress=None) -> str:
    """Download `model`; on_progress(done_bytes, total_bytes) called as files arrive."""
    from tqdm.auto import tqdm

    class _Bar(tqdm):
        def update(self, n=1):
            r = super().update(n)
            if on_progress and self.total and self.unit == "B":
                on_progress(self.n, self.total)
            return r

    return _fetch(model, tqdm_class=_Bar)


def delete(model: str) -> bool:
    """Remove a downloaded model from the Hugging Face cache. Only touches the model's own cache folder."""
    import shutil
    try:
        snap = local_path(model)  # .../models--org--name/snapshots/<rev>
    except Exception:
        return False
    root = snap.parents[1]
    if root.name != "models--" + _MODELS[model].replace("/", "--"):
        raise ValueError(f"Refusing to delete unexpected path {root}")
    shutil.rmtree(root)
    return True
