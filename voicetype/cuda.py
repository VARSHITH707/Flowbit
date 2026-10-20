"""Make pip-installed cuBLAS/cuDNN DLLs visible to CTranslate2 (Windows).

Searches site-packages/nvidia/*/bin (development install) and <app folder>/nvidia/*/bin (PyInstaller build).
"""
import os
import site
import sys
from pathlib import Path


def _roots() -> list[Path]:
    roots = [Path(sp, "nvidia") for sp in site.getsitepackages()]
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        roots += [base / "nvidia", Path(sys.executable).parent / "nvidia"]
    return roots


def add_cuda_dll_dirs() -> list[str]:
    added = []
    for root in _roots():
        for bin_dir in sorted(root.glob("*/bin")):
            if str(bin_dir) in added:
                continue
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
            added.append(str(bin_dir))
    return added
