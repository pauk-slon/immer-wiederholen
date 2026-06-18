import random
from typing import Final, Any

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from wiederholen.cards import Card, CardPicker
from wiederholen.i18n import Language, LANGUAGES
from .l10n import DEFAULT_LANGUAGE, LOCALES

dp: Final = Dispatcher()


class UserState(StatesGroup):
    answering = State()


def _get_language(state: dict[str, Any]) -> Language:
    raw_language = state.get("language")
    return raw_language if raw_language in LANGUAGES else DEFAULT_LANGUAGE


def _make_keyboard(card: Card) -> InlineKeyboardMarkup:
    options = list(card.distractors) + [card.answer]
    random.shuffle(options)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=opt)] for opt in options
        ]
    )


@dp.message(Command("start"))
async def command_start(message: Message, state: FSMContext) -> None:
    language = _get_language(await state.get_data())
    await message.answer(LOCALES[language].start)


@dp.message(Command("language"))
async def command_language(message: Message, state: FSMContext) -> None:
    language = _get_language(await state.get_data())
    new_language = "en" if language == "ru" else "ru"
    await state.update_data(language=new_language)
    await message.answer(LOCALES[new_language].start)


@dp.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message,
    state: FSMContext,
    card_picker: CardPicker,
) -> None:
    card = card_picker()
    await state.set_state(UserState.answering)
    await state.update_data(answer=card.answer, explanation=card.explanation)
    await message.answer(card.question, reply_markup=_make_keyboard(card))


@dp.callback_query(UserState.answering)
async def handle_answer(callback: CallbackQuery, state: FSMContext) -> None:
    state_data = await state.get_data()
    await state.clear()
    language = _get_language(state_data)
    await state.update_data(language=language)
    explanation = state_data["explanation"][language]
    locale = LOCALES[language]
    if callback.data == state_data["answer"]:
        text = f"{locale.correct}\n\n{explanation}"
    else:
        text = f"{locale.wrong.format(answer=state_data['answer'])}\n\n{explanation}"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()
