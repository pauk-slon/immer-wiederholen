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
        "ich warte auf den Bas", ["Ich warte auf den Bus."], ignore_punctuation=True
    )

    assert correction == Correction(
        answer="Ich warte auf den B<u>u</u>s.", mistake=None
    )


def test_strikes_through_extra_letters_without_the_ignored_punctuation() -> None:
    correction = correct("Kinders!", ["Kinder"], ignore_punctuation=True)

    assert correction == Correction(answer="Kinder", mistake="Kinder<s>s</s>!")


def test_shows_the_comma_inside_without_marking_it_on_request() -> None:
    correction = correct(
        "Wenn ich Zeit hätte kann ich dir helfen",
        ["Wenn ich Zeit hätte, könnte ich dir helfen."],
        ignore_punctuation=True,
    )

    assert correction == Correction(
        answer="Wenn ich Zeit hätte, k<u>ö</u>nn<u>te</u> ich dir helfen.", mistake=None
    )


def test_doesnt_strike_through_an_extra_comma_on_request() -> None:
    correction = correct("Kinders, ja", ["Kinder ja"], ignore_punctuation=True)

    assert correction == Correction(answer="Kinder ja", mistake="Kinder<s>s</s>, ja")


def test_marks_a_missing_comma_without_the_request() -> None:
    correction = correct("hätte könnte", ["hätte, könnte"])

    assert correction == Correction(answer="hätte<u>,</u> könnte", mistake=None)


def test_diffs_against_the_closest_of_several_answers() -> None:
    correction = correct("die Stadte", ["Städte", "die Städte"])

    assert correction == Correction(answer="Städte / die St<u>ä</u>dte", mistake=None)


def test_escapes_html() -> None:
    correction = correct("a<b", ["a<c & d"])

    assert correction == Correction(
        answer="a&lt;<u>c</u> <u>&amp;</u> <u>d</u>", mistake=None
    )
