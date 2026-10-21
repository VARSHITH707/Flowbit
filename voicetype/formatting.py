"""Deterministic text formatting: Audio -> recognition -> SEGMENT JOIN -> FORMAT -> (optional AI) -> insert.

Measured cause of the punctuation problem (docs/formatting.md): Whisper itself returns long continuous speech
with almost no punctuation (e.g. 129 words, 0 marks), on every model size. Rules here fix what rules can fix
reliably (spacing, capitals, sentence ends, explicit lists and commands, numbers); restoring commas inside
pause-free run-on speech needs the local AI's punctuation pass (cleanup.punctuate), which may not change words.

Every function is pure, idempotent (formatting formatted text changes nothing) and never drops content.
"""
import re

PAUSE_SENTENCE_S = 0.8  # a gap this long between recognised segments ends a sentence when nothing else did


# ---------------------------------------------------------------- segments and spacing
def join_segments(segments) -> str:
    """Join recognised segments [(start_s, end_s, text)]. A long pause before a capitalised segment ends the
    previous sentence if Whisper did not; otherwise segments are joined with one space (never mechanically).
    Words that Whisper repeated at the start of a segment, because the two segments overlapped, are dropped."""
    out = ""
    prev_end = None
    for start, end, text in segments:
        t = " ".join(text.split())
        if out and t:
            t = _drop_overlap(out, t)
        if not t:
            continue
        if out:
            gap = start - prev_end if prev_end is not None else 0.0
            if gap >= PAUSE_SENTENCE_S and out[-1].isalnum() and t[0].isupper():
                out += "."
            out += "" if t[0] in ",.?!;:%)" else " "
        out += t
        prev_end = end
    return out


OVERLAP_MAX_WORDS = 4


def _drop_overlap(previous: str, segment: str) -> str:
    """Remove the first words of `segment` when they repeat the last words of `previous` (overlapping segments)."""
    prev = previous.split()
    words = segment.split()
    for k in range(min(OVERLAP_MAX_WORDS, len(prev), len(words)), 0, -1):
        if [w.lower().strip(".,?!") for w in prev[-k:]] == [w.lower().strip(".,?!") for w in words[:k]]:
            if k == 1 and words[0].lower().strip(".,?!") in INTENTIONAL:
                return segment  # a single intentional word ("very" very) is not an overlap
            return " ".join(words[k:])
    return segment


# Words people often say twice on purpose. Anything else said twice in a row is an accidental repeat.
INTENTIONAL = {"very", "really", "so", "no", "yes", "bye", "ha", "hah", "hey", "hi", "ok", "okay", "go", "little", "much",
               "more", "long", "far", "ever", "quite", "nah", "wow", "oh", "ah", "aha", "fine", "well", "hard", "fast",
               "ya", "mm", "uh", "um", "tick", "tock", "bam", "boom", "knock", "ding", "dong",
               "had", "that"}  # grammatical doubles: "we had had enough", "that that"
_WORD = re.compile(r"[A-Za-z][A-Za-z']*")


def remove_repeats(text: str) -> str:
    """'I I want to build this' -> 'I want to build this'; 'the app app is slow' -> 'the app is slow'.
    Only a word repeated immediately, not in INTENTIONAL, loses its extra copies. Digits, names with different
    spellings, and repeats separated by other words are never touched. Phrase repeats are left alone (too risky)."""
    out, last = [], None
    pos = 0
    for m in re.finditer(r"\S+", text):
        token = m.group(0)
        core = _WORD.fullmatch(token.strip(".,?!;:\"'")) and token.strip(".,?!;:\"'").lower()
        gap = text[pos:m.start()]
        pos = m.end()
        if core and core == last and core not in INTENTIONAL:
            # drop this copy; keep any punctuation the copy carried onto the kept word
            if token[-1:] in ".,?!;:" and out and out[-1][-1:] != token[-1:]:
                out[-1] = out[-1] + token[-1]
            continue
        out.append(gap + token if out else token)
        last = core
    return "".join(out)


_SPACE_BEFORE = re.compile(r"[ \t]+([,.?!;:%)\]])")
_SPACE_AFTER = re.compile(r"([,;:?!])(?=[^\W\d_])")  # "a,b" -> "a, b" (letters only: keeps 10:30 and 1,000)
_PERIOD_AFTER = re.compile(r"(?<=[^\W\d_]{2})\.(?=[A-Z][a-z])")  # "end.Next" -> "end. Next" (keeps e.g., U.S., 3.5)


