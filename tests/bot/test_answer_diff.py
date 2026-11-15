import pytest

from wiederholen.bot.answer_diff import Correction, correct


@pytest.mark.parametrize(
    ("user_text", "answer", "shown"),
    [
        ("an dem", "an den", "an de<u>n</u>"),
        ("meinen Bruder", "meinem Bruder", "meine<u>m</u> Bruder"),
        ("an", "nach", "<u>nach</u>"),
        ("in dem", "an den", "<u>an</u> de<u>n</u>"),
        ("gegangt", "gegangen", "gegang<u>en</u>"),
        ("auf", "über", "<u>über</u>"),
        ("an", "an den", "an <u>den</u>"),
        ("Gegangt", "gegangen", "gegang<u>en</u>"),
        ("Dem Mann", "dem Mann", "dem Mann"),
    ],
)
def test_underlines_letters_in_similar_words_and_other_words_as_a_whole(
    user_text: str, answer: str, shown: str
) -> None:
    assert correct(user_text, [answer]) == Correction(answer=shown, mistake=None)


@pytest.mark.parametrize(
    ("user_text", "answer", "mistake"),
    [
        ("Kinders", "Kinder", "Kinder<s>s</s>"),
        ("gegangenen", "gegangen", "gegangen<s>en</s>"),
        ("an den den", "an den", "an den <s>den</s>"),
        ("Ja.", "Ja", "Ja<s>.</s>"),
    ],
)
def test_strikes_through_extra_letters_when_nothing_is_underlined(
    user_text: str, answer: str, mistake: str
) -> None:
    assert correct(user_text, [answer]) == Correction(answer=answer, mistake=mistake)


def test_ignores_punctuation_at_the_ends_on_request() -> None:
    correction = correct(
        "ich warte auf den Bas", ["Ich warte auf den Bus."], ignore_end_punctuation=True
    )

    assert correction == Correction(
        answer="Ich warte auf den B<u>u</u>s.", mistake=None
    )


def test_strikes_through_extra_letters_without_the_ignored_punctuation() -> None:
    correction = correct("Kinders!", ["Kinder"], ignore_end_punctuation=True)

    assert correction == Correction(answer="Kinder", mistake="Kinder<s>s</s>!")


def test_diffs_against_the_closest_of_several_answers() -> None:
    correction = correct("die Stadte", ["Städte", "die Städte"])

    assert correction == Correction(answer="Städte / die St<u>ä</u>dte", mistake=None)


def test_escapes_html() -> None:
    correction = correct("a<b", ["a<c & d"])

    assert correction == Correction(
        answer="a&lt;<u>c</u> <u>&amp;</u> <u>d</u>", mistake=None
    )
