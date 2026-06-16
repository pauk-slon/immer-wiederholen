import asyncio
import os
import random
from pathlib import Path
from typing import Final

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from iwh.cards import Card, CardPicker, load_cards, make_card_picker
from iwh.locales import EN, RU, Language, Locale

TOKEN: Final = os.environ["BOT_TOKEN"]
CARDS_PATH: Final = Path(os.environ.get("CARDS_PATH", "data/cards.yaml"))

dp: Final = Dispatcher()

LOCALES: Final[dict[Language, Locale]] = {"ru": RU, "en": EN}
DEFAULT_LANGUAGE: Final[Language] = "ru"


class UserState(StatesGroup):
    answering = State()


async def get_locale(state: FSMContext) -> Locale:
    data = await state.get_data()
    return LOCALES[data.get("language", DEFAULT_LANGUAGE)]


def make_keyboard(card: Card) -> InlineKeyboardMarkup:
    options = list(card.distractors) + [card.answer]
    random.shuffle(options)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=opt)] for opt in options
        ]
    )


@dp.message(Command("start"))
async def command_start(message: Message, state: FSMContext) -> None:
    locale = await get_locale(state)
    await message.answer(locale.start)


@dp.message(Command("language"))
async def command_language(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    current = data.get("language", DEFAULT_LANGUAGE)
    new_language = "en" if current == "ru" else "ru"
    await state.update_data(language=new_language)
    locale = LOCALES[new_language]
    await message.answer(locale.start)


@dp.message(Command("wiederholen"))
async def command_wiederholen(
    message: Message, state: FSMContext, card_picker: CardPicker
) -> None:
    card = card_picker()
    await state.set_state(UserState.answering)
    await state.update_data(answer=card.answer, explanation=card.explanation)
    await message.answer(card.question, reply_markup=make_keyboard(card))


@dp.callback_query(UserState.answering)
async def handle_answer(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    locale = LOCALES[data.get("language", DEFAULT_LANGUAGE)]
    await state.clear()
    await state.update_data(language=data.get("language", DEFAULT_LANGUAGE))

    language = data.get("language", DEFAULT_LANGUAGE)
    explanation = data["explanation"][language]

    if callback.data == data["answer"]:
        text = f"{locale.correct}\n\n{explanation}"
    else:
        text = f"{locale.wrong.format(answer=data['answer'])}\n\n{explanation}"

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()


async def main() -> None:
    cards = load_cards(CARDS_PATH)
    bot = Bot(token=TOKEN)
    for language_code, locale in LOCALES.items():
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=locale.cmd_start),
                BotCommand(command="wiederholen", description=locale.cmd_wiederholen),
                BotCommand(command="language", description=locale.cmd_language),
            ],
            language_code=language_code,
        )
    await dp.start_polling(bot, card_picker=make_card_picker(cards))


if __name__ == "__main__":
    asyncio.run(main())