def normalize_spacing(text: str) -> str:
    """Conservative: one space between words, none before punctuation, one after; line breaks kept."""
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = re.sub(r"[ \t]{2,}", " ", line).strip()
        s = _SPACE_BEFORE.sub(r"\1", s)
        s = re.sub(r"([(\[])\s+", r"\1", s)
        s = _SPACE_AFTER.sub(r"\1 ", s)
        s = _PERIOD_AFTER.sub(". ", s)
        s = re.sub(r"([,;:])\1+", r"\1", s)  # ",," -> ","
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# ---------------------------------------------------------------- capitals and sentence ends
_I = re.compile(r"\bi\b(?!\.\w)(?=$|[\s,.?!;:'’])")  # standalone "i", not "i.e."
_ITEM = r"(?:\d+\.\s+|- )"
WH = {"what", "why", "how", "who", "where", "when", "which", "whose"}
AUX = {"is", "are", "am", "was", "were", "can", "could", "would", "should", "do", "does", "did", "will", "shall", "may",
       "might", "have", "has", "had", "isn't", "aren't", "can't", "won't", "don't", "doesn't", "didn't", "wouldn't",
       "shouldn't", "couldn't"}
SUBJECTS = {"i", "you", "we", "they", "he", "she", "it", "this", "that", "there", "anyone", "someone", "everyone",
            "your", "my", "our", "the"}


def capitalize(text: str) -> str:
    """Capital letter at the start of each sentence, line and list item; standalone 'i' -> 'I'."""
    text = _I.sub("I", text)
    return re.sub(r"(^\s*" + _ITEM + r"?|[.?!]\s+|\n\s*" + _ITEM + r"?)([a-z])",
                  lambda m: m.group(1) + m.group(2).upper(), text)


def is_question(sentence: str) -> bool:
    """Conservative: 'can you ...', 'is it ...', 'what is ...', 'how do ...'. Not 'do it now', 'when I get home'."""
    w = [x.strip(",").lower() for x in sentence.split()[:2]]
    if len(w) < 2 or (w[0] == "do" and w[1] in ("it", "this", "that", "the")):  # "do it now" is an instruction
        return False
    return (w[0] in AUX and w[1] in SUBJECTS) or (w[0] in WH and w[1] in AUX)


def end_sentences(text: str) -> str:
    """Every paragraph and list item ends with punctuation: '?' if it clearly opens as a question, else '.'."""
    out, lines = [], text.split("\n")
    for i, line in enumerate(lines):
        s = line.rstrip()
        heading = i < len(lines) - 1 and len(s.split()) <= 3 and not re.match(r"^" + _ITEM, s)  # "Dear team", "Notes"
        if s and not heading and (s[-1].isalnum() or s[-1] in "%)'\"’"):
            item = re.match(r"^" + _ITEM, s)
            last = re.split(r"[.?!]\s+", s[item.end() if item else 0:])[-1]
            s += "?" if not item and is_question(last) else "."
        out.append(s)
    return "\n".join(out)


# ---------------------------------------------------------------- spoken commands
_NOT_AFTER = r"(?<!\ba )(?<!\bthe )(?<!\bthis )(?<!\bthat )(?<!\bone )(?<!\banother )(?<!\bevery )(?<!\beach )"
_COMMANDS = [
    (re.compile(r"[,.;:]?\s*" + _NOT_AFTER + r"\bnew paragraph\b[,.;:!]?\s*", re.I), "\n\n"),
    (re.compile(r"[,.;:]?\s*" + _NOT_AFTER + r"\b(?:new|next) line\b[,.;:!]?\s*", re.I), "\n"),
]


def spoken_commands(text: str) -> str:
    """'new paragraph' -> blank line, 'new line' / 'next line' -> line break. Not after 'a', 'the', 'this' ...
    so 'a new line of products' stays as said."""
    for pat, rep in _COMMANDS:
        text = pat.sub(rep, text)
    return text


