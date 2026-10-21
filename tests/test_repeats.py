"""Accidental repeats: removed when they are mistakes, kept when they are intentional, and overlapping segments are joined once."""
import pytest

from voicetype import formatting as f


@pytest.mark.parametrize("raw, want", [
    ("I I want to build this", "I want to build this"),
    ("The app app is slow", "The app is slow"),
    ("We need to fix fix the issue", "We need to fix the issue"),
    ("Please send send me the file.", "Please send me the file."),
    ("I I, want to build this", "I, want to build this"),  # the copy's comma is kept on the word
    ("that is it, it, done", "that is it, done"),
])
def test_accidental_repeats_are_removed(raw, want):
    assert f.remove_repeats(raw) == want


@pytest.mark.parametrize("raw", [
    "it was very very good",  # intensifier
    "ha ha that is funny",  # laughter
    "no no no, not that one",  # emphasis in the list of intentional words
    "the 10 10 items",  # numbers are never touched
    "that is that one",  # separated by another word: not a repeat
    "we had had enough",  # grammatical repeat of a different word is not adjacent identical; kept as said
    "Ok ok let us go",
])
def test_intentional_repeats_are_kept(raw):
    assert f.remove_repeats(raw) == raw


def test_overlapping_segments_do_not_repeat_words():
    assert f.join_segments([(0, 2, " we need to fix the"), (1.9, 4, " the issue today")]) == "we need to fix the issue today"
    assert f.join_segments([(0, 2, " we went to the store"), (2.1, 4, " and bought milk")]) == "we went to the store and bought milk"


def test_a_real_intentional_double_across_segments_is_kept():
    assert f.join_segments([(0, 2, " it was very"), (1.9, 4, " very good")]) == "it was very very good"


def test_repeat_cleanup_is_idempotent():
    once = f.remove_repeats("I I want to fix fix this app app now")
    assert f.remove_repeats(once) == once == "I want to fix this app now"
