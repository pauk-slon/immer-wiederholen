from tests.plugins.curriculum import make_exercise
from wiederholen.school import Recall
from wiederholen.web.session import WebSessionStore
from wiederholen.web.web_student_id import WebStudentID


async def test_get_shown_exercise_is_none_for_an_unknown_student(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    assert await web_session_store.get_shown_exercise(student_id, []) is None


async def test_set_then_get_shown_exercise_round_trips(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    exercise = make_exercise(word="warten", answer="auf")

    await web_session_store.set_shown_exercise(student_id, ["government"], exercise)

    assert (
        await web_session_store.get_shown_exercise(student_id, ["government"])
        == exercise
    )


async def test_students_are_addressed_independently(
    web_session_store: WebSessionStore,
) -> None:
    student_a = WebStudentID.generate()
    student_b = WebStudentID.generate()
    exercise_a = make_exercise(word="warten")
    exercise_b = make_exercise(word="sprechen")

    await web_session_store.set_shown_exercise(student_a, ["government"], exercise_a)
    await web_session_store.set_shown_exercise(student_b, ["government"], exercise_b)

    assert (
        await web_session_store.get_shown_exercise(student_a, ["government"])
        == exercise_a
    )
    assert (
        await web_session_store.get_shown_exercise(student_b, ["government"])
        == exercise_b
    )


async def test_get_shown_recall_is_none_for_an_unknown_student(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    assert await web_session_store.get_shown_recall(student_id, []) is None


async def test_get_shown_recall_is_none_before_one_is_set(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    await web_session_store.set_shown_exercise(
        student_id, ["government"], make_exercise()
    )

    assert await web_session_store.get_shown_recall(student_id, ["government"]) is None


async def test_set_then_get_shown_recall_round_trips(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    recall = Recall(question="Ich ___ (der Bus).", answer=["Ich warte auf den Bus."])
    await web_session_store.set_shown_exercise(
        student_id, ["government"], make_exercise()
    )

    await web_session_store.set_shown_recall(student_id, ["government"], recall)

    assert (
        await web_session_store.get_shown_recall(student_id, ["government"]) == recall
    )


async def test_set_shown_exercise_clears_a_previously_set_recall(
    web_session_store: WebSessionStore,
) -> None:
    student_id = WebStudentID.generate()
    recall = Recall(question="Ich ___ (der Bus).", answer=["Ich warte auf den Bus."])
    await web_session_store.set_shown_exercise(
        student_id, ["government"], make_exercise()
    )
    await web_session_store.set_shown_recall(student_id, ["government"], recall)

    await web_session_store.set_shown_exercise(
        student_id, ["government"], make_exercise(word="sprechen")
    )

    assert await web_session_store.get_shown_recall(student_id, ["government"]) is None


async def test_different_topics_scopes_are_addressed_independently(
    web_session_store: WebSessionStore,
) -> None:
    # The regression this whole scoping scheme exists to fix: two different
    # landing pages (different topics) sharing one student_id must never
    # see each other's "shown exercise" — see session.py's own comment.
    student_id = WebStudentID.generate()
    exercise_a = make_exercise(word="warten", topic="government")
    exercise_b = make_exercise(word="sprechen", topic="partizip_ii")

    await web_session_store.set_shown_exercise(student_id, ["government"], exercise_a)
    await web_session_store.set_shown_exercise(student_id, ["partizip_ii"], exercise_b)

    assert (
        await web_session_store.get_shown_exercise(student_id, ["government"])
        == exercise_a
    )
    assert (
        await web_session_store.get_shown_exercise(student_id, ["partizip_ii"])
        == exercise_b
    )
