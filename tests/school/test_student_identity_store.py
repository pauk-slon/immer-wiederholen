import asyncio

import pytest

from wiederholen.school import IdentityAlreadyLinkedError, StudentIdentityStore


async def test_resolve_or_create_mints_a_new_student_id(
    student_identity_store: StudentIdentityStore,
) -> None:
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )

    assert student_id


async def test_resolve_or_create_is_stable_for_the_same_identifier(
    student_identity_store: StudentIdentityStore,
) -> None:
    first = await student_identity_store.resolve_or_create_student_id("telegram", "1")
    second = await student_identity_store.resolve_or_create_student_id("telegram", "1")

    assert first == second


async def test_resolve_or_create_differs_across_identifiers(
    student_identity_store: StudentIdentityStore,
) -> None:
    first = await student_identity_store.resolve_or_create_student_id("telegram", "1")
    second = await student_identity_store.resolve_or_create_student_id("telegram", "2")

    assert first != second


async def test_resolve_or_create_converges_under_concurrent_calls(
    student_identity_store: StudentIdentityStore,
) -> None:
    # Two callers racing to resolve the exact same, brand-new identifier at
    # once must still agree on one winner — the atomic "set if absent" in
    # _create_if_absent() is what this actually exercises.
    results = await asyncio.gather(
        *(
            student_identity_store.resolve_or_create_student_id("telegram", "1")
            for _ in range(10)
        )
    )

    assert len(set(results)) == 1


async def test_link_identity_links_a_new_identifier_to_an_existing_student(
    student_identity_store: StudentIdentityStore,
) -> None:
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )

    await student_identity_store.link_identity(student_id, "telegram", "2")

    assert (
        await student_identity_store.resolve_or_create_student_id("telegram", "2")
        == student_id
    )


async def test_link_identity_is_a_no_op_when_already_linked_to_the_same_student(
    student_identity_store: StudentIdentityStore,
) -> None:
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )

    await student_identity_store.link_identity(student_id, "telegram", "1")


async def test_link_identity_raises_when_identifier_already_linked_elsewhere(
    student_identity_store: StudentIdentityStore,
) -> None:
    other_student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "2"
    )

    with pytest.raises(IdentityAlreadyLinkedError):
        await student_identity_store.link_identity(student_id, "telegram", "1")

    # The existing link is untouched by the failed attempt.
    assert (
        await student_identity_store.resolve_or_create_student_id("telegram", "1")
        == other_student_id
    )


async def test_iter_identifiers_yields_every_linked_identifier_for_that_provider(
    student_identity_store: StudentIdentityStore,
) -> None:
    first = await student_identity_store.resolve_or_create_student_id("telegram", "1")
    second = await student_identity_store.resolve_or_create_student_id("telegram", "2")

    pairs = {pair async for pair in student_identity_store.iter_identifiers("telegram")}

    assert pairs == {("1", first), ("2", second)}


async def test_iter_identifiers_stays_scoped_to_one_provider_among_several(
    student_identity_store: StudentIdentityStore,
) -> None:
    telegram_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )
    await student_identity_store.link_identity(telegram_id, "browser", "1")

    pairs = {pair async for pair in student_identity_store.iter_identifiers("telegram")}

    assert pairs == {("1", telegram_id)}


async def test_resolve_student_id_returns_none_for_an_unlinked_identifier(
    student_identity_store: StudentIdentityStore,
) -> None:
    resolved = await student_identity_store.resolve_student_id("browser", "unknown")

    assert resolved is None


async def test_resolve_student_id_finds_a_linked_identifier_without_creating_one(
    student_identity_store: StudentIdentityStore,
) -> None:
    student_id = await student_identity_store.resolve_or_create_student_id(
        "telegram", "1"
    )
    await student_identity_store.link_identity(student_id, "browser", "token")

    resolved = await student_identity_store.resolve_student_id("browser", "token")

    assert resolved == student_id
