import io, json
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from keyboards.inline import rating_kb, catalog_kb
from keyboards.reply import commands_keyboard
from services.deepseek import ai_request

router = Router()

class SocialSimStates(StatesGroup):
    choosing_scenario = State()
    in_progress = State()
    waiting_for_custom_name = State()
    waiting_for_custom_desc = State()
    waiting_for_custom_role = State()
    waiting_for_custom_count = State()
    waiting_for_persona_name = State()
    waiting_for_persona_desc = State()
    adding_persona = State()
    waiting_for_date_gender = State()

SCENARIOS = {
    "salary": {
        "name": "💰 Разговор о повышении",
        "description": "Вы просите прибавку у начальника. Один на один.",
        "personas": [
            {"name": "Начальник", "role": "system",
             "content": "Ты — начальник отдела. Скептически относишься к повышению зарплат без веских оснований. Задаёшь конкретные вопросы о результатах."}
        ]
    },
    "date": {
        "name": "💕 Первое свидание",
        "description": "Романтическая встреча в кафе. Вы и ваш собеседник (пол можно выбрать).",
        "personas": []  # заполняется после выбора пола
    },
    "internet_meeting": {
        "name": "💬 Знакомство в интернете",
        "description": "Вы знакомитесь в чате/приложении. Один собеседник (пол выбирается).",
        "personas": []  # заполняется после выбора пола
    },
    "team_meeting": {
        "name": "👥 Совещание команды",
        "description": "Scrum-встреча: обсуждаете срыв сроков. Вы — тимлид, два разработчика с противоположными мнениями.",
        "personas": [
            {"name": "Разработчик-энтузиаст", "role": "system",
             "content": "Предлагает переписать модуль на новой технологии. Горячий сторонник инноваций, иногда не учитывает сроки."},
            {"name": "Разработчик-консерватор", "role": "system",
             "content": "Против необдуманных изменений, ценит стабильность. Скептик, но надёжный."}
        ]
    }
}

# ---------- Клавиатуры ----------
def custom_persona_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить персонажа", callback_data="add_persona")],
        [InlineKeyboardButton(text="▶️ Начать симуляцию", callback_data="start_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom")]
    ])

def gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 Девушка", callback_data="gender_girl"),
         InlineKeyboardButton(text="👨 Парень", callback_data="gender_guy")]
    ])

# ---------- Вспомогательные функции ----------
async def update_persona_state(current_state, user_message):
    prompt = [
        {"role": "system", "content": f"Ты анализируешь диалог. Текущее состояние персонажа: {json.dumps(current_state, ensure_ascii=False)}. Пользователь сказал: «{user_message}». Как изменились интерес (0-100) и настроение (одно из: злое, раздражённое, нейтральное, заинтересованное, радостное, влюблённое)? Верни только JSON с полями interest (число) и mood (строка)."}
    ]
    try:
        response = await ai_request(prompt)
        j = json.loads(response.strip().replace("'", '"'))
        new_state = {
            "interest": max(0, min(100, j.get("interest", current_state["interest"]))),
            "mood": j.get("mood", current_state["mood"])
        }
        return new_state
    except:
        return current_state

# ---------- Обработчики ----------
@router.callback_query(F.data == "scenario_interview")
async def interview_chosen(call: types.CallbackQuery, state: FSMContext):
    from handlers.interview_setup import start_interview_setup
    await start_interview_setup(call.message, state)
    await call.answer()

@router.callback_query(F.data.startswith("scenario_"))
async def scenario_chosen(call: types.CallbackQuery, state: FSMContext):
    key = call.data.split("_", 1)[1]
    if key == "interview":
        return

    # Сценарии, требующие выбора пола
    if key in ("date", "internet_meeting"):
        sc = SCENARIOS[key]
        await call.message.edit_text(
            f"💕 Выберите пол вашего собеседника:",
            reply_markup=gender_kb()
        )
        await state.update_data(scenario=key)
        await state.set_state(SocialSimStates.waiting_for_date_gender)
        await call.answer()
        return

    sc = SCENARIOS.get(key)
    if not sc:
        await call.answer("Сценарий не найден", show_alert=True)
        return

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Сейчас начнётся групповая беседа. Ты будешь играть роль одного из персонажей. Говори только за себя. Не добавляй своё имя перед ответом."}
    ]
    persona_states = {}
    for p in sc["personas"]:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']} Не добавляй своё имя в начале реплики."})
        persona_states[p["name"]] = {"interest": 50, "mood": "нейтральное"}

    await state.update_data(
        scenario=key,
        personas=sc["personas"],
        history=system_messages,
        persona_states=persona_states
    )

    persona_list = "\n".join([f"• {p['name']}" for p in sc["personas"]])
    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

