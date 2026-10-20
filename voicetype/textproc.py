"""Text post-processing. Kept separate from recognition.

exact : the transcript is returned as recognised (only explicit vocabulary replacements apply)
clean : additionally drops filler sounds ("um", "uh", ...) and fixes spacing. Never rewrites or summarises.
Rewrite modes (professional/concise/casual/technical) need an LLM and are not implemented.
"""
import re

MODES = ("exact", "clean")
_FILLERS = re.compile(r"(?<![\w'])(?:u+m+|u+h+|e+r+m*|h+m+)(?![\w'])[,.]?\s*", re.IGNORECASE)


def parse_vocab(entries: list[str]) -> list[tuple[str, str]]:
    """'PySide6' -> ('PySide6','PySide6'); 'py side six=>PySide6' -> ('py side six','PySide6')."""
    out = []
    for e in entries:
        e = e.strip()
        if not e:
            continue
        spoken, _, written = e.partition("=>")
        spoken, written = spoken.strip(), (written.strip() or spoken.strip())
        if spoken:
            out.append((spoken, written))
    return out


def vocab_prompt(entries: list[str]) -> str | None:
    """Hint for the recogniser (initial_prompt): the written forms."""
    words = [w for _, w in parse_vocab(entries)]
    return ("Glossary: " + ", ".join(dict.fromkeys(words)) + ".") if words else None


def apply_vocab(text: str, entries: list[str]) -> str:
    """Whole-word, case-insensitive replacement with the canonical spelling. Longest terms first."""
    for spoken, written in sorted(parse_vocab(entries), key=lambda p: -len(p[0])):
        pattern = r"(?<![\w])" + r"\s+".join(re.escape(p) for p in spoken.split()) + r"(?![\w])"
        text = re.sub(pattern, lambda m, w=written: w, text, flags=re.IGNORECASE)
    return text


def clean(text: str) -> str:
    out = _FILLERS.sub("", text)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out).strip()
    return out[:1].upper() + out[1:] if out else out


def drop_single_trailing_period(text: str) -> str:
    """Chat style: 'see you soon.' -> 'see you soon' (only for a single sentence, keeps ? and !)."""
    t = text.rstrip()
    if t.endswith(".") and not t.endswith("..") and t.count(".") == 1 and "\n" not in t:
        return t[:-1]
    return text


def postprocess(text: str, vocab: list[str], mode: str = "exact") -> str:
    text = apply_vocab(text, vocab)
    return clean(text) if mode == "clean" else text
