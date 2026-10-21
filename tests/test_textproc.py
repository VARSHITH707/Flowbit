from voicetype.textproc import apply_vocab, clean, parse_vocab, postprocess, vocab_prompt


def test_vocab_fixes_case_whole_word_only():
    assert apply_vocab("we use kubernetes and postgresql daily", ["Kubernetes", "PostgreSQL"]) == "we use Kubernetes and PostgreSQL daily"
    assert apply_vocab("unkubernetes kubernetesish", ["Kubernetes"]) == "unkubernetes kubernetesish"  # no partial-word damage


def test_vocab_spoken_to_written_multiword():
    assert apply_vocab("I like py side six a lot", ["py side six=>PySide6"]) == "I like PySide6 a lot"
    assert apply_vocab("I like py   side   six", ["py side six=>PySide6"]) == "I like PySide6"


def test_unrelated_text_untouched():
    t = "The quick brown fox, it's 100% fine: Café — 日本語."
    assert apply_vocab(t, ["Fox2", "x=>y"]) == t


def test_regex_metacharacters_in_terms_are_literal():
    assert apply_vocab("use c++ and c#", ["C++", "C#"]) == "use C++ and C#"
    assert apply_vocab("price (a+b)", ["(a+b)"]) == "price (a+b)"


def test_longest_term_wins():
    assert apply_vocab("open ai api", ["open ai=>OpenAI", "open ai api=>OpenAI API"]) == "OpenAI API"


def test_vocab_prompt_and_parse():
    assert vocab_prompt([]) is None
    assert vocab_prompt(["PySide6", "py side six=>PySide6", "Kubernetes"]) == "Glossary: PySide6, Kubernetes."
    assert parse_vocab([" a=>b ", "", "c"]) == [("a", "b"), ("c", "c")]


def test_exact_mode_keeps_fillers_and_wording():
    t = "Um, so I think, uh, we should go."
    assert postprocess(t, [], "exact") == t


def test_clean_mode_drops_fillers_only():
    assert clean("Um, so I think, uh, we should go.") == "So I think, we should go."
    assert clean("The umbrella is humming near the herm.") == "The umbrella is humming near the herm."
    assert clean("") == ""


# ---- recogniser hinting must stay opt-in (it made Whisper add/drop words in real audio tests)
def test_vocab_hint_to_recogniser_is_off_by_default():
    import numpy as np
    from voicetype.config import Config
    from voicetype.speech import Result
    from voicetype.transcriber import Transcriber

    seen = {}

    class Eng:
        notice = None

        def transcribe(self, audio, language=None, vocab=None):
            seen["vocab"] = vocab
            return Result("we use py side six", "en", 1.0, 0.1, "cpu")

    cfg = Config()
    cfg.vocab = ["py side six=>PySide6"]
    cfg.format_mode = "exact"  # this test is about the recogniser hint, not AI cleanup
    t = Transcriber(lambda: cfg)
    t._engine, t._key = Eng(), (cfg.model, cfg.device)
    out = t.transcribe(np.ones(16000, "float32") * 0.1)
    assert seen["vocab"] is None and out.text == "we use PySide6"  # replacement works, no hint sent
    cfg.vocab_bias = True
    t.transcribe(np.ones(16000, "float32") * 0.1)
    assert seen["vocab"] == "Glossary: PySide6."
