from unittest.mock import patch

from opentelemetry import trace as otel_trace

from tests.plugins.aiogram import FeedMessage
from tests.plugins.tutoring import make_exercise
from wiederholen.tutoring import Course


async def test_sets_feature_attribute_when_flag_matches_chat_id(
    feed_message: FeedMessage, chat_id: int
) -> None:
    exercise = make_exercise()
    with patch(
        "wiederholen.bot.commands.wiederholen.trace", spec=otel_trace
    ) as mock_trace:
        await feed_message(
            "/wiederholen",
            course=Course([exercise]),
            feature_flags={"ai_exercises": frozenset({chat_id})},
        )

    mock_trace.get_current_span.return_value.set_attribute.assert_called_once_with(
        "feature.ai_exercises", True
    )


async def test_does_not_set_feature_attribute_when_chat_id_is_not_listed(
    feed_message: FeedMessage, chat_id: int
) -> None:
    exercise = make_exercise()
    with patch(
        "wiederholen.bot.commands.wiederholen.trace", spec=otel_trace
    ) as mock_trace:
        await feed_message(
            "/wiederholen",
            course=Course([exercise]),
            feature_flags={"ai_exercises": frozenset({chat_id + 1})},
        )

    mock_trace.get_current_span.return_value.set_attribute.assert_not_called()


async def test_does_not_set_feature_attribute_when_no_flags_are_configured(
    feed_message: FeedMessage,
) -> None:
    exercise = make_exercise()
    with patch(
        "wiederholen.bot.commands.wiederholen.trace", spec=otel_trace
    ) as mock_trace:
        await feed_message("/wiederholen", course=Course([exercise]))

    mock_trace.get_current_span.return_value.set_attribute.assert_not_called()