# ---------------------------------------------------------------- lists
_ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
_ORDLY = ["firstly", "secondly", "thirdly", "fourthly", "fifthly"]
_CARD = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_SUF = ["st", "nd", "rd"] + ["th"] * 7
_N = {w: i + 1 for i, w in enumerate(_ORD)} | {w: i + 1 for i, w in enumerate(_ORDLY)} | {w: i + 1 for i, w in enumerate(_CARD)}
_N |= {str(i): i for i in range(1, 11)} | {f"{i}{s}": i for i, s in zip(range(1, 11), _SUF)}
_DIGIT_ORD = [f"{i}{s}" for i, s in zip(range(1, 11), _SUF)]  # Whisper writes spoken ordinals as digits
_ORD_RE = "|".join(_ORD + [f"{i}{s}" for i, s in zip(range(1, 11), _SUF)])
_NUM_RE = "|".join(_CARD + [str(i) for i in range(10, 0, -1)])
_LEAD = r"(?:^|(?<=[.?!,;:\n])\s*|\s+(?:and\s+|then\s+)?)"  # a cue starts the text, follows punctuation, or a space
_CUE = re.compile(
    r"(?P<lead>" + _LEAD + r")(?:the\s+)?(?:"
    r"(?P<ord>" + _ORD_RE + r")\s+(?:point|item|step)"  # first point, 2nd item
    r"|(?:point|item|step|number)\s+(?P<num>" + _NUM_RE + r")(?![\w.,]\d)"  # point one, number 2
    r"|(?P<ordly>" + "|".join(_ORDLY) + r")"  # firstly, secondly
    r"|(?P<seq>" + "|".join(_ORD + _DIGIT_ORD) + r")"  # 'first, biryani', '1st biryani', 'and 5th, buttermilk' (checked in _cues)
    r"|(?P<next>next|another)\s+(?:point|item|step)"  # next point
    r"|(?P<bullet>bullet point|next bullet|add a bullet|new bullet)"
    r"|(?P<numbered>numbered list)"
    r"|(?P<end>end (?:of )?(?:the )?list)"
    r")\b(?:\s+(?:is|was))?\s*[,.:;\-–]?\s*", re.I)
_KINDS = ("ord", "num", "ordly", "seq", "next", "bullet", "numbered", "end")
_NUMBERED = ("ord", "num", "ordly", "seq", "next", "numbered")


def _item(s: str) -> str:
    s = re.sub(r"^[\s,.;:\-–]+|[\s,;:\-–]+$", "", s)
    s = re.sub(r"\s+(?:and|then)$", "", s, flags=re.I)
    return s[:1].upper() + s[1:]


def _cues(text: str) -> list[dict]:
    out = []
    for m in _CUE.finditer(text):
        kind = next(k for k in _KINDS if m.group(k))
        n = _N.get(m.group(kind).lower()) if kind in ("ord", "num", "ordly", "seq") else (1 if kind == "numbered" else None)
        prefix = text[:m.start("lead")] + m.group("lead")
        # 'number one' / 'point two' mid-sentence ("our number one priority") and 'the first time' are not cues
        word_ordinal = kind == "seq" and not m.group("seq")[0].isdigit()
        if word_ordinal and not re.match(r"\s*[,;:]", text[m.end("seq"):]):
            continue  # a spoken-word ordinal is a list cue only with its comma ("first, biryani", not "first thing"); 1st, 2nd always are
        if (kind == "num" or word_ordinal) and not re.search(r"(?:^|[.?!,;:\n]|\band|\bthen)\s*$", prefix, re.I):
            continue
        out.append({"kind": kind, "n": n, "start": m.start(), "end": m.end()})
    return out


def _sequence(cues: list[dict]) -> list[dict]:
    """The run of list items: it starts at 'first' (or 'numbered list') and each cue must count up
    ('second', 'third', 'next point'). Gaps are fine ('third' then 'fifth'); counting back is not."""
    run = []
    for c in cues:
        if not run:
            if c["n"] == 1:
                run.append(c)
            continue
        want = run[-1]["n"] + 1
        n = c["n"] if c["n"] is not None else want
        if n >= want:
            run.append({**c, "n": n})
    return run


