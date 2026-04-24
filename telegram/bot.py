import os
import asyncio
from datetime import datetime, timezone

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from telegram.storage.subscription import SubscriptionStorage
from parser.fetcher import ArxivFetcher
from telegram.services.digest_service import DigestService


load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
fetcher = ArxivFetcher()
digest_service = DigestService(fetcher)
storage = SubscriptionStorage()


class BotForm(StatesGroup):
    waiting_interval_days = State()
    waiting_topics = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Интервал"), KeyboardButton(text="🏷 Топики")],
            [KeyboardButton(text="⚙️ Мои настройки"), KeyboardButton(text="📰 Дайджест сейчас")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или введите команду…",
    )


def start_only_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Старт")]],
        resize_keyboard=True,
        input_field_placeholder="Нажмите «Старт»…",
    )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для arXiv-дайджестов.\n"
        "Нажмите «Старт», чтобы открыть меню.",
        reply_markup=start_only_kb(),
    )


@dp.message(F.text == "🚀 Старт")
async def btn_open_menu(message: Message):
    await message.answer(
        "Выберите действие:",
        reply_markup=main_menu_kb(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "/start - запуск\n"
        "/help - помощь\n"
        "/set_topics - задать топики через запятую\n"
        "/set_interval - задать интервал в днях\n"
        "/my_settings - показать текущие настройки\n"
        "/digest_now - отправить дайджест сейчас\n"
        "/cancel - отмена ввода"
    )


@dp.message(Command("set_interval"))
async def cmd_set_interval(message: Message, state: FSMContext):
    await state.set_state(BotForm.waiting_interval_days)
    await message.answer("Введите интервал в днях (например, 1, 3, 7)")


@dp.message(F.text == "📅 Интервал")
async def btn_interval(message: Message, state: FSMContext):
  await cmd_set_interval(message, state)


@dp.message(Command("set_topics"))
async def cmd_set_topics(message: Message, state: FSMContext):
    await state.set_state(BotForm.waiting_topics)
    await message.answer(
        "Введите топики через запятую.\n"
        "Пример: llm, nlp, computer vision"
    )


@dp.message(F.text == "🏷 Топики")
async def btn_topics(message: Message, state: FSMContext):
  await cmd_set_topics(message, state)


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return

    await state.clear()
    await message.answer("Ок, отменил ввод.")


@dp.message(F.text == "❌ Отмена")
async def btn_cancel(message: Message, state: FSMContext):
  await cmd_cancel(message, state)



@dp.message(Command("my_settings"))
async def cmd_my_settings(message: Message):
    sub = await storage.get_user(message.chat.id)
    if not sub:
        await message.answer("Настройки пока не заданы. Используйте /set_topics и /set_interval")
        return

    topics_text = ", ".join(sub.topics) if sub.topics else "не выбраны"
    await message.answer(
        f"Ваши настройки:\n"
        f"- Интервал: {sub.interval_days} дн.\n"
        f"- Топики: {topics_text}\n"
        f"- Следующий дайджест: {sub.next_digest_at}"
    )


@dp.message(F.text == "⚙️ Мои настройки")
async def btn_my_settings(message: Message):
  await cmd_my_settings(message)


@dp.message(Command("digest_now"))
async def cmd_digest_now(message: Message):
    sub = await storage.get_user(message.chat.id)
    try:
        messages = await digest_service.build_digest_messages(sub.topics, per_topic_limit=5)
    except Exception as error:
        await message.answer(f"Ошибка при получении дайджеста: {error}")
        return

    if not messages:
        await message.answer("По выбранным топикам пока не найдено статей.")
        return

    for msg in messages:
        await message.answer(msg, parse_mode="HTML")


@dp.message(F.text == "📰 Дайджест сейчас")
async def btn_digest_now(message: Message):
  await cmd_digest_now(message)


@dp.message(BotForm.waiting_interval_days)
async def process_interval_days(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text.isdigit():
        await message.answer("Нужно ввести целое число дней, например: 1, 3 или 7")
        return

    days = int(text)
    if days < 1 or days > 30:
        await message.answer("Допустимый диапазон: от 1 до 30 дней")
        return

    sub = await storage.upsert_user_interval(message.chat.id, days)
    await state.clear()

    await message.answer(
        f"Ок, буду отправлять дайджест каждые {sub.interval_days} дн.\n"
        f"Следующая отправка: {sub.next_digest_at}"
    )


@dp.message(BotForm.waiting_topics)
async def process_topics(message: Message, state: FSMContext):
    raw = (message.text or "").strip()

    if not raw:
        await message.answer("Пустой ввод. Введите хотя бы один топик.")
        return

    topics = [topic.strip().lower() for topic in raw.split(",")]
    topics = [topic for topic in topics if topic]
    unique_topics = list(dict.fromkeys(topics))

    if not unique_topics:
        await message.answer("Не удалось распознать топики. Пример: llm, nlp")
        return

    if len(unique_topics) > 10:
        await message.answer("Можно указать максимум 10 топиков.")
        return

    sub = await storage.set_user_topics(message.chat.id, unique_topics)
    await state.clear()

    await message.answer(
        "Топики сохранены:\n"
        f"{', '.join(sub.topics)}"
    )


async def digest_scheduler_loop(bot: Bot):
    while True:
        try:
            all_subs = await storage.get_all_users()
            now = datetime.now(timezone.utc)

            for sub in all_subs:
                if not sub.topics:
                    continue

                next_at = datetime.fromisoformat(sub.next_digest_at)
                if next_at > now:
                    continue

                await storage.upsert_user_interval(sub.chat_id, sub.interval_days)

                messages = await digest_service.build_digest_messages(sub.topics, per_topic_limit=5)
                for msg in messages:
                    await bot.send_message(sub.chat_id, msg, parse_mode="HTML")

        except Exception as error:
            print(f"[scheduler] error: {error}")

        await asyncio.sleep(60)


async def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(token=TOKEN)
    scheduler_task = asyncio.create_task(digest_scheduler_loop(bot))

    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())