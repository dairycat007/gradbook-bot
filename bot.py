import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)


BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН_БОТА"

TEAM_CHAT_ID = 0  # ID рабочего чата GRADBOOK добавим позже


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


class Form(StatesGroup):
    place = State()
    city = State()
    school_class = State()
    full_name = State()
    phone = State()


def inline_keyboard(*rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=data
                )
                for text, data in row
            ]
            for row in rows
        ]
    )


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Поделиться контактом",
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    await state.clear()

    await message.answer(
        "Хотите заказать классные альбомы для своих детей? 📸\n\n"
        "Давайте соберем анкету, чтобы мы могли отправить вам "
        "примеры альбомов для вашего возраста.",
        reply_markup=inline_keyboard(
            [("Начать", "start_form")]
        )
    )


@dp.callback_query(F.data == "start_form")
async def start_form(
    callback: CallbackQuery,
    state: FSMContext
):

    await callback.answer()

    await callback.message.answer(
        "Сообщите, пожалуйста: школа или детский сад?",
        reply_markup=inline_keyboard(
            [("🏫 Школа", "school")],
            [("🧸 Детский сад", "kindergarten")]
        )
    )

    await state.set_state(Form.place)


@dp.callback_query(
    Form.place,
    F.data.in_({"school", "kindergarten"})
)
async def choose_place(
    callback: CallbackQuery,
    state: FSMContext
):

    if callback.data == "school":
        place = "Школа"
    else:
        place = "Детский сад"

    await state.update_data(place=place)

    await callback.answer()

    await callback.message.answer(
        "Сообщите, пожалуйста, ваш город."
    )

    await state.set_state(Form.city)


@dp.message(Form.city)
async def get_city(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        city=message.text.strip()
    )

    data = await state.get_data()

    if data.get("place") == "Школа":

        await message.answer(
            "Укажите, из какого класса выпускаются дети?"
        )

        await state.set_state(
            Form.school_class
        )

    else:

        await message.answer(
            "Введите ваше имя и фамилию."
        )

        await state.set_state(
            Form.full_name
        )


@dp.message(Form.school_class)
async def get_school_class(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        school_class=message.text.strip()
    )

    await message.answer(
        "Введите ваше имя и фамилию."
    )

    await state.set_state(
        Form.full_name
    )


@dp.message(Form.full_name)
async def get_full_name(
    message: Message,
    state: FSMContext
):

    await state.update_data(
        full_name=message.text.strip()
    )

    await message.answer(
        "Остался последний шаг до презентации! ✨\n\n"
        "Поделитесь номером телефона, чтобы за вами "
        "был закреплен личный менеджер для ответов на вопросы.",
        reply_markup=contact_keyboard()
    )

    await state.set_state(
        Form.phone
    )


@dp.message(Form.phone, F.contact)
async def get_phone_contact(
    message: Message,
    state: FSMContext
):

    phone = message.contact.phone_number

    await finish_form(
        message,
        state,
        phone
    )


@dp.message(Form.phone)
async def wrong_phone_input(
    message: Message
):

    await message.answer(
        "Пожалуйста, нажмите кнопку "
        "«📱 Поделиться контактом» ниже.",
        reply_markup=contact_keyboard()
    )


async def finish_form(
    message: Message,
    state: FSMContext,
    phone: str
):

    await state.update_data(
        phone=phone
    )

    data = await state.get_data()


    # СОЗДАНИЕ ВЕТКИ В РАБОЧЕМ ЧАТЕ

    if TEAM_CHAT_ID:

        topic_name = (
            f"{data.get('city')} | "
            f"{data.get('place')}"
        )

        if data.get("school_class"):

            topic_name += (
                f" | {data.get('school_class')}"
            )


        topic = await bot.create_forum_topic(

            chat_id=TEAM_CHAT_ID,

            name=topic_name[:128]

        )


        manager_text = (

            "🆕 Новая заявка GRADBOOK\n\n"

            f"Имя и фамилия: "
            f"{data.get('full_name')}\n"

            f"Телефон: "
            f"{data.get('phone')}\n"

            f"Город: "
            f"{data.get('city')}\n"

            f"Тип: "
            f"{data.get('place')}\n"

            f"Класс: "
            f"{data.get('school_class', '—')}\n\n"

            "Статус: 🟢 Новый\n"

            "Менеджер: Не назначен"

        )


        await bot.send_message(

            chat_id=TEAM_CHAT_ID,

            text=manager_text,

            message_thread_id=(
                topic.message_thread_id
            ),

            reply_markup=inline_keyboard(

                [
                    (
                        "🟢 Забрать клиента",
                        "take_client"
                    )
                ]

            )

        )


    await message.answer(

        "Спасибо за ваш ответ. "
        "Вот примеры наших альбомов с ценами.",

        reply_markup=ReplyKeyboardRemove()

    )


    await message.answer(

        "Если вы сомневаетесь в формате альбома, "
        "мы можем рассказать вам о преимуществах "
        "и особенностях.\n\n"
        "Хотите подробнее?",

        reply_markup=inline_keyboard(

            [("✅ Да", "details_yes")],

            [("Нет, спасибо", "details_no")]

        )

    )


    await state.clear()


@dp.callback_query(F.data == "details_yes")
async def details_yes(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.answer(

        "📖 Планшет\n\n"

        "Компактный и стильный формат "
        "выпускного альбома.\n\n"

        "Подходит, если хочется красивый "
        "памятный альбом без лишнего объёма.\n\n"

        "📚 Стандарт\n\n"

        "Более наполненный классический "
        "выпускной альбом.\n\n"

        "В нём больше страниц, фотографий "
        "и пространства для воспоминаний."

    )


    await callback.message.answer(

        "🎁 При заказе от 20 альбомов - "
        "альбом учителю в подарок!"

    )


@dp.callback_query(F.data == "details_no")
async def details_no(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.answer(

        "Спасибо! Ваш менеджер свяжется "
        "с вами и ответит на вопросы 😊"

    )


@dp.callback_query(F.data == "take_client")
async def take_client(
    callback: CallbackQuery
):

    await callback.answer(
        "Клиент закреплен за вами"
    )

    await callback.message.edit_text(

        callback.message.text

        + f"\n\n✅ Менеджер: "
        f"{callback.from_user.full_name}"

        + "\nСтатус: 🟡 В работе"

    )


async def main():

    # Удаляем старый webhook.
    # Это обязательно для запуска через polling.

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