@router.callback_query(SocialSimStates.waiting_for_date_gender, F.data.startswith("gender_"))
async def gender_chosen(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = data.get("scenario")
    sc = SCENARIOS.get(key)
    if not sc:
        await call.answer("Ошибка", show_alert=True)
        return

    gender = call.data
    if gender == "gender_girl":
        persona_name = "Девушка"
        persona_content = "Обаятельная, с чувством юмора. Задаёт вопросы о хобби, работе, мечтах. Лёгкий флирт."
    else:
        persona_name = "Парень"
        persona_content = "Обаятельный, с чувством юмора. Задаёт вопросы о хобби, работе, мечтах. Лёгкий флирт."

    persona = {"name": persona_name, "role": "system", "content": persona_content}

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Сейчас начнётся беседа. Ты — {persona_name}. Не добавляй своё имя перед ответом."},
        {"role": "system", "content": f"[Роль: {persona_name}] {persona_content} Не добавляй своё имя в начале реплики."}
    ]

    persona_states = {persona_name: {"interest": 50, "mood": "нейтральное"}}

    await state.update_data(
        personas=[persona],
        history=system_messages,
        persona_states=persona_states
    )

    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Собеседник: {persona_name}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

# ---------- Кастомный сценарий ----------
@router.callback_query(F.data == "custom_scenario")
async def custom_scenario_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Давайте создадим ваш уникальный сценарий.\nСначала введите **название** (одним сообщением):")
    await state.set_state(SocialSimStates.waiting_for_custom_name)
    await call.answer()

@router.message(SocialSimStates.waiting_for_custom_name, F.text)
async def custom_name(msg: types.Message, state: FSMContext):
    await state.update_data(custom_name=msg.text.strip())
    await msg.answer("Теперь напишите краткое описание ситуации:")
    await state.set_state(SocialSimStates.waiting_for_custom_desc)

@router.message(SocialSimStates.waiting_for_custom_desc, F.text)
async def custom_desc(msg: types.Message, state: FSMContext):
    await state.update_data(custom_desc=msg.text.strip())
    await msg.answer("Какова **ваша роль** в этом сценарии? (например: менеджер, родитель, друг)")
    await state.set_state(SocialSimStates.waiting_for_custom_role)

@router.message(SocialSimStates.waiting_for_custom_role, F.text)
async def custom_role(msg: types.Message, state: FSMContext):
    role = msg.text.strip()
    await state.update_data(custom_user_role=role, custom_personas=[], custom_persona_index=0)
    await msg.answer("Сколько будет собеседников? (введите число, например 2)")
    await state.set_state(SocialSimStates.waiting_for_custom_count)

@router.message(SocialSimStates.waiting_for_custom_count, F.text)
async def custom_count(msg: types.Message, state: FSMContext):
    try:
        count = int(msg.text)
        if count < 1:
            raise ValueError
    except:
        await msg.answer("Введите целое число от 1 и выше.")
        return

    await state.update_data(custom_total_personas=count, custom_personas=[])
    await msg.answer(f"Отлично! Теперь введите имя и характер для собеседника №1.\nСначала **имя**:")
    await state.set_state(SocialSimStates.waiting_for_persona_name)

@router.message(SocialSimStates.waiting_for_persona_name, F.text)
async def persona_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if not name:
        await msg.answer("Имя не может быть пустым.")
        return
    await state.update_data(temp_persona_name=name)
    await msg.answer(f"Теперь введите **характер** для «{name}»:")
    await state.set_state(SocialSimStates.waiting_for_persona_desc)

