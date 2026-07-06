import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "7914646524:AAGeBP-MXFQNr4EUjompez-m5X4aNwi344A"
TEAM_CHAT_ID = 0  # сюда позже вставим ID рабочего чата

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    place = State()
    school_class = State()
    city = State()
    contact = State()

def keyboard(*rows):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Хотите заказать классные альбомы для своих детей? 📸\n\n"
        "Давайте соберем анкету, чтобы мы могли отправить вам примеры альбомов для вашего возраста.\n\n"
        "Сообщите, пожалуйста: школа или детский сад?",
        reply_markup=keyboard([("🏫 Школа","school")],[("🧸 Детский сад","kindergarten")])
    )
    await state.set_state(Form.place)

@dp.callback_query(Form.place, F.data.in_({"school","kindergarten"}))
async def choose_place(c: CallbackQuery, state: FSMContext):
    place = "Школа" if c.data == "school" else "Детский сад"
    await state.update_data(place=place)
    await c.answer()
    if place == "Школа":
        await c.message.answer("Укажите, из какого класса выпускаются дети?",
            reply_markup=keyboard([("4 класс","4"),("9 класс","9"),("11 класс","11")]))
        await state.set_state(Form.school_class)
    else:
        await c.message.answer("Сообщите, пожалуйста, ваш город.")
        await state.set_state(Form.city)

@dp.callback_query(Form.school_class)
async def choose_class(c: CallbackQuery, state: FSMContext):
    await state.update_data(school_class=c.data + " класс")
    await c.answer()
    await c.message.answer("Сообщите, пожалуйста, ваш город.")
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
        name = f"{data['city']} | {data['place']}"
        if data.get("school_class"): name += f" | {data['school_class']}"
        topic = await bot.create_forum_topic(TEAM_CHAT_ID, name=name[:128])
        text = (
            "🆕 Новая заявка GRADBOOK\n\n"
            f"Имя и телефон: {data['contact']}\n"
            f"Город: {data['city']}\n"
            f"Тип: {data['place']}\n"
            f"Класс: {data.get('school_class','—')}\n\n"
            "Статус: 🟢 Новый\nМенеджер: Не назначен"
        )
        await bot.send_message(TEAM_CHAT_ID, text, message_thread_id=topic.message_thread_id,
            reply_markup=keyboard([("🟢 Забрать клиента","take")]))

    await message.answer(
        "Спасибо за ваш ответ. Вот примеры наших альбомов с ценами.\n\n"
        "Если вы сомневаетесь в формате альбома мы можем рассказать вам о преимуществах и особенностях. Хотите подробнее?",
        reply_markup=keyboard([("✅ Да","details_yes")],[("Нет, спасибо","details_no")])
    )
    await state.clear()

@dp.callback_query(F.data == "details_yes")
async def details(c: CallbackQuery):
    await c.answer()
    await c.message.answer(
        "📖 Планшет\n\nКомпактный и стильный формат выпускного альбома.\n\n"
        "📚 Стандарт\n\nБолее наполненный альбом с большим количеством страниц и фотографий."
    )
    await c.message.answer("🎁 При заказе от 20 альбомов - альбом учителю в подарок!")

@dp.callback_query(F.data == "details_no")
async def no_details(c: CallbackQuery):
    await c.answer()
    await c.message.answer("Спасибо! Ваш менеджер свяжется с вами 😊")

@dp.callback_query(F.data == "take")
async def take(c: CallbackQuery):
    await c.answer("Клиент закреплен за вами")
    await c.message.edit_text(c.message.text + f"\n\n✅ Менеджер: {c.from_user.full_name}\nСтатус: 🟡 В работе")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
