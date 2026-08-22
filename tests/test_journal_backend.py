from unittest.mock import patch

import pytest

from wiederholen.journal_backend import JournalBackend


async def test_open_yields_an_empty_dict_for_an_unknown_student(
    journal_backend: JournalBackend,
) -> None:
    async with journal_backend.open("111") as journal:
        assert journal == {}


async def test_open_persists_mutations(journal_backend: JournalBackend) -> None:
    async with journal_backend.open("111") as journal:
        journal["marker"] = "a"

    async with journal_backend.open("111") as journal:
        assert journal == {"marker": "a"}


async def test_open_persists_mutations_even_if_the_body_raises(
    journal_backend: JournalBackend,
) -> None:
    with pytest.raises(ValueError, match="boom"):
        async with journal_backend.open("111") as journal:
            journal["marker"] = "a"
            raise ValueError("boom")

    async with journal_backend.open("111") as journal:
        assert journal == {"marker": "a"}


async def test_open_deletes_the_entry_once_emptied(
    journal_backend: JournalBackend,
) -> None:
    async with journal_backend.open("111") as journal:
        journal["marker"] = "a"

    async with journal_backend.open("111") as journal:
        journal.clear()

    assert [student_id async for student_id in journal_backend] == []


async def test_open_does_not_write_when_nothing_changed(
    journal_backend: JournalBackend,
) -> None:
    with patch.object(journal_backend, "_save", autospec=True) as mock_save:
        async with journal_backend.open("111"):
            pass

    mock_save.assert_not_awaited()


async def test_open_writes_when_something_changed(
    journal_backend: JournalBackend,
) -> None:
    with patch.object(journal_backend, "_save", autospec=True) as mock_save:
        async with journal_backend.open("111") as journal:
            journal["marker"] = "a"

    mock_save.assert_awaited_once_with("111", {"marker": "a"})


async def test_students_are_addressed_independently(
    journal_backend: JournalBackend,
) -> None:
    async with journal_backend.open("111") as journal:
        journal["marker"] = "a"
    async with journal_backend.open("222") as journal:
        journal["marker"] = "b"

    async with journal_backend.open("111") as journal:
        assert journal == {"marker": "a"}
    async with journal_backend.open("222") as journal:
        assert journal == {"marker": "b"}


async def test_iterating_yields_every_student_id(
    journal_backend: JournalBackend,
) -> None:
    async with journal_backend.open("111") as journal:
        journal["marker"] = "a"
    async with journal_backend.open("222") as journal:
        journal["marker"] = "b"

    student_ids = {student_id async for student_id in journal_backend}

    assert student_ids == {"111", "222"}
