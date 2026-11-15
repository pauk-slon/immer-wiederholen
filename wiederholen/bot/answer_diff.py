"""Telegram HTML that shows where a wrong answer differs from the correct one (#319).

The texts are compared word by word. Inside a pair of similar words, only the
letters that differ are marked, because in declension one letter carries the
case (`den`/`dem`). A word that has little in common with the learner's word
is marked as a whole, because a letter diff of unrelated words is noise.

Answer checks ignore case, and a recall check also ignores `.,!?` at the ends
of the text. So the diff ignores what the check ignores, or a capital letter
from the phone's keyboard would show as a mistake.
"""

import difflib
import html
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

# den/dem (0.67) and meinen/meinem (0.83) are similar, in/an (0.5) and
# an/nach (0.33) aren't
_SIMILAR_WORDS_RATIO: Final = 0.5

# The same characters as in Tutor.check_recall()
_END_PUNCTUATION: Final = ".,!?"

# A piece of a word and whether it differs from the other text
_Segment = tuple[str, bool]


@dataclass(frozen=True)
class Correction:
    # The shown answers, the one closest to the learner's text with the
    # parts that differ underlined
    answer: str
    # The learner's text with the extra letters struck through. Only when
    # the answer has nothing to underline, because the learner only added
    # letters (Kinders for Kinder). Otherwise None, so that the learner
    # doesn't see the wrong form again
    mistake: str | None


def correct(
    user_text: str, answers: Sequence[str], *, ignore_end_punctuation: bool = False
) -> Correction:
    closest = max(range(len(answers)), key=lambda i: _ratio(user_text, answers[i]))
    ignored = " " + (_END_PUNCTUATION if ignore_end_punctuation else "")
    user_lead, user_core, user_trail = _split_ends(user_text, ignored)
    lead, core, trail = _split_ends(answers[closest], ignored)
    user_words, correct_words = _diff_words(user_core, core)
    rendered = [
        html.escape(lead) + _render(correct_words, "u") + html.escape(trail)
        if i == closest
        else html.escape(answer)
        for i, answer in enumerate(answers)
    ]
    mistake = None
    if not _is_marked(correct_words) and _is_marked(user_words):
        mistake = (
            html.escape(user_lead) + _render(user_words, "s") + html.escape(user_trail)
        )
    return Correction(answer=" / ".join(rendered), mistake=mistake)


def _split_ends(text: str, ignored: str) -> tuple[str, str, str]:
    # The ignored characters at the start, the text between, and the ignored
    # characters at the end
    start = len(text) - len(text.lstrip(ignored))
    end = max(start, len(text.rstrip(ignored)))
    return text[:start], text[start:end], text[end:]


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(
        None, _letters(a), _letters(b), autojunk=False
    ).ratio()


def _letters(word: str) -> list[str]:
    # Each character in lower case. Not word.lower(), because a character
    # can become two (İ), and then the indices don't fit the original word
    return [letter.lower() for letter in word]


def _diff_words(
    user_text: str, correct_text: str
) -> tuple[list[list[_Segment]], list[list[_Segment]]]:
    user_words = user_text.split()
    correct_words = correct_text.split()
    user_result: list[list[_Segment]] = []
    correct_result: list[list[_Segment]] = []
    matcher = difflib.SequenceMatcher(
        None,
        [word.lower() for word in user_words],
        [word.lower() for word in correct_words],
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            user_result.extend([(word, False)] for word in user_words[i1:i2])
            correct_result.extend([(word, False)] for word in correct_words[j1:j2])
            continue
        user_block = user_words[i1:i2]
        correct_block = correct_words[j1:j2]
        for k in range(max(len(user_block), len(correct_block))):
            user_word = user_block[k] if k < len(user_block) else None
            correct_word = correct_block[k] if k < len(correct_block) else None
            if (
                user_word is not None
                and correct_word is not None
                and _ratio(user_word, correct_word) > _SIMILAR_WORDS_RATIO
            ):
                user_segments, correct_segments = _diff_letters(user_word, correct_word)
                user_result.append(user_segments)
                correct_result.append(correct_segments)
                continue
            if user_word is not None:
                user_result.append([(user_word, True)])
            if correct_word is not None:
                correct_result.append([(correct_word, True)])
    return user_result, correct_result


def _diff_letters(
    user_word: str, correct_word: str
) -> tuple[list[_Segment], list[_Segment]]:
    user_segments: list[_Segment] = []
    correct_segments: list[_Segment] = []
    matcher = difflib.SequenceMatcher(
        None, _letters(user_word), _letters(correct_word), autojunk=False
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        is_different = tag != "equal"
        if i2 > i1:
            user_segments.append((user_word[i1:i2], is_different))
        if j2 > j1:
            correct_segments.append((correct_word[j1:j2], is_different))
    return user_segments, correct_segments


def _is_marked(words: list[list[_Segment]]) -> bool:
    return any(is_different for word in words for _, is_different in word)


def _render(words: list[list[_Segment]], tag: str) -> str:
    return " ".join(
        "".join(
            f"<{tag}>{html.escape(text)}</{tag}>" if is_different else html.escape(text)
            for text, is_different in word
        )
        for word in words
    )
