from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.deepseek import ai_request

router = Router()

class SocialSimStates(StatesGroup):
    choosing_scenario = State()
    in_progress = State()

# ------------------- СЦЕНАРИИ -------------------
SCENARIOS = {
    "salary": {
        "name": "💰 Переговоры о повышении",
        "description": "Вы просите прибавку у начальника в присутствии HR и финдиректора.",
        "personas": [
            {
                "name": "Начальник",
                "role": "system",
                "content": "Ты — начальник отдела. Скептически относишься к повышению зарплат без веских оснований. Задаёшь конкретные вопросы о результатах."
            },
            {
                "name": "HR",
                "role": "system",
                "content": "Ты — HR-менеджер. Поддерживаешь сотрудника, но обязана соблюдать политику компании. Ищешь компромисс."
            },
            {
                "name": "Финдиректор",
                "role": "system",
                "content": "Ты — финансовый директор. Жёстко контролируешь бюджет. Требуешь обоснований и предлагаешь альтернативы (доп. обязанности)."
            }
        ]
    },
    "pitch": {
        "name": "🚀 Питч перед инвесторами",
        "description": "Вы представляете стартап трём скептически настроенным инвесторам.",
        "personas": [
            {
                "name": "Инвестор 1 (технарь)",
                "role": "system",
                "content": "Технический эксперт. Спрашивает про архитектуру, масштабируемость, конкурентов."
            },
            {
                "name": "Инвестор 2 (финансист)",
                "role": "system",
                "content": "Финансовый аналитик. Интересуется юнит-экономикой, CAC, LTV, прогнозами."
            },
            {
                "name": "Инвестор 3 (скептик)",
                "role": "system",
                "content": "Общий скептик. Сомневается в команде, рынке, реализуемости. Задаёт провокационные вопросы."
            }
        ]
    }
}

# ------------------- Клавиатура сценариев -------------------
def social_scenario_kb():
    buttons = []
    for key, sc in SCENARIOS.items():
        buttons.append([InlineKeyboardButton(text=sc["name"], callback_data=f"scenario_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_mode")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ------------------- Вход в режим -------------------
@router.callback_query(F.data == "mode_social")
async def start_social(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Выберите сценарий социального симулятора:",
        reply_markup=social_scenario_kb()
    )
    await state.set_state(SocialSimStates.choosing_scenario)
    await call.answer()

# ------------------- Выбор сценария -------------------
@router.callback_query(SocialSimStates.choosing_scenario, F.data.startswith("scenario_"))
async def scenario_chosen(call: types.CallbackQuery, state: FSMContext):
    key = call.data.split("_", 1)[1]  # всё после первого "_"
    sc = SCENARIOS.get(key)
    if not sc:
        await call.answer("Сценарий не найден", show_alert=True)
        return

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Сейчас начнётся групповая беседа. Ты будешь играть роль одного из персонажей. Говори только за себя."}
    ]
    for p in sc["personas"]:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']}"})

    await state.update_data(
        scenario=key,
        personas=sc["personas"],
        history=system_messages
    )

    persona_list = "\n".join([f"• {p['name']}" for p in sc["personas"]])
    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?"
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

# ------------------- Назад в главное меню -------------------
@router.callback_query(F.data == "back_to_mode")
async def back_to_mode(call: types.CallbackQuery, state: FSMContext):
    from keyboards.inline import mode_selection_kb
    await call.message.edit_text("Выберите режим работы:", reply_markup=mode_selection_kb())
    await state.clear()
    await call.answer()

# ------------------- Обработка сообщений пользователя -------------------
@router.message(SocialSimStates.in_progress, F.text)
async def handle_social_message(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data["history"]
    personas = data["personas"]

    user_msg = f"[Пользователь]: {msg.text}"
    history.append({"role": "user", "content": user_msg})

    responses = []
    for p in personas:
        persona_history = history + [
            {"role": "system", "content": f"Сейчас твоя очередь говорить. Ты — {p['name']}. Отвечай на последнее сообщение пользователя, учитывая предыдущий диалог. Будь краток, реалистичен. Не говори за других."}
        ]
        try:
            reply = await ai_request(persona_history)
        except Exception:
            reply = f"{p['name']}: (промолчал)"
        history.append({"role": "assistant", "content": f"[{p['name']}]: {reply}"})
        responses.append(f"**{p['name']}:** {reply}")

    await state.update_data(history=history)

    for resp in responses:
        await msg.answer(resp, parse_mode="Markdown")

    await msg.answer("✏️ Продолжайте диалог или напишите /finish для завершения.")

# ------------------- Завершение симуляции -------------------
@router.message(Command("finish"), SocialSimStates.in_progress)
async def finish_social(msg: types.Message, state: FSMContext):
    from keyboards.inline import mode_selection_kb
    await msg.answer("🏁 Симуляция завершена.", reply_markup=mode_selection_kb())
    await state.clear()
