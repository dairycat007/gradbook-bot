import asyncio
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TEAM_CHAT_ID = int(os.getenv("TEAM_CHAT_ID", "0"))
GOOGLE_SHEET_ID = os.getenv(
    "GOOGLE_SHEET_ID",
    "1pjUP2_jVgAiE5qxUQl73NMvZp9rm0g-C9f9xKWbuOHY",
)
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in Railway Variables")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
REQUEST_ROWS = {}


class Form(StatesGroup):
    place = State()
    city = State()
    school_class = State()
    full_name = State()
    phone = State()


def inline_keyboard(*rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Поделиться контактом",
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_sheet():
    if not GOOGLE_CREDENTIALS_JSON:
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).sheet1


def append_lead_to_sheet(message: Message, data: dict, presentation_name: str):
    try:
        sheet = get_sheet()
        if sheet is None:
            print("Google Sheets skipped: GOOGLE_CREDENTIALS_JSON is not set")
            return

        now = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M:%S")
        user = message.from_user
        username = f"@{user.username}" if user.username else ""
        telegram_name = " ".join(filter(None, [user.first_name, user.last_name]))

        row = [
            now,
            str(user.id),
            username,
            telegram_name,
            data.get("place", ""),
            data.get("city", ""),
            data.get("school_class", ""),
            data.get("full_name", ""),
            data.get("phone", ""),
            "да",
            data.get("ads_consent", "нет"),
            presentation_name,
            "нет",
            "новая",
            "",
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        REQUEST_ROWS[user.id] = len(sheet.col_values(1))
    except Exception as e:
        print(f"Google Sheets append error: {e}")


def update_details_in_sheet(user_id: int, value: str):
    try:
        row_number = REQUEST_ROWS.get(user_id)
        if not row_number:
            return

        sheet = get_sheet()
        if sheet is None:
            return

        sheet.update_cell(row_number, 13, value)
    except Exception as e:
        print(f"Google Sheets update error: {e}")


def choose_presentation(data: dict):
    if data.get("place") == "Детский сад":
        return "presentation_kindergarten.pdf", "Детский сад"

    class_text = (data.get("school_class") or "").lower()
    numbers = re.findall(r"\d+", class_text)

    if any(num in {"1", "2", "3", "4"} for num in numbers) or "млад" in class_text:
        return "presentation_school_junior.pdf", "Младшая школа"

    return "presentation_school_senior.pdf", "Старшая школа"


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer_photo(
        photo=FSInputFile("start.jpg"),
        caption=(
            "Хотите заказать классные альбомы для своих детей? 📸\n\n"
            "Давайте соберем анкету, чтобы мы могли отправить вам примеры альбомов для вашего возраста."
        ),
        reply_markup=inline_keyboard([("Начать", "start_form")]),
    )


@dp.callback_query(F.data == "start_form")
async def start_form(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Перед заполнением анкеты ознакомьтесь, пожалуйста, с документами.\n\n"
        "Чтобы продолжить, нужно принять согласие на обработку персональных данных.",
        reply_markup=inline_keyboard(
            [("📄 Политика обработки персональных данных", "doc_policy")],
            [("📄 Согласие на обработку персональных данных", "doc_personal")],
            [("📄 Согласие на получение рекламных сообщений", "doc_ads")],
            [("✅ Принимаю и продолжить", "accept_no_ads")],
            [("✅ Принимаю + хочу получать новости", "accept_ads")],
            [("Не согласен", "decline_legal")],
        ),
    )


@dp.callback_query(F.data == "doc_policy")
async def send_policy(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer_document(FSInputFile("policy_personal_data.pdf"))


@dp.callback_query(F.data == "doc_personal")
async def send_personal(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer_document(FSInputFile("consent_personal_data.pdf"))


@dp.callback_query(F.data == "doc_ads")
async def send_ads(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer_document(FSInputFile("consent_ads.pdf"))


@dp.callback_query(F.data == "decline_legal")
async def decline_legal(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        "Понимаем. Без согласия на обработку персональных данных мы не можем принять заявку через бота."
    )


@dp.callback_query(F.data.in_({"accept_no_ads", "accept_ads"}))
async def accept_legal(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        personal_data_consent="да",
        ads_consent="да" if callback.data == "accept_ads" else "нет",
    )
    await callback.answer()
    await callback.message.answer(
        "Сообщите, пожалуйста: школа или детский сад?",
        reply_markup=inline_keyboard(
            [("🏫 Школа", "school")],
            [("🧸 Детский сад", "kindergarten")],
        ),
    )
    await state.set_state(Form.place)


@dp.callback_query(Form.place, F.data.in_({"school", "kindergarten"}))
async def choose_place(callback: CallbackQuery, state: FSMContext):
    place = "Школа" if callback.data == "school" else "Детский сад"
    await state.update_data(place=place)
    await callback.answer()
    await callback.message.answer("Сообщите, пожалуйста, ваш город.")
    await state.set_state(Form.city)


@dp.message(Form.city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    data = await state.get_data()

    if data.get("place") == "Школа":
        await message.answer("Укажите, из какого класса выпускаются дети?")
        await state.set_state(Form.school_class)
    else:
        await message.answer("Введите ваше имя и фамилию.")
        await state.set_state(Form.full_name)


@dp.message(Form.school_class)
async def get_school_class(message: Message, state: FSMContext):
    await state.update_data(school_class=message.text.strip())
    await message.answer("Введите ваше имя и фамилию.")
    await state.set_state(Form.full_name)


@dp.message(Form.full_name)
async def get_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer(
        "Остался последний шаг до презентации! ✨\n\n"
        "Поделитесь номером телефона, чтобы за вами был закреплен личный менеджер для ответов на вопросы.",
        reply_markup=contact_keyboard(),
    )
    await state.set_state(Form.phone)


@dp.message(Form.phone, F.contact)
async def get_phone_contact(message: Message, state: FSMContext):
    await finish_form(message, state, message.contact.phone_number)


@dp.message(Form.phone)
async def wrong_phone_input(message: Message):
    await message.answer(
        "Пожалуйста, нажмите кнопку «📱 Поделиться контактом» ниже.",
        reply_markup=contact_keyboard(),
    )


async def finish_form(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    data = await state.get_data()
    presentation_file, presentation_name = choose_presentation(data)

    if TEAM_CHAT_ID:
        topic_name = f"{data.get('city')} | {data.get('place')}"
        if data.get("school_class"):
            topic_name += f" | {data.get('school_class')}"

        topic = await bot.create_forum_topic(
            chat_id=TEAM_CHAT_ID,
            name=topic_name[:128],
        )

        manager_text = (
            "🆕 Новая заявка GRADBOOK\n\n"
            f"Имя и фамилия: {data.get('full_name')}\n"
            f"Телефон: {phone}\n"
            f"Город: {data.get('city')}\n"
            f"Тип: {data.get('place')}\n"
            f"Класс: {data.get('school_class', '—')}\n"
            f"Согласие на рассылку: {data.get('ads_consent', 'нет')}\n"
            f"Презентация: {presentation_name}\n\n"
            "Статус: 🟢 Новый\n"
            "Менеджер: Не назначен"
        )

        await bot.send_message(
            chat_id=TEAM_CHAT_ID,
            text=manager_text,
            message_thread_id=topic.message_thread_id,
            reply_markup=inline_keyboard([("🟢 Забрать клиента", "take_client")]),
        )

    await asyncio.to_thread(
        append_lead_to_sheet,
        message,
        data,
        presentation_name,
    )

    await message.answer(
        "Спасибо за ваш ответ. Вот примеры наших альбомов с ценами.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer_document(FSInputFile(presentation_file))
    await message.answer(
        "Если вы сомневаетесь в формате альбома, мы можем рассказать вам о преимуществах и особенностях.\n\n"
        "Хотите подробнее?",
        reply_markup=inline_keyboard(
            [("✅ Да", "details_yes")],
            [("Нет, спасибо", "details_no")],
        ),
    )
    await state.clear()


@dp.callback_query(F.data == "details_yes")
async def details_yes(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "📕 Мини\n\n"
        "Самый компактный формат выпускного альбома, в котором сохранено самое главное.\n\n"
        "Мини — отличный выбор для тех, кто хочет оставить память о выпуске в лаконичном и аккуратном исполнении. "
        "Внутри расположен разворот с виньетками, где собраны портреты всех детей с подписями имен и фамилий. "
        "Такой альбом позволяет спустя годы легко вспомнить каждого одноклассника или воспитанника группы.\n\n"
        "Обложка оформляется в едином фирменном дизайне с названием детского сада, школы или класса, "
        "создавая стильный и современный внешний вид.\n\n"
        "В альбом входит:\n\n"
        "— стильная тематическая обложка с названием класса или группы;\n"
        "— разворот с виньетками всех детей;\n"
        "— подписи с именами и фамилиями;\n"
        "— профессиональная цветокоррекция и лёгкая ретушь фотографий;\n"
        "— качественная печать и плотные материалы.\n\n"
        "Мини — это лаконичный выпускной альбом, который сохраняет самое важное без лишних деталей."
    )

    await callback.message.answer(
        "📖 Планшет\n\n"
        "Красивый и сбалансированный формат, который сочетает компактность и индивидуальность.\n\n"
        "Планшет включает всё необходимое, чтобы сохранить самые яркие воспоминания о выпускном. "
        "На обложке размещается большой портрет ребёнка, благодаря чему альбом становится по-настоящему личным. "
        "Внутри расположен разворот с виньетками, где представлены все дети с подписями имен и фамилий, "
        "а на задней стороне размещается общая фотография класса или группы.\n\n"
        "Такой формат идеально подходит семьям, которые хотят сохранить память о выпуске "
        "в компактном, но полноценном виде.\n\n"
        "В альбом входит:\n\n"
        "— индивидуальный портрет ребёнка на обложке;\n"
        "— разворот с виньетками и подписями всех детей;\n"
        "— общая фотография класса или группы на задней стороне;\n"
        "— профессиональная цветокоррекция и лёгкая ретушь фотографий;\n"
        "— качественная печать и плотные материалы.\n\n"
        "Планшет — это один из самых популярных форматов благодаря удачному сочетанию цены, красоты и информативности."
    )

    await callback.message.answer(
        "📚 Стандарт\n\n"
        "Полноценная история выпускного в одном альбоме.\n\n"
        "Стандарт — это классический выпускной альбом, который позволяет сохранить не только портреты детей, "
        "но и атмосферу целого учебного года. Помимо индивидуального портрета на обложке, разворота с виньетками "
        "и общей фотографии на задней стороне, в альбом входят дополнительные страницы с большим количеством фотографий.\n\n"
        "Во время расширенной фотосессии фотограф создаёт разнообразные портретные, сюжетные и групповые кадры. "
        "Именно они наполняют альбом живыми эмоциями, искренними улыбками и настоящими моментами детства.\n\n"
        "В альбом входит:\n\n"
        "— индивидуальный портрет ребёнка на обложке;\n"
        "— разворот с виньетками и подписями всех детей;\n"
        "— дополнительные страницы с большим количеством фотографий;\n"
        "— портретные, групповые и репортажные снимки;\n"
        "— расширенная фотосессия, включённая в стоимость;\n"
        "— общая фотография класса или группы на задней стороне;\n"
        "— профессиональная обработка всех фотографий;\n"
        "— современный дизайн и качественная печать на плотных страницах.\n\n"
        "Стандарт — это альбом, который спустя годы позволяет не просто увидеть лица одноклассников, "
        "а заново пережить атмосферу выпускного, вспомнить друзей, любимых учителей и самые счастливые моменты детства."
    )

    await callback.message.answer(
        "🎁 При заказе от 20 альбомов — альбом учителю в подарок!"
    )

    asyncio.create_task(
        asyncio.to_thread(
            update_details_in_sheet,
            callback.from_user.id,
            "да",
        )
    )


@dp.callback_query(F.data == "details_no")
async def details_no(callback: CallbackQuery):
    await callback.answer()
    asyncio.create_task(
        asyncio.to_thread(
            update_details_in_sheet,
            callback.from_user.id,
            "нет",
        )
    )
    await callback.message.answer(
        "Спасибо! Ваш менеджер свяжется с вами и ответит на вопросы 😊"
    )


@dp.callback_query(F.data == "take_client")
async def take_client(callback: CallbackQuery):
    await callback.answer("Клиент закреплен за вами")
    await callback.message.edit_text(
        callback.message.text
        + f"\n\n✅ Менеджер: {callback.from_user.full_name}"
        + "\nСтатус: 🟡 В работе"
    )


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
