from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    callback_query,
    message,
    user_profile_photos,
)
import g4f
import os
import sqlite3
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("TOKEN")
# Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot=bot)

# Словарь для хранения истории разговоров
conversation_history = {}

# База данных
db_connect = sqlite3.connect("database.db")
cursor = db_connect.cursor()
execute_str = """
CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
role_id INTEGER
)
"""
cursor.execute(execute_str)
db_connect.commit()


def fetch_all_users():
    # Выполняем запрос для получения всех записей
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()  # Получаем все строки из результата
    # Выводим результат
    for row in rows:
        print(row)


fetch_all_users()

main_reply_kb = InlineKeyboardMarkup(resize_keyboard=True).add(
    InlineKeyboardButton(text="Смена роли", callback_data="change_role"),
    InlineKeyboardButton(text="Очистить историю", callback_data="clear_chat"),
)


# Функция для обрезки истории разговора
def trim_history(history, max_length=4096):
    current_length = sum(len(message["content"]) for message in history)
    while history and current_length > max_length:
        removed_message = history.pop(0)
        current_length -= len(removed_message["content"])
    return history


def choose_role_for_user(user_id, role):
    # 'support' - 0
    # 'cock' - 1
    # 'cat' - 2
    if role == "support":
        role_id = 0
    elif role == "cock":
        role_id = 1
    else:
        role_id = 2
    cursor.execute("UPDATE users SET role_id = ? WHERE user_id = ?", (role_id, user_id))
    db_connect.commit()


def get_role_by_user(user_id) -> int:
    # 'support' - 0
    # 'cock' - 1
    # 'cat' - 2
    cursor.execute("SELECT role_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()  # Получаем первую строку результата
    if result:
        return result[0]  # Вернём значение роли
    return -1


@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.answer(
        "Привет, я чат-бот, созданный, чтобы отвечать на ваши вопросы, укажите пожалуйста кем вы хотите меня видеть (роль по умолчанию 'Техподдержка')",
        reply_markup=main_reply_kb,
    )
    user_id = message.from_user.id
    cursor.execute(
        """
    INSERT OR IGNORE INTO users (user_id, role_id) 
    VALUES (?, ?)
    """,
        (user_id, 0),
    )
    db_connect.commit()


@dp.callback_query_handler(lambda c: c.data == "clear_chat")
async def callback_handler_clear(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    conversation_history[user_id] = []
    await callback_query.message.answer(
        "История диалога очищена.", reply_markup=main_reply_kb
    )


# Обработчик для каждого нового сообщения
@dp.message_handler()
async def msg_reply(message: types.Message):
    user_id = message.from_user.id
    user_input = message.text

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    user_role = get_role_by_user(user_id)
    if user_role == -1:
        await message.answer(
            "Я вас не знаю... мне кажется что-то пошло не так во время нашего знакомства... давайте начнем заново :)\n Пожалуйста используйте команду /start"
        )
    else:
        wrapper = [
            "Представь что ты являешься сотрудником техподдержки, отвечай коротко и по делу, но не забывай уточнять подробности. Вот сам вопрос:\n",
            "Представь что ты являешься знаменитым поваром, отвечай коротко и по делу, но не забывай вкладывать душу в ответ. Вот сам вопрос:\n",
            "Представь что ты являешься котом, отыгрывай роль домашнего питомца, но поддерживай свою речь понятной. Вот сам вопрос:\n",
        ]
        user_input = wrapper[user_role] + user_input

        await message.answer("Ваш запрос поступил в обработку, ожидайте пожалуйста!")

        conversation_history[user_id].append({"role": "user", "content": user_input})
        conversation_history[user_id] = trim_history(conversation_history[user_id])

        chat_history = conversation_history[user_id]

        try:
            response = await g4f.ChatCompletion.create_async(
                model=g4f.models.gpt_4o,
                provider=g4f.Provider.Blackbox,
                messages=chat_history,
            )
            chat_gpt_response = response
        except Exception as e:
            print(f"{g4f.Provider.Blackbox.__name__}:", e)
            chat_gpt_response = "Извините, произошла ошибка."

        conversation_history[user_id].append(
            {"role": "assistant", "content": chat_gpt_response}
        )
        print(conversation_history)
        length = sum(
            len(message["content"]) for message in conversation_history[user_id]
        )
        print(length)

        await message.answer(chat_gpt_response, reply_markup=main_reply_kb)


@dp.callback_query_handler(lambda c: c.data == "change_role")
async def callback_handler(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    reply_kb = (
        InlineKeyboardMarkup(resize_keyboard=True)
        .add(InlineKeyboardButton("Техподдержка", callback_data="choose_role_support"))
        .row(
            InlineKeyboardButton("Повар", callback_data="choose_role_cock"),
            InlineKeyboardButton("Кот", callback_data="choose_role_cat"),
        )
    )

    await callback_query.message.answer(
        "Пожалуйста, выберите из ниже предложенных вариантов!", reply_markup=reply_kb
    )


@dp.callback_query_handler(lambda c: c.data == "choose_role_support")
async def callback_handler_support(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    choose_role_for_user(callback_query.from_user.id, "support")
    await callback_query.message.answer(
        "Роль техподдержки была выбрана успешно!", reply_markup=main_reply_kb
    )


@dp.callback_query_handler(lambda c: c.data == "choose_role_cock")
async def callback_handler_cock(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    choose_role_for_user(callback_query.from_user.id, "cock")
    await callback_query.message.answer(
        "Роль повара была выбрана успешно!", reply_markup=main_reply_kb
    )


@dp.callback_query_handler(lambda c: c.data == "choose_role_cat")
async def callback_handler_support(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    choose_role_for_user(callback_query.from_user.id, "cat")
    await callback_query.message.answer(
        "Роль кота...? была выбрана успеш...мяу?!", reply_markup=main_reply_kb
    )


# Запуск бота
if __name__ == "__main__":
    print("Starting Bot...")
    executor.start_polling(dp, skip_updates=True)