@router.message(SocialSimStates.waiting_for_persona_desc, F.text)
async def persona_desc(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("temp_persona_name", "Безымянный")
    description = msg.text.strip()
    if not description:
        await msg.answer("Описание не может быть пустым.")
        return

    personas = data.get("custom_personas", [])
    personas.append({"name": name, "role": "system", "content": description})
    total = data.get("custom_total_personas", 0)
    current = len(personas)

    if current < total:
        await state.update_data(custom_personas=personas, temp_persona_name=None)
        await msg.answer(f"✅ Персонаж «{name}» добавлен ({current}/{total}).\nТеперь введите имя для собеседника №{current+1}:")
        await state.set_state(SocialSimStates.waiting_for_persona_name)
    else:
        await state.update_data(custom_personas=personas, temp_persona_name=None)
        await msg.answer(f"✅ Все {total} персонажей добавлены.\nНажмите «▶️ Начать симуляцию» или «❌ Отмена».",
                         reply_markup=custom_persona_kb())
        await state.set_state(SocialSimStates.adding_persona)

@router.callback_query(SocialSimStates.adding_persona, F.data == "start_custom")
async def start_custom(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    personas = data.get("custom_personas", [])
    if not personas:
        await call.answer("Добавьте хотя бы одного персонажа!", show_alert=True)
        return
    name = data.get("custom_name", "Мой сценарий")
    desc = data.get("custom_desc", "")
    user_role = data.get("custom_user_role", "участник")

    system_messages = [
        {"role": "system", "content": f"Сценарий: {name}. {desc}. Роль пользователя: {user_role}. Сейчас начнётся групповая беседа. Ты — один из персонажей. Не добавляй своё имя перед ответом."}
    ]
    for p in personas:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']} Не добавляй своё имя в начале реплики."})

    await state.update_data(
        scenario="custom",
        personas=personas,
        history=system_messages,
        persona_states={}
    )
    persona_list = "\n".join([f"• {p['name']}" for p in personas])
    await call.message.edit_text(
        f"🎬 Ваш сценарий: {name}\n\n{desc}\n\n"
        f"Ваша роль: {user_role}\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

@router.callback_query(SocialSimStates.adding_persona, F.data == "cancel_custom")
async def cancel_custom(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Создание сценария отменено.", reply_markup=catalog_kb())
    await state.clear()
    await call.answer()

# ---------- Игровой процесс (без автоматических подсказок) ----------
@router.message(SocialSimStates.in_progress, F.text)
async def handle_social_message(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data["history"]
    personas = data["personas"]
    persona_states = data.get("persona_states", {})

    user_msg = msg.text
    history.append({"role": "user", "content": user_msg})

    responses = []
    for p in personas:
        p_name = p["name"]
        current_state = persona_states.get(p_name, {"interest": 50, "mood": "нейтральное"})
        state_desc = f"Текущее состояние: интерес {current_state['interest']}/100, настроение: {current_state['mood']}."
        persona_history = history + [
            {"role": "system", "content": f"Сейчас твоя очередь говорить. Ты — {p_name}. {state_desc} Отвечай на последнее сообщение пользователя, учитывая предыдущий диалог и своё настроение. Будь краток, реалистичен. Не говори за других. Не добавляй своё имя перед ответом."}
        ]
        try:
            reply = await ai_request(persona_history)
        except Exception:
            reply = "..."
        history.append({"role": "assistant", "content": reply})

        if persona_states and p_name in persona_states:
            new_state = await update_persona_state(current_state, user_msg)
            persona_states[p_name] = new_state

        responses.append(f"**{p_name}:** {reply}")

    await state.update_data(history=history, persona_states=persona_states)

    for resp in responses:
        await msg.answer(resp, parse_mode="Markdown")

# ---------- Глобальный /finish ----------
@router.message(Command("finish"))
async def global_finish(msg: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await msg.answer("🔄 Действие отменено. Возврат в каталог.", reply_markup=catalog_kb())
        await msg.answer("⌨️ Используйте кнопки для управления:", reply_markup=commands_keyboard())
    else:
        await msg.answer("Вы не в активном сценарии.", reply_markup=commands_keyboard())

# ---------- Завершение и анализ ----------
@router.message(Command("finish"), SocialSimStates.in_progress)
async def finish_social_analyze(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])
    scenario_name = data.get("scenario", "сценарий")

    await msg.answer("Оцените сценарий:", reply_markup=rating_kb())

    analysis_prompt = history + [
        {"role": "system", "content": "Проведи анализ прошедшего диалога. Оцени навыки общения пользователя по 10-балльной шкале, выдели сильные стороны, дай 1-2 конкретных совета по улучшению. Будь краток."}
    ]
    try:
        analysis = await ai_request(analysis_prompt)
    except Exception:
        analysis = "Анализ временно недоступен."

    await msg.answer(f"📊 **Анализ симуляции «{scenario_name}»:**\n{analysis}", parse_mode="Markdown")
    await msg.answer("Спасибо за участие! Возвращайтесь в каталог.", reply_markup=catalog_kb())

@router.callback_query(F.data.startswith("rate_"))
async def rate_scenario(call: types.CallbackQuery, state: FSMContext):
    rating = call.data.split("_")[1]
    if rating == "like":
        await call.answer("👍 Спасибо за оценку!")
    else:
        await call.answer("👎 Спасибо за обратную связь!")
    await call.message.edit_text("Спасибо за участие!", reply_markup=None)

# ---------- Экспорт диалога ----------
@router.message(Command("export"), SocialSimStates.in_progress)
async def export_dialog(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])
    if not history:
        await msg.answer("Нет истории для экспорта.")
        return

    lines = ["=== ДИАЛОГ ==="]
    for entry in history:
        role = entry["role"]
        content = entry["content"]
        if role == "user":
            lines.append(f"Вы: {content}")
        elif role == "assistant":
            lines.append(content)
    text = "\n".join(lines)

    file = BufferedInputFile(text.encode("utf-8"), filename="dialog.txt")
    await msg.answer_document(file, caption="Ваш диалог")
