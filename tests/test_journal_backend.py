from wiederholen.journal_backend import JournalBackend


async def test_get_journal_is_empty_for_an_unknown_student(
    journal_backend: JournalBackend,
) -> None:
    assert await journal_backend.get_journal("111") == {}


async def test_save_journal_roundtrips_through_get_journal(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save_journal("111", {"word_schedule": {"marker": True}})

    assert await journal_backend.get_journal("111") == {
        "word_schedule": {"marker": True}
    }


async def test_save_journal_with_an_empty_dict_deletes_the_entry(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save_journal("111", {"marker": True})

    await journal_backend.save_journal("111", {})

    assert await journal_backend.get_journal("111") == {}
    assert [item async for item in journal_backend.iter_journals()] == []


async def test_students_are_addressed_independently(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save_journal("111", {"marker": "a"})
    await journal_backend.save_journal("222", {"marker": "b"})

    assert await journal_backend.get_journal("111") == {"marker": "a"}
    assert await journal_backend.get_journal("222") == {"marker": "b"}


async def test_iter_journals_yields_every_student(
    journal_backend: JournalBackend,
) -> None:
    await journal_backend.save_journal("111", {"marker": "a"})
    await journal_backend.save_journal("222", {"marker": "b"})

    items = {
        student_id: journal
        async for student_id, journal in journal_backend.iter_journals()
    }

    assert items == {"111": {"marker": "a"}, "222": {"marker": "b"}}
