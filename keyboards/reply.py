from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚀 Начать собеседование")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ], resize_keyboard=True)
