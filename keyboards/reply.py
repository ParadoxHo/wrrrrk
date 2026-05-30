from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def commands_keyboard():
    """Постоянная клавиатура с командами управления"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start")],
            [KeyboardButton(text="/finish"), KeyboardButton(text="/stats")],
            [KeyboardButton(text="/help")]
        ],
        resize_keyboard=True
    )
