import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

urls = [
    'https://abit.itmo.ru/program/master/ai',
    'https://abit.itmo.ru/program/master/ai_product'
]

parsed_data = {}  # Глобальное хранилище результатов


def fetch_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None


def parse_contents_by_headings(html, heading_tag='h2'):
    soup = BeautifulSoup(html, 'html.parser')
    headings = soup.find_all(heading_tag)
    content_by_heading = {}

    for heading in headings:
        title = heading.get_text(strip=True)
        content_parts = []
        next_sib = heading.find_next_sibling()
        while next_sib and next_sib.name != heading_tag:
            content_parts.append(next_sib.get_text(strip=True, separator="\n"))
            next_sib = next_sib.find_next_sibling()
        content = "\n".join(part for part in content_parts if part).strip()
        content_by_heading[title] = content

    return content_by_heading


def parse_multiple_pages(urls, heading_tag='h2'):
    global parsed_data
    all_data = {}
    all_heading_sets = []

    for url in urls:
        html = fetch_html(url)
        if html:
            parsed = parse_contents_by_headings(html, heading_tag)
            all_data[url] = parsed
            all_heading_sets.append(set(parsed.keys()))
        else:
            all_data[url] = {}
            all_heading_sets.append(set())

    if not all_heading_sets:
        parsed_data = {}
        return

    common_headings = set.intersection(*all_heading_sets)

    for url in all_data:
        all_data[url] = {title: all_data[url][title] for title in common_headings}

    parsed_data = all_data


# --- Telegram Handlers ---


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Парсинг сайтов, подождите...")
    parse_multiple_pages(urls)
    if parsed_data:
        await update.message.reply_text(f"Парсинг завершён. Найдено {len(parsed_data[urls[0]])} общих заголовков.")
    else:
        await update.message.reply_text("Ошибка при парсинге сайтов.")


async def show_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not parsed_data:
        await update.message.reply_text("Данные не загружены. Выполните команду /update.")
        return

    url = urls[0]
    common_titles = list(parsed_data[url].keys())
    if not common_titles:
        await update.message.reply_text("Общие заголовки не найдены.")
        return

    keyboard = [
        [InlineKeyboardButton(t, callback_data=f"show_0_{i}")]
        for i, t in enumerate(common_titles)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите заголовок для просмотра:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not parsed_data:
        await query.edit_message_text("Данные отсутствуют. Запустите /update.")
        return

    data = query.data
    parts = data.split('_')
    if len(parts) != 3 or parts[0] != "show":
        await query.edit_message_text("Неверная команда.")
        return

    site_index = int(parts[1])
    title_index = int(parts)

    url = urls[site_index]
    common_titles = list(parsed_data[url].keys())
    if title_index >= len(common_titles):
        await query.edit_message_text("Неверный индекс заголовка.")
        return

    title = common_titles[title_index]
    content = parsed_data[url].get(title, "Содержимое не найдено")

    buttons = []
    other_site_index = 1 - site_index
    if other_site_index < len(urls):
        buttons.append(InlineKeyboardButton(
            f"Показать сайт {other_site_index + 1}",
            callback_data=f"show_{other_site_index}_{title_index}"
        ))

    keyboard = InlineKeyboardMarkup([buttons]) if buttons else None

    msg = f"*{title}*\n\n{content}"
    await query.edit_message_text(msg, reply_markup=keyboard, parse_mode='Markdown')


def register_handlers(application):
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("show", show_command))
    application.add_handler(CallbackQueryHandler(button_handler, pattern=r"show_\d+_\d+"))
