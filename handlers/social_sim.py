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
    waiting_for_custom_name = State()
    waiting_for_custom_desc = State()
    adding_persona = State()
    confirm_personas = State()
    waiting_for_date_gender = State()       # выбор пола на свидании

# ------------------- 10 БАЗОВЫХ СЦЕНАРИЕВ -------------------
SCENARIOS = {
    "salary": {
        "name": "💰 Переговоры о повышении",
        "description": "Вы просите прибавку у начальника в присутствии HR и финдиректора.",
        "personas": [
            {"name": "Начальник", "role": "system", "content": "Ты — начальник отдела. Скептически относишься к повышению зарплат без веских оснований. Задаёшь конкретные вопросы о результатах."},
            {"name": "HR", "role": "system", "content": "Ты — HR-менеджер. Поддерживаешь сотрудника, но обязана соблюдать политику компании. Ищешь компромисс."},
            {"name": "Финдиректор", "role": "system", "content": "Ты — финансовый директор. Жёстко контролируешь бюджет. Требуешь обоснований и предлагаешь альтернативы."}
        ]
    },
    "pitch": {
        "name": "🚀 Питч перед инвесторами",
        "description": "Вы представляете стартап трём инвесторам.",
        "personas": [
            {"name": "Инвестор-технарь", "role": "system", "content": "Технический эксперт. Спрашивает про архитектуру, масштабируемость, конкурентов."},
            {"name": "Инвестор-финансист", "role": "system", "content": "Финансовый аналитик. Интересуется юнит-экономикой, CAC, LTV, прогнозами."},
            {"name": "Инвестор-скептик", "role": "system", "content": "Сомневается в команде, рынке, реализуемости. Задаёт провокационные вопросы."}
        ]
    },
    "client_conflict": {
        "name": "📞 Конфликт с VIP-клиентом",
        "description": "Недовольный заказчик требует срочных изменений. Вы — менеджер проекта, также участвует технический специалист.",
        "personas": [
            {"name": "VIP-клиент", "role": "system", "content": "Требовательный клиент с большим бюджетом. Недоволен сроками и качеством. Эмоциональный, перебивает, но готов к конструктиву."},
            {"name": "Техлид", "role": "system", "content": "Технический руководитель. Защищает команду, объясняет реалистичность требований. Спокойный, но уверенный."}
        ]
    },
    "team_meeting": {
        "name": "👥 Совещание команды",
        "description": "Scrum-встреча: обсуждаете срыв сроков. Вы — тимлид, два разработчика с противоположными мнениями.",
        "personas": [
            {"name": "Разработчик-энтузиаст", "role": "system", "content": "Предлагает переписать модуль на новой технологии. Горячий сторонник инноваций, иногда не учитывает сроки."},
            {"name": "Разработчик-консерватор", "role": "system", "content": "Против необдуманных изменений, ценит стабильность. Скептик, но надёжный."}
        ]
    },
    "project_defense": {
        "name": "🎓 Защита проекта",
        "description": "Защита дипломной работы перед комиссией из трёх преподавателей.",
        "personas": [
            {"name": "Профессор-добряк", "role": "system", "content": "Хочет, чтобы студент раскрылся. Задаёт мягкие наводящие вопросы."},
            {"name": "Доцент-придира", "role": "system", "content": "Ищет слабые места в методологии и расчётах. Ставит каверзные вопросы."},
            {"name": "Ассистент-наблюдатель", "role": "system", "content": "В основном молчит, но иногда вставляет замечания по оформлению или литературе."}
        ]
    },
    "family_discussion": {
        "name": "🏠 Семейный разговор",
        "description": "Подросток хочет бросить школу и заняться музыкой. Вы — один из родителей.",
        "personas": [
            {"name": "Подросток", "role": "system", "content": "16 лет, мечтает стать музыкантом, считает школу бесполезной. Эмоциональный, иногда дерзкий."},
            {"name": "Мать", "role": "system", "content": "Переживает за будущее ребёнка. Хочет поддержать, но боится нестабильности творческой карьеры."}
        ]
    },
    "neighbor_dispute": {
        "name": "🏘️ Спор с соседом",
        "description": "Сосед жалуется на шум после 23:00. Вы пытаетесь уладить конфликт мирно.",
        "personas": [
            {"name": "Сосед-пенсионер", "role": "system", "content": "Раздражённый пожилой человек, жалуется на громкую музыку. Требует тишины."},
            {"name": "Участковый", "role": "system", "content": "Пришёл разобраться. Нейтрален, но склонен успокоить обе стороны."}
        ]
    },
    "supplier_negotiation": {
        "name": "📦 Переговоры с поставщиком",
        "description": "Поставщик задерживает партию товара. Вы — менеджер по закупкам.",
        "personas": [
            {"name": "Поставщик", "role": "system", "content": "Оправдывается логистическими проблемами, предлагает скидку на следующий заказ."},
            {"name": "Финансовый контролёр", "role": "system", "content": "Внутренний сотрудник, который напоминает о штрафных санкциях и бюджете."}
        ]
    },
    "date": {
        "name": "💕 Первое свидание",
        "description": "Романтическая встреча в кафе. Вы и ваш собеседник (пол можно выбрать).",
        "personas": []   # персонаж будет создан после выбора пола
    },
    "reprimand": {
        "name": "⚠️ Воспитательная беседа",
        "description": "Начальник вызывает подчинённого из-за серьёзной ошибки в отчёте.",
        "personas": [
            {"name": "Начальник", "role": "system", "content": "Строгий, но справедливый. Требует объяснений и плана исправления."}
        ]
    }
}

