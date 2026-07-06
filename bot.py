import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "7914646524:AAGeBP-MXFQNr4EUjompez-m5X4aNwi344A"
TEAM_CHAT_ID = 0  # сюда позже вставим ID рабочего чата GRADBOOK

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


class Form(StatesGroup):
    place = State()
    school_class = State()
    city = State()
    contact = State()


def keyboard(*rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Хотите заказать классные альбомы для своих детей? 📸\n\n"
        "Давайте соберем анкету, чтобы мы могли отправить вам примеры альбомов для вашего возраста.",
        reply_markup=keyboard([("Начать", "start_form")])
    )


@dp.callback_query(F.data == "start_form")
async def start_form(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "Сообщите, пожалуйста: школа или детский сад?",
        reply_markup=keyboard(
            [("🏫 Школа", "school")],
            [("🧸 Детский сад", "kindergarten")]
        )
    )
    await state.set_state(Form.place)


@dp.callback_query(Form.place, F.data.in_({"school", "kindergarten"}))
async def choose_place(callback: CallbackQuery, state: FSMContext):
    place = "Школа" if callback.data == "school" else "Детский сад"
    await state.update_data(place=place)
    await callback.answer()

    if place == "Школа":
        await callback.message.answer("Укажите, из какого класса выпускаются дети?")
        await state.set_state(Form.school_class)
    else:
        await callback.message.answer("Сообщите, пожалуйста, ваш город.")
        await state.set_state(Form.city)


@dp.message(Form.school_class)
async def get_school_class(message: Message, state: FSMContext):
    await state.update_data(school_class=message.text.strip())
    await message.answer("Сообщите, пожалуйста, ваш город.")
    await state.set_state(Form.city)


@dp.message(Form.city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer(
        "Остался последний шаг до презентации! ✨\n\n"
        "Напишите ваш номер телефона и Имя, для вас будет закреплен личный менеджер для ответов на вопросы."
    )
    await state.set_state(Form.contact)


@dp.message(Form.contact)
async def get_contact(message: Message, state: FSMContext):
    await state.update_data(contact=message.text.strip())
    data = await state.get_data()

    if TEAM_CHAT_ID:
        topic_name = f"{data.get('city', 'Город не указан')} | {data.get('place', 'Тип не указан')}"
        if data.get("school_class"):
            topic_name += f" | {data['school_class']}"

        topic = await bot.create_forum_topic(
            chat_id=TEAM_CHAT_ID,
            name=topic_name[:128]
        )

        manager_text = (
            "🆕 Новая заявка GRADBOOK\n\n"
            f"Имя и телефон: {data.get('contact', '—')}\n"
            f"Город: {data.get('city', '—')}\n"
            f"Тип: {data.get('place', '—')}\n"
            f"Класс: {data.get('school_class', '—')}\n\n"
            "Статус: 🟢 Новый\n"
            "Менеджер: Не назначен"
        )

        await bot.send_message(
            chat_id=TEAM_CHAT_ID,
            text=manager_text,
            message_thread_id=topic.message_thread_id,
            reply_markup=keyboard([("🟢 Забрать клиента", "take_client")])
        )

    await message.answer(
        "Спасибо за ваш ответ. Вот примеры наших альбомов с ценами.\n\n"
        "Если вы сомневаетесь в формате альбома мы можем рассказать вам о преимуществах и особенностях. Хотите подробнее?",
        reply_markup=keyboard(
            [("✅ Да", "details_yes")],
            [("Нет, спасибо", "details_no")]
        )
    )
    await state.clear()


@dp.callback_query(F.data == "details_yes")
async def details_yes(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📖 Планшет\n\n"
        "Компактный и стильный формат выпускного альбома. "
        "Подходит, если хочется красивый памятный альбом без лишнего объёма.\n\n"
        "📚 Стандарт\n\n"
        "Более наполненный классический выпускной альбом. "
        "В нём больше страниц, больше фотографий и больше пространства для воспоминаний."
    )
    await callback.message.answer(
        "🎁 При заказе от 20 альбомов - альбом учителю в подарок!"
    )


@dp.callback_query(F.data == "details_no")
async def details_no(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Спасибо! Ваш менеджер свяжется с вами и ответит на вопросы 😊"
    )


@dp.callback_query(F.data == "take_client")
async def take_client(callback: CallbackQuery):
    await callback.answer("Клиент закреплен за вами")
    await callback.message.edit_text(
        callback.message.text
        + f"\n\n✅ Менеджер: {callback.from_user.full_name}\nСтатус: 🟡 В работе"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