def lists(text: str) -> str:
    """Explicit list cues -> one item per line, renumbered 1..n. Numbered: 'first', 'second', 'third' ... (also
    'first point', 'point one', 'next point', 'numbered list'), at least two items. Bullets: 'bullet point' at
    least twice. 'end list' closes the list and the rest becomes a new paragraph. Ordinary sentences are untouched."""
    cues = _cues(text)
    seq = _sequence([c for c in cues if c["kind"] in _NUMBERED])
    bullets = [c for c in cues if c["kind"] == "bullet"]
    if len(seq) >= 2:
        use, bullet = seq, False
    elif len(bullets) >= 2:
        use, bullet = bullets, True
    else:
        return text
    ends = [c for c in cues if c["kind"] == "end" and c["start"] >= use[-1]["end"]]
    boundary = ends[0]["start"] if ends else len(text)
    tail = text[ends[0]["end"]:].strip() if ends else ""
    items = []
    for i, c in enumerate(use):
        nxt = use[i + 1]["start"] if i + 1 < len(use) else boundary
        items.append(_item(text[c["end"]:nxt]))
    items = [x for x in items if x]
    if len(items) < 2:
        return text
    body = "\n".join(("- " if bullet else f"{i}. ") + x for i, x in enumerate(items, 1))
    intro = text[:use[0]["start"]].strip().rstrip(",;")
    if intro and intro[-1] not in ".?!:":
        intro += ":"
    return "\n".join(p for p in (intro, body) if p) + (("\n\n" + tail) if tail else "")


# ---------------------------------------------------------------- numbers
_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
             "ninth": 9}
_NUMWORD = "|".join(sorted(list(_UNITS) + list(_TENS) + list(_SCALES), key=len, reverse=True))
_DIGIT = r"(?:zero|one|two|three|four|five|six|seven|eight|nine)\b"
_PHRASE = re.compile(
    r"\b(?P<num>(?:(?:" + _NUMWORD + r")(?:[\s-]+(?:and[\s-]+)?(?=(?:" + _NUMWORD + r")\b))?)+)"
    r"(?:[\s-]+(?P<ordt>" + "|".join(_ORDINALS) + r"))?"
    r"(?:\s+point\s+(?P<dec>" + _DIGIT + r"(?:\s+" + _DIGIT + r")*))?\b", re.I)
_MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_UNIT_AFTER = re.compile(r"\s*(?:percent\b|per cent\b|%|(?:kg|kilograms?|grams?|km|kilometers?|kilometres?|meters?|"
                         r"metres?|cm|mm|miles?|feet|foot|inches|gb|gigabytes?|mb|megabytes?|tb|terabytes?|ghz|mhz|mph|"
                         r"kmph|fps|px|pixels?|degrees?|liters?|litres?|ml|ms|milliseconds?|dollars?|bucks|euros?|"
                         r"rupees?)\b)", re.I)