# ------------------- Клавиатуры -------------------
def custom_persona_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить персонажа", callback_data="add_persona")],
        [InlineKeyboardButton(text="▶️ Начать симуляцию", callback_data="start_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom")]
    ])

def date_gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 Девушка", callback_data="date_girl"),
         InlineKeyboardButton(text="👨 Парень", callback_data="date_guy")]
    ])

# ------------------- Обработчик каталога: выбор сценария -------------------
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

    if key == "date":
        await call.message.edit_text(
            "💕 Выберите пол вашего собеседника:",
            reply_markup=date_gender_kb()
        )
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
    for p in sc["personas"]:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']} Не добавляй своё имя в начале реплики."})

    await state.update_data(
        scenario=key,
        personas=sc["personas"],
        history=system_messages
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

# ------------------- Выбор пола для свидания -------------------
@router.callback_query(SocialSimStates.waiting_for_date_gender, F.data.startswith("date_"))
async def date_gender_chosen(call: types.CallbackQuery, state: FSMContext):
    gender = call.data
    if gender == "date_girl":
        persona_name = "Девушка"
        persona_content = "Обаятельная, с чувством юмора. Задаёт вопросы о хобби, работе, мечтах. Лёгкий флирт."
    else:
        persona_name = "Парень"
        persona_content = "Обаятельный, с чувством юмора. Задаёт вопросы о хобби, работе, мечтах. Лёгкий флирт."

    sc = SCENARIOS["date"]
    persona = {"name": persona_name, "role": "system", "content": persona_content}

    system_messages = [
        {"role": "system", "content": f"Сценарий: {sc['name']}. {sc['description']}. Сейчас начнётся беседа. Ты — {persona_name}. Не добавляй своё имя перед ответом."},
        {"role": "system", "content": f"[Роль: {persona_name}] {persona_content} Не добавляй своё имя в начале реплики."}
    ]

    await state.update_data(
        scenario="date",
        personas=[persona],
        history=system_messages
    )

    await call.message.edit_text(
        f"🎬 Сценарий: {sc['name']}\n\n{sc['description']}\n\n"
        f"Собеседник: {persona_name}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

@router.callback_query(F.data == "custom_scenario")
async def custom_scenario_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Давайте создадим ваш уникальный сценарий.\n"
        "Сначала введите **название** (одним сообщением):"
    )
    await state.set_state(SocialSimStates.waiting_for_custom_name)
    await call.answer()

# ------------------- Создание кастомного сценария -------------------
@router.message(SocialSimStates.waiting_for_custom_name, F.text)
async def custom_name(msg: types.Message, state: FSMContext):
    await state.update_data(custom_name=msg.text.strip())
    await msg.answer("Теперь напишите краткое описание ситуации:")
    await state.set_state(SocialSimStates.waiting_for_custom_desc)

@router.message(SocialSimStates.waiting_for_custom_desc, F.text)
async def custom_desc(msg: types.Message, state: FSMContext):
    await state.update_data(custom_desc=msg.text.strip(), custom_personas=[])
    await msg.answer(
        "Отлично! Теперь будем добавлять персонажей.\n"
        "На каждого персонажа отправьте **одно сообщение** в формате:\n"
        "`Имя: характер`\n\n"
        "Например: `Босс: строгий, требует отчёт`\n\n"
        "Когда закончите, нажмите кнопку ниже.",
        reply_markup=custom_persona_kb()
    )
    await state.set_state(SocialSimStates.adding_persona)

@router.callback_query(SocialSimStates.adding_persona, F.data == "add_persona")
async def prompt_persona(call: types.CallbackQuery):
    await call.message.answer("Жду описание персонажа в формате `Имя: характер`")
    await call.answer()

@router.message(SocialSimStates.adding_persona, F.text)
async def add_persona(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    personas = data.get("custom_personas", [])
    parts = msg.text.split(":", 1)
    if len(parts) != 2:
        await msg.answer("Неверный формат. Используйте: `Имя: описание характера`")
        return
    name = parts[0].strip()
    description = parts[1].strip()
    personas.append({"name": name, "role": "system", "content": description})
    await state.update_data(custom_personas=personas)
    await msg.answer(f"✅ Персонаж «{name}» добавлен. Всего персонажей: {len(personas)}",
                     reply_markup=custom_persona_kb())

@router.callback_query(SocialSimStates.adding_persona, F.data == "start_custom")
async def start_custom(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    personas = data.get("custom_personas", [])
    if not personas:
        await call.answer("Добавьте хотя бы одного персонажа!", show_alert=True)
        return
    name = data.get("custom_name", "Мой сценарий")
    desc = data.get("custom_desc", "")
    system_messages = [
        {"role": "system", "content": f"Сценарий: {name}. {desc}. Сейчас начнётся групповая беседа. Не добавляй своё имя перед ответом."}
    ]
    for p in personas:
        system_messages.append({"role": "system", "content": f"[Роль: {p['name']}] {p['content']} Не добавляй своё имя в начале реплики."})

    await state.update_data(
        scenario="custom",
        personas=personas,
        history=system_messages
    )
    persona_list = "\n".join([f"• {p['name']}" for p in personas])
    await call.message.edit_text(
        f"🎬 Ваш сценарий: {name}\n\n{desc}\n\n"
        f"Участники:\n{persona_list}\n\n"
        "Начинайте беседу. Ваше первое сообщение?\n"
        "ℹ️ Для завершения используйте /finish."
    )
    await state.set_state(SocialSimStates.in_progress)
    await call.answer()

@router.callback_query(SocialSimStates.adding_persona, F.data == "cancel_custom")
async def cancel_custom(call: types.CallbackQuery, state: FSMContext):
    from keyboards.inline import catalog_kb
    await call.message.edit_text("Создание сценария отменено.", reply_markup=catalog_kb())
    await state.clear()
    await call.answer()

# ------------------- Игровой процесс -------------------
@router.message(SocialSimStates.in_progress, F.text)
async def handle_social_message(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    history = data["history"]
    personas = data["personas"]

    user_msg = msg.text
    history.append({"role": "user", "content": user_msg})

    responses = []
    for p in personas:
        persona_history = history + [
            {"role": "system", "content": f"Сейчас твоя очередь говорить. Ты — {p['name']}. Отвечай на последнее сообщение пользователя, учитывая предыдущий диалог. Будь краток, реалистичен. Не говори за других. Не добавляй своё имя перед ответом."}
        ]
        try:
            reply = await ai_request(persona_history)
        except Exception:
            reply = "..."
        history.append({"role": "assistant", "content": reply})
        responses.append(f"**{p['name']}:** {reply}")

    await state.update_data(history=history)

    for resp in responses:
        await msg.answer(resp, parse_mode="Markdown")

# ------------------- Завершение -------------------
@router.message(Command("finish"), SocialSimStates.in_progress)
async def finish_social(msg: types.Message, state: FSMContext):
    from keyboards.inline import catalog_kb
    await msg.answer("🏁 Симуляция завершена.", reply_markup=catalog_kb())
    await state.clear()
