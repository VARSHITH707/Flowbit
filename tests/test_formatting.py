"""Formatting pipeline: what it must change, and (just as important) what it must leave alone."""
import pytest

from voicetype import formatting as f

smart = f.format_smart


# ---- segments and spacing
def test_segments_joined_with_one_space_and_long_pause_ends_a_sentence():
    segs = [(0.0, 2.0, " so today I fixed the bug"), (3.2, 4.0, " Then I tested it."), (4.1, 5.0, " and it works")]
    assert f.join_segments(segs) == "so today I fixed the bug. Then I tested it. and it works"


def test_short_pause_or_lowercase_next_segment_is_not_a_sentence_break():
    assert f.join_segments([(0, 1, "we tested the app in"), (1.2, 2, "Notepad today")]) == "we tested the app in Notepad today"
    assert f.join_segments([(0, 1, "it was fine"), (3, 4, "but slow")]) == "it was fine but slow"


def test_spacing_is_normalised_without_touching_numbers_times_or_abbreviations():
    assert f.normalize_spacing("Hello ,  world !How are you ?") == "Hello, world! How are you?"
    assert f.normalize_spacing("It costs 1,000 at 10:30 and 3.5 more, e.g. here.") == "It costs 1,000 at 10:30 and 3.5 more, e.g. here."
    assert f.normalize_spacing("line one  \n\n\n\nline two ") == "line one\n\nline two"


# ---- punctuation and capitals
def test_capitals_and_sentence_end_are_added():
    assert smart("so today i worked on the project") == "So today I worked on the project."
    assert smart("i'm done. next we ship it") == "I'm done. Next we ship it."


def test_questions_only_when_they_clearly_open_as_questions():
    assert smart("can you send me the report") == "Can you send me the report?"
    assert smart("what is the plan for today") == "What is the plan for today?"
    assert smart("do it now") == "Do it now."
    assert smart("when I get home I will call you") == "When I get home I will call you."


def test_existing_punctuation_is_kept_and_no_exclamation_marks_are_invented():
    for t in ("Wow, that is great!", "Is it ready?", "I tested it, and it works.", "Ship it on Friday."):
        assert smart(t) == t
    assert "!" not in smart("that is amazing we finished early")


def test_i_e_is_not_capitalised():
    assert "i.e." in smart("use the small model i.e. the fast one")


# ---- numbered and bullet lists
def test_numbered_list_from_ordinal_cues():
    raw = "First point improve the UI second point fix the microphone third point add number formatting"
    assert smart(raw) == "1. Improve the UI.\n2. Fix the microphone.\n3. Add number formatting."


def test_numbered_list_as_whisper_actually_punctuates_it():
    raw = "First point improve the UI. Second point fix the microphone. Third point add number formatting."
    assert smart(raw) == "1. Improve the UI.\n2. Fix the microphone.\n3. Add number formatting."


@pytest.mark.parametrize("raw", [
    "Point one open the app. Point two log in.",
    "Number one open the app, number two log in",
    "Firstly open the app secondly log in",
    "First item open the app next item log in",
    "numbered list open the app next point log in end list",
])
def test_other_numbered_cues(raw):
    assert smart(raw).startswith("1. Open the app.\n2. Log in.")


def test_intro_and_text_after_end_list_are_kept():
    raw = "here are the steps first point open the app second point log in end list then we are done"
    assert smart(raw) == "Here are the steps:\n1. Open the app.\n2. Log in.\n\nThen we are done."


def test_bullet_list():
    raw = "Bullet point improve the design bullet point fix recording errors"
    assert smart(raw) == "- Improve the design.\n- Fix recording errors."


@pytest.mark.parametrize("raw", [
    "Our number one priority is speed.",  # 'number one' mid-sentence
    "The first point I want to make is simple.",  # a single cue is not a list
    "Secondly, we need more tests.",  # does not start at one
    "I have 2 cats and 3 dogs.",  # numbers in a sentence
    "At some point one of us has to decide.",
    "That is a good bullet point for the slide.",  # single bullet mention
])
def test_ordinary_sentences_never_become_lists(raw):
    assert "\n" not in smart(raw)


