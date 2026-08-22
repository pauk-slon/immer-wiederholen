import pytest

from wiederholen.journal_backend import JournalBackend


async def test_get_is_empty_for_an_unknown_student(
    journal_backend: JournalBackend,
) -> None:
    assert await journal_backend.get("111") == {}


async def test_save_roundtrips_through_get(journal_backend: JournalBackend) -> None:
    await journal_backend.save("111", {"word_schedule": {"marker": True}})

    assert await journal_backend.get("111") == {"word_schedule": {"marker": True}}


async def test_save_with_an_empty_dict_deletes_the_entry(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save("111", {"marker": True})

    await journal_backend.save("111", {})

    assert await journal_backend.get("111") == {}
    assert [item async for item in journal_backend] == []


async def test_students_are_addressed_independently(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save("111", {"marker": "a"})
    await journal_backend.save("222", {"marker": "b"})

    assert await journal_backend.get("111") == {"marker": "a"}
    assert await journal_backend.get("222") == {"marker": "b"}


async def test_iterating_yields_every_student(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save("111", {"marker": "a"})
    await journal_backend.save("222", {"marker": "b"})

    items = {student_id: journal async for student_id, journal in journal_backend}

    assert items == {"111": {"marker": "a"}, "222": {"marker": "b"}}


async def test_session_yields_the_journal_for_mutation(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save("111", {"marker": "a"})

    async with journal_backend.session("111") as journal:
        assert journal == {"marker": "a"}


async def test_session_saves_mutations_on_normal_exit(
    journal_backend: JournalBackend,
) -> None:
    async with journal_backend.session("111") as journal:
        journal["marker"] = "a"

    assert await journal_backend.get("111") == {"marker": "a"}


async def test_session_saves_mutations_even_when_the_body_raises(
    journal_backend: JournalBackend,
) -> None:
    with pytest.raises(ValueError, match="boom"):
        async with journal_backend.session("111") as journal:
            journal["marker"] = "a"
            raise ValueError("boom")

    assert await journal_backend.get("111") == {"marker": "a"}