_CURRENCY = {"dollar": "$", "dollars": "$", "bucks": "$", "euro": "€", "euros": "€"}
_HOURS = {w: i for i, w in enumerate(["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                                      "eleven", "twelve"], 1)}
_MINUTE_WORDS = "|".join(sorted([f"{t} {u}" for t in ("twenty", "thirty", "forty", "fifty")
                                 for u in ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")]
                                + list(_TENS)[:4] + [w for w, v in _UNITS.items() if v >= 10], key=len, reverse=True))
_TIME = re.compile(r"\b(?P<h>" + "|".join(_HOURS) + r"|1[0-2]|[1-9])(?:\s+(?P<m>oh\s+(?:one|two|three|four|five|six|"
                   r"seven|eight|nine)|" + _MINUTE_WORDS + r"))?\s+(?P<ap>a\.?\s?m\b\.?|p\.?\s?m\b\.?)", re.I)


def _value(words: list[str]) -> int | None:
    """Value of a well-formed spoken number, else None ('three thirty' and 'two three' are not one number)."""
    total, cur, last = 0, 0, None
    for w in (x.lower() for x in words):
        if w == "and":
            if last not in ("hundred", "scale"):
                return None
            continue
        if w in _UNITS:
            if last in ("unit", "teen") or (last == "tens" and _UNITS[w] >= 10) or (last == "tens" and _UNITS[w] == 0):
                return None
            cur += _UNITS[w]
            last = "teen" if _UNITS[w] >= 10 else "unit"
        elif w in _TENS:
            if last in ("unit", "teen", "tens"):
                return None
            cur += _TENS[w]
            last = "tens"
        elif w == "hundred":
            if last not in ("unit", "teen") or cur >= 100:
                return None
            cur *= 100
            last = "hundred"
        elif w in _SCALES:
            if last is None:
                return None
            total += cur * _SCALES[w]
            cur, last = 0, "scale"
        else:
            return None
    return total + cur


def _suffix(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def times(text: str) -> str:
    """'three thirty pm' -> '3:30 PM', 'seven am' -> '7 AM', 'ten oh five pm' -> '10:05 PM'."""
    def repl(m: re.Match) -> str:
        h = m.group("h").lower()
        hour = _HOURS.get(h) or int(h)
        mm = m.group("m")
        t = str(hour)
        if mm:
            parts = mm.lower().split()
            minute = _UNITS[parts[1]] if parts[0] == "oh" else _value(parts)
            if minute is None or minute > 59:
                return m.group(0)
            t = f"{hour}:{minute:02d}"
        tail = m.group(0)[m.end("ap") - m.start():]
        return t + (" AM" if m.group("ap").lower().startswith("a") else " PM") + tail
    return _TIME.sub(repl, text)


def numbers(text: str) -> str:
    """Spoken numbers -> digits where the context makes it a number: 10 and above, decimals, percentages,
    currency, measurements, dates, ordinals from 21st, times. 'one of them', 'two days', 'first' stay words."""
    text = times(text)

    def repl(m: re.Match) -> str:
        words = re.split(r"[\s-]+", m.group("num").strip())
        if words[0].lower() in _SCALES:  # "a hundred people" stays words
            return m.group(0)
        before, after = text[:m.start()], text[m.end():]
        if m.group("ordt"):  # "twenty first" -> 21st ; "October twenty first" -> October 21
            n = _value(words)
            if n is None or n < 20 or n % 10:
                return m.group(0)
            v = n + _ORDINALS[m.group("ordt").lower()]
            return str(v) if re.search(_MONTHS + r"\s*$", before) else f"{v}{_suffix(v)}"
        if len(words) >= 2 and words[0].lower() in _TENS and words[1].lower() in _TENS:  # "twenty twenty six" = 2026
            tail = _value(words[1:])
            return f"{_TENS[words[0].lower()]}{tail:02d}" if tail is not None and tail < 100 else m.group(0)
        n = _value(words)
        if n is None:
            return m.group(0)
        if m.group("dec"):
            return f"{n}." + "".join(str(_UNITS[d.lower()]) for d in m.group("dec").split())
        if n >= 10 or _UNIT_AFTER.match(after) or re.search(_MONTHS + r"\s*$", before) or re.search(r"[$€£₹]\s*$", before):
            return f"{n:,}" if n >= 10000 else str(n)
        return m.group(0)  # small number in prose: keep the word

    out = _PHRASE.sub(repl, text)
    out = re.sub(r"(\d)\s*(?:percent|per cent)\b", r"\1%", out, flags=re.I)
    out = re.sub(r"(?<![$€£₹\d.,])(\d[\d,]*(?:\.\d+)?)\s+(million|billion)\s+(dollars|euros)\b",
                 lambda m: _CURRENCY[m.group(3).lower()] + m.group(1) + " " + m.group(2), out, flags=re.I)
    out = re.sub(r"(?<![$€£₹\d.,])(\d[\d,]*(?:\.\d+)?)\s+(dollars?|bucks|euros?)\b",
                 lambda m: _CURRENCY[m.group(2).lower()] + m.group(1), out, flags=re.I)
    return out


def keep_line_breaks(before: str, after: str) -> str:
    """After an AI step: if it kept the same lines, put back the exact breaks the speaker asked for
    ('new line' = one break, 'new paragraph' = blank line); the AI tends to turn one into the other."""
    b = [x for x in before.strip().split("\n") if x.strip()]
    a = [x for x in after.strip().split("\n") if x.strip()]
    if "\n" not in before.strip() or len(a) != len(b):
        return after
    seps = re.findall(r"\n\s*", before.strip())
    return a[0] + "".join(sep.replace(" ", "") + line for sep, line in zip(seps, a[1:]))


# ---------------------------------------------------------------- pipeline
def format_exact(text: str) -> str:
    """Exact Transcription: the recognised words untouched; only spacing is normalised."""
    return normalize_spacing(text)


def format_smart(text: str, numbers_on: bool = True, commands_on: bool = True) -> str:
    """Smart Formatting: commands, lists, numbers, spacing, capitals, sentence ends. Never adds or removes words
    other than the spoken cues it interprets ("new line", "first point", "percent" ...)."""
    if commands_on:
        text = spoken_commands(text)
    text = lists(text)
    if numbers_on:
        text = numbers(text)
    text = normalize_spacing(text)
    text = capitalize(text)
    return end_sentences(text)