# ---- spoken commands
def test_new_paragraph_and_new_line_commands():
    assert smart("Dear team new paragraph the release is ready new line thanks for your help") == \
        "Dear team\n\nThe release is ready.\nThanks for your help."
    assert smart("Dear Team New Paragraph The release is ready New Line Thanks for your help.") == \
        "Dear Team\n\nThe release is ready.\nThanks for your help."


def test_commands_inside_ordinary_phrases_stay_as_said():
    assert smart("we launched a new line of products") == "We launched a new line of products."
    assert smart("start the new paragraph with a quote", commands_on=True) == "Start the new paragraph with a quote."


def test_commands_can_be_switched_off():
    assert smart("hello new line world", commands_on=False) == "Hello new line world."


# ---- numbers
@pytest.mark.parametrize("raw, want", [
    ("the price went up by fifteen percent", "The price went up by 15%."),
    ("it is three point five times faster", "It is 3.5 times faster."),
    ("we have twenty five users", "We have 25 users."),
    ("it costs twenty dollars", "It costs $20."),
    ("revenue was three point five million dollars", "Revenue was $3.5 million."),
    ("the meeting is on October twenty first", "The meeting is on October 21."),
    ("the twenty first century", "The 21st century."),
    ("it weighs five kilograms", "It weighs 5 kilograms."),
    ("we raised two hundred and fifty thousand", "We raised 250,000."),
    ("see you in twenty twenty six", "See you in 2026."),
    ("call me at three thirty pm", "Call me at 3:30 PM."),
    ("the bus leaves at seven am", "The bus leaves at 7 AM."),
])
def test_numbers_where_context_makes_them_numbers(raw, want):
    assert smart(raw) == want


@pytest.mark.parametrize("raw", [
    "One of them is broken.", "I need two days.", "No one came.", "Someone called.", "It was a one-time thing.",
    "We need a hundred people.", "First, open the app.", "Three thirty people? No.",
])
def test_numbers_in_prose_stay_words(raw):
    assert smart(raw) == raw


def test_whisper_numbers_are_left_alone():
    t = "The price went up by 15% to $3.5 million on October 21."
    assert smart(t) == t


def test_numbers_can_be_switched_off():
    assert smart("we have twenty five users", numbers_on=False) == "We have twenty five users."


def test_line_breaks_the_speaker_asked_for_survive_an_ai_step():
    before = "Dear Team\n\nThe release is ready\nThanks for your help"
    ai = "Dear Team,\n\nThe release is ready.\n\nThanks for your help."
    assert f.keep_line_breaks(before, ai) == "Dear Team,\n\nThe release is ready.\nThanks for your help."
    assert f.keep_line_breaks("one line only", "One line only.") == "One line only."
    assert f.keep_line_breaks("a\nb", "A, b.") == "A, b."  # AI merged lines: nothing to map, keep its text


# ---- modes and safety
def test_exact_mode_keeps_wording_and_only_fixes_spacing():
    raw = "so  um today i worked new paragraph first point fix it second point test it"
    out = f.format_exact(raw)
    assert out == "so um today i worked new paragraph first point fix it second point test it"


def test_smart_formatting_is_idempotent():
    for raw in ("First point improve the UI second point fix the microphone", "Bullet point a bullet point b",
                "hello new paragraph world", "the price went up by fifteen percent", "can you send it"):
        once = smart(raw)
        assert smart(once) == once


def test_smart_formatting_never_drops_content_words():
    raw = "so today i worked on the project and i fixed the microphone bug then i tested the app in notepad"
    out = smart(raw)
    strip = lambda s: [w.strip(".,?!:").lower() for w in s.split()]  # noqa: E731
    assert strip(out) == strip(raw)
