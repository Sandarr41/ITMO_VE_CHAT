from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          CallbackQueryHandler, ContextTypes,
                          MessageHandler, filters)
import re
import URL_parc
from pdf_parc import extract_courses_from_pdf


# Предзагруженные (или заранее считанные) данные из PDF файлов
# Здесь для примера загружаем из файлов, в реальности выгружайте при старте или сохраняйте в памяти
courses_plan1 = extract_courses_from_pdf(open("10130-abit.pdf", "rb"))
courses_plan2 = extract_courses_from_pdf(open("10033-abit.pdf", "rb"))

PAGE_SIZE = 10

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()  # приводим к нижнему регистру для удобства проверки

    if 'привет' in text:
        await start(update, context)

    elif 'план' in text:
        await compare(update, context)

    elif 'что' or 'help' in text:
        await update.message.reply_text("Я могу сравнить программы по следующим заголовкам:")
        await URL_parc.show_command(update, context)

    else:
        await update.message.reply_text("Не понимаю, что ты хочешь сравнить.")

# Вопросы и варианты
QUESTIONS = [
    {
        "question": "Вопрос 1: Как вы оцениваете свои знания в ИИ?",
        "options": ["Начинающий", "Продвинутый"],
    },
    {
        "question": "Вопрос 2: Что вам интереснее?",
        "options": ["Разработка продуктов", "Техническая сторона"],
    }
]
# Рекомендации по итогам (упрощённо)
RECOMMENDATIONS = {
    (0, 0): "Рекомендуем программу Управление ИИ-продуктами/AI Product — для начинающих специалистов, ориентированных на продукты.",
    (1, 1): "Рекомендуем программу Искусственный интеллект — для начинающих технических специалистов.",
    # Добавьте другие варианты
}
async def send_question(update, context, q_index):
    question = QUESTIONS[q_index]['question']
    options = QUESTIONS[q_index]['options']
    keyboard = [
        [InlineKeyboardButton(opt, callback_data=f"answer_{q_index}_{i}")]
        for i, opt in enumerate(options)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        # если вызвали из callback, редактируем сообщение
        await update.callback_query.edit_message_text(text=question, reply_markup=reply_markup)
    else:
        # если из команды /start
        await update.message.reply_text(text=question, reply_markup=reply_markup)

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # формат: answer_<номер_вопроса>_<номер_выбора>
    print(f"Handling callback data: {data}")
    parts = data.split('_')
    if len(parts) != 3 or parts[0] != 'answer':
        return
    q_index = int(parts[1])
    choice = int(parts[2])
    # Сохраняем ответ
    answers = context.user_data.get('answers', [])
    if len(answers) > q_index:
        answers[q_index] = choice
    else:
        answers.append(choice)
    context.user_data['answers'] = answers
    next_q_index = q_index + 1
    if next_q_index < len(QUESTIONS):
        # Следующий вопрос
        await send_question(update, context, next_q_index)
    else:
        # Все вопросы отвечены — выдаём рекомендацию
        key = tuple(context.user_data['answers'])
        recommendation = RECOMMENDATIONS.get(key, "Рекомендация по вашему выбору пока отсутствует.")
        await query.edit_message_text(f"Тест завершён.\n\nРекомендация:\n{recommendation}")
        await URL_parc.update_command(update, context)
        await URL_parc.show_command(update, context)

def build_keyboard(page, max_page):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{page-1}"))
    buttons.append(InlineKeyboardButton(f"Стр. {page+1}/{max_page}", callback_data="noop"))
    if page < max_page - 1:
        buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"next_{page+1}"))
    return InlineKeyboardMarkup([buttons])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я умею сравнивать программы ИИ и Управление продуктами ИИ от ИТМО! Давай найдём подходящую именноя тебе')
    context.user_data['answers'] = []
    await send_question(update, context, 0)

async def compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Общие дисциплины", callback_data='show_common_0')],
        [InlineKeyboardButton("Уникальные для плана 1", callback_data='show_unique_1_0')],
        [InlineKeyboardButton("Уникальные для плана 2", callback_data='show_unique_2_0')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите, что показать:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    print(f"Handling callback data: {data}")

    # Подправленное регулярное выражение для поддержи нужных callback_data
    pattern = r'(show_common|show_unique_1|show_unique_2)_(\d+)'
    match = re.match(pattern, data)
    if match:
        mode, page_str = match.groups()
        page = int(page_str)
    elif data.startswith('next_') or data.startswith('prev_'):
        page = int(data.split('_')[1])
        mode = context.user_data.get('mode', 'show_common')
    else:
        # noop или неизвестные - игнорируем
        return

    context.user_data['mode'] = mode
    context.user_data['page'] = page

    common = courses_plan1 & courses_plan2
    unique1 = courses_plan1 - courses_plan2
    unique2 = courses_plan2 - courses_plan1

    if mode == 'show_common':
        items = sorted(common)
        title = (f"📋 Общие дисциплины (всего {len(common)}):\n"
                 f"Семестр | Название дисциплины | зач. ед | часы")
    elif mode == 'show_unique_1':
        items = sorted(unique1)
        title = (f"📌 Уникальные для плана 1 (всего {len(unique1)}):\n"
                 f"Семестр | Название дисциплины | зач. ед | часы")
    else:  # show_unique_2
        items = sorted(unique2)
        title = (f"📌 Уникальные для плана 2 (всего {len(unique2)}):\n"
                 f"Семестр | Название дисциплины | зач. ед | часы")

    max_page = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, max_page - 1))

    page_items = items[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    msg = f"{title}\n\n" + "\n".join(f"{i+1 + page*PAGE_SIZE}. {item}" for i, item in enumerate(page_items))

    keyboard = build_keyboard(page, max_page)
    await query.edit_message_text(msg, reply_markup=keyboard)



if __name__ == '__main__':
    # Вставьте сюда токен вашего бота
    TOKEN = '7917796591:AAEIX5L59A1YYuvRpvkSbxxLc-9WGlcujd0'

    application = ApplicationBuilder().token(TOKEN).build()


    application.add_handler(CallbackQueryHandler(answer_handler, pattern=r"answer_\d+_\d+"))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(URL_parc.button_handler, pattern=r"show_\d+_\d+"))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    URL_parc.register_handlers(application)
    application.add_handler(CommandHandler("start", start))

    print("Запускаем бот, зарегистрированы хендлеры:")
    print(application.handlers)
    application.run_polling()






