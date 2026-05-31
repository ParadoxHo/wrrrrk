from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def commands_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главная"), KeyboardButton(text="❌ Завершить")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )
