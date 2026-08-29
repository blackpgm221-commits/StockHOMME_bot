# 👕 БОТ ДЛЯ УЧЁТА ТОВАРОВ (с поиском и пагинацией)

import json
import os
import asyncio
from datetime import datetime
from collections import Counter

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в переменных окружения!")

# ============ СОЗДАНИЕ БОТА ============
bot = Bot(token=TOKEN)
dp = Dispatcher()

print("👕 Запускаю бота для учёта товаров...")
print("🌐 Amnezia VPN должен быть включён!")

# ============ СПИСОК СКЛАДОВ ============
SHOPS = ["Авиапарк", "Европейский"]
user_shop = {}


def get_shop(user_id):
    if user_id not in user_shop:
        user_shop[user_id] = "Авиапарк"
    return user_shop[user_id]


def set_shop(user_id, shop):
    if shop in SHOPS:
        user_shop[user_id] = shop
        return True
    return False


def get_inventory_file(shop):
    return f"inventory_{shop.lower()}.json"


def get_sales_file(shop):
    return f"sales_{shop.lower()}.json"


# ============ ЗАГРУЗКА/СОХРАНЕНИЕ ============

def load_inventory(shop):
    file = get_inventory_file(shop)
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_inventory(shop, inventory):
    file = get_inventory_file(shop)
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)


def load_sales(shop):
    file = get_sales_file(shop)
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_sales(shop, sales):
    file = get_sales_file(shop)
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(sales, f, ensure_ascii=False, indent=2)


# ============ ФУНКЦИЯ ДЛЯ ОТОБРАЖЕНИЯ ТОВАРОВ ============

def format_items(inventory, page, per_page=10):
    """Форматирует список товаров для вывода"""
    start = page * per_page
    end = start + per_page
    items = inventory[start:end]

    if not items:
        return None

    text = f"📋 **Товары (стр. {page + 1}):**\n\n"
    for item in items:
        qty = item["quantity"]
        emoji = "🔴" if qty == 0 else "🟡" if qty <= 2 else "🟢"
        text += f"{emoji} {item['name']} | {item['size']} — {qty} шт.\n"

    total = sum(item["quantity"] for item in inventory)
    text += f"\n📦 Всего: {len(inventory)} позиций, {total} шт."
    return text


def get_pagination_keyboard(page, total_items, per_page=10, action="stock"):
    """Создаёт клавиатуру для пагинации"""
    total_pages = (total_items + per_page - 1) // per_page
    keyboard = []

    if total_pages > 1:
        row = []
        if page > 0:
            row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{action}_prev_{page}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"{action}_next_{page}"))
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============ КЛАВИАТУРА ============

def get_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Все товары")],
            [KeyboardButton(text="🔍 Поиск")],
            [KeyboardButton(text="🛒 Продать")],
            [KeyboardButton(text="📦 Добавить товары")],
            [KeyboardButton(text="🏪 Авиапарк"), KeyboardButton(text="🏪 Европейский")],
        ],
        resize_keyboard=True,
    )


# ============ КОМАНДА /start ============

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    await message.answer(
        f"👕 Привет, {message.from_user.first_name}!\n\n"
        f"📍 Текущий склад: **{shop}**\n\n"
        "📌 **Команды:**\n"
        "• 📋 Все товары — показать товары\n"
        "• 🔍 Поиск — найти товар\n"
        "• 🛒 Продать — продать товар\n"
        "• 📦 Добавить товары — добавить список\n"
        "• 🏪 Авиапарк / 🏪 Европейский — переключить склад",
        reply_markup=get_keyboard()
    )


# ============ ПЕРЕКЛЮЧЕНИЕ СКЛАДА ============

@dp.message(lambda msg: msg.text == "🏪 Авиапарк")
async def switch_to_aviapark(message: types.Message):
    user_id = message.from_user.id
    set_shop(user_id, "Авиапарк")
    await message.answer(f"✅ Переключился на склад: **Авиапарк**")


@dp.message(lambda msg: msg.text == "🏪 Европейский")
async def switch_to_european(message: types.Message):
    user_id = message.from_user.id
    set_shop(user_id, "Европейский")
    await message.answer(f"✅ Переключился на склад: **Европейский**")


# ============ ВСЕ ТОВАРЫ (с пагинацией) ============

@dp.message(lambda msg: msg.text == "📋 Все товары")
async def show_all(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    inventory = load_inventory(shop)

    if not inventory:
        await message.answer(f"📭 На складе **{shop}** пока нет товаров!")
        return

    page = 0
    text = format_items(inventory, page)
    keyboard = get_pagination_keyboard(page, len(inventory), action="stock")

    await message.answer(text, reply_markup=keyboard)


# ============ ОБРАБОТКА ПАГИНАЦИИ ============

@dp.callback_query(lambda c: c.data.startswith('stock_'))
async def handle_stock_pagination(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    shop = get_shop(user_id)

    action, direction, page = callback.data.split('_')
    page = int(page)

    if direction == "prev":
        page -= 1
    elif direction == "next":
        page += 1

    inventory = load_inventory(shop)
    text = format_items(inventory, page)
    keyboard = get_pagination_keyboard(page, len(inventory), action="stock")

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ============ ПОИСК ============

class SearchState(StatesGroup):
    waiting_for_search = State()


@dp.message(lambda msg: msg.text == "🔍 Поиск")
async def search_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🔍 **Поиск товара**\n\n"
        "Напиши название товара (или часть названия):"
    )
    await state.set_state(SearchState.waiting_for_search)


@dp.message(SearchState.waiting_for_search)
async def process_search(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    shop = get_shop(user_id)
    query = message.text.lower()

    inventory = load_inventory(shop)
    results = [item for item in inventory if query in item["name"].lower()]

    await state.clear()

    if not results:
        await message.answer(f"❌ По запросу '{query}' ничего не найдено на складе **{shop}**")
        return

    # Сохраняем результаты поиска в кэш (для пагинации)
    # Используем словарь для хранения последнего поиска
    if not hasattr(dp, 'search_results'):
        dp.search_results = {}
    dp.search_results[user_id] = results

    page = 0
    text = f"🔍 **Результаты поиска** (стр. {page + 1}):\n\n"
    per_page = 10
    start = page * per_page
    items = results[start:start + per_page]

    for item in items:
        qty = item["quantity"]
        emoji = "🔴" if qty == 0 else "🟡" if qty <= 2 else "🟢"
        text += f"{emoji} {item['name']} | {item['size']} — {qty} шт.\n"

    text += f"\n📦 Найдено: {len(results)} позиций"

    # Клавиатура для поиска
    total_pages = (len(results) + per_page - 1) // per_page
    keyboard = []
    if total_pages > 1:
        row = []
        if page > 0:
            row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"search_prev_{page}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"search_next_{page}"))
        keyboard.append(row)

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


# ============ ОБРАБОТКА ПАГИНАЦИИ ПОИСКА ============

@dp.callback_query(lambda c: c.data.startswith('search_'))
async def handle_search_pagination(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    shop = get_shop(user_id)

    action, direction, page = callback.data.split('_')
    page = int(page)

    if direction == "prev":
        page -= 1
    elif direction == "next":
        page += 1

    results = dp.search_results.get(user_id, [])
    if not results:
        await callback.message.edit_text("❌ Результаты поиска устарели. Используйте /search заново.")
        await callback.answer()
        return

    per_page = 10
    start = page * per_page
    items = results[start:start + per_page]

    text = f"🔍 **Результаты поиска** (стр. {page + 1}):\n\n"
    for item in items:
        qty = item["quantity"]
        emoji = "🔴" if qty == 0 else "🟡" if qty <= 2 else "🟢"
        text += f"{emoji} {item['name']} | {item['size']} — {qty} шт.\n"

    text += f"\n📦 Найдено: {len(results)} позиций"

    total_pages = (len(results) + per_page - 1) // per_page
    keyboard = []
    if total_pages > 1:
        row = []
        if page > 0:
            row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"search_prev_{page}"))
        if page < total_pages - 1:
            row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"search_next_{page}"))
        keyboard.append(row)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


# ============ ДОБАВЛЕНИЕ ТОВАРОВ ============

@dp.message(Command("add"))
@dp.message(lambda msg: msg.text == "📦 Добавить товары")
async def add_items_start(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    await message.answer(
        f"📦 **Добавление товаров на склад {shop}**\n\n"
        "Отправь список в формате:\n"
        "`Название Размер Количество`\n\n"
        "**Пример:**\n"
        "`BASE BOMBER M 5`\n"
        "`DIAMOND HOODIE L 3`"
    )


@dp.message(lambda msg: msg.text and not msg.text.startswith('/') and
                        len(msg.text.split()) >= 3 and
                        msg.text.split()[0] not in ["📋", "🛒", "📦", "👕", "🏪", "🔍"])
async def process_add_items(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    await message.answer(f"⏳ Добавляю товары на склад {shop}...")

    inventory = load_inventory(shop)
    lines = message.text.strip().split('\n')
    added = 0
    updated = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        try:
            quantity = int(parts[-1])
            size = parts[-2].upper()
            name = ' '.join(parts[:-2])
        except ValueError:
            continue

        found = False
        for item in inventory:
            if item["name"] == name and item["size"] == size:
                item["quantity"] += quantity
                updated += 1
                found = True
                break

        if not found:
            inventory.append({
                "name": name,
                "size": size,
                "quantity": quantity
            })
            added += 1

    save_inventory(shop, inventory)

    await message.answer(
        f"✅ **Товары добавлены на {shop}!**\n\n"
        f"🆕 Добавлено новых: {added}\n"
        f"🔄 Обновлено: {updated}\n"
        f"📦 Всего: {len(inventory)}"
    )


# ============ ПРОДАЖА ============

@dp.message(Command("sell"))
@dp.message(lambda msg: msg.text == "🛒 Продать")
async def sell_item(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    if message.text == "🛒 Продать":
        await message.answer(
            f"🛒 **Продажа на складе {shop}**\n\n"
            "Напиши: `/sell Название Размер Количество`\n"
            "Например: `/sell BASE BOMBER M 3`"
        )
        return

    args = message.text.split(maxsplit=3)

    if len(args) < 3:
        await message.answer(f"❌ Напиши: `/sell Название Размер Количество`")
        return

    _, name, size = args[0], args[1], args[2]
    size = size.upper()
    quantity = 1

    if len(args) > 3:
        try:
            quantity = int(args[3])
        except ValueError:
            pass

    inventory = load_inventory(shop)

    for item in inventory:
        if item["name"] == name and item["size"] == size:
            if item["quantity"] >= quantity:
                item["quantity"] -= quantity
                save_inventory(shop, inventory)

                sales = load_sales(shop)
                sales.append({
                    "name": name,
                    "size": size,
                    "quantity": quantity,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "shop": shop
                })
                save_sales(shop, sales)

                await message.answer(
                    f"✅ Продано! {name} {size} — {quantity} шт.\n"
                    f"📍 {shop}\n"
                    f"📦 Осталось: {item['quantity']} шт."
                )
            else:
                await message.answer(
                    f"❌ Недостаточно! Есть {item['quantity']} шт., надо {quantity}."
                )
            return

    await message.answer(f"❌ Товар '{name}' {size} не найден на складе {shop}.")


# ============ СТАТИСТИКА ============

@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    user_id = message.from_user.id
    shop = get_shop(user_id)

    sales = load_sales(shop)

    if not sales:
        await message.answer(f"📭 На складе **{shop}** продаж пока нет!")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    today_sales = [s for s in sales if s["date"].startswith(today)]

    text = f"📊 **Статистика ({shop})**\n\n"
    text += f"📦 Всего продаж: {len(sales)} шт.\n"
    text += f"📈 Сегодня: {len(today_sales)} шт.\n\n"

    counter = Counter()
    for sale in sales:
        key = f"{sale['name']} | {sale['size']}"
        counter[key] += sale["quantity"]

    text += "🏆 **ТОП продаж:**\n"
    for key, count in counter.most_common(5):
        text += f"  {key} — {count} шт.\n"

    await message.answer(text)


# ============ ЗАПУСК ============

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())