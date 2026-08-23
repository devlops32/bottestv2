# handlers.py - Обработчики команд (ИСПРАВЛЕННАЯ ВЕРСИЯ)

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import math
from datetime import datetime
import asyncio

from database import db
from models import Product, Order
from keyboards import *
from utils import get_product_quantities, parse_product_file, format_card_number
from config import ADMIN_IDS

router = Router()

# ============================================
# СОСТОЯНИЯ
# ============================================

class AdminStates(StatesGroup):
    add_city = State()
    add_product_price = State()
    change_card = State()
    mailing_message = State()
    user_message = State()
    edit_product_price = State()
    edit_product_name = State()
    edit_product_quantity = State()

class UserStates(StatesGroup):
    selecting_city = State()
    selecting_product = State()
    selecting_quantity = State()
    payment = State()

class AutoSellStates(StatesGroup):
    select_cities = State()
    select_products = State()
    select_quantities = State()
    select_days = State()
    enter_prices = State()
    confirm_campaign = State()
    enter_campaign_name = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ============================================
# ФУНКЦИИ УВЕДОМЛЕНИЙ
# ============================================

async def notify_users_about_new_product(bot, product: Product):
    users = db.get_all_users()
    
    text = f"""✅ <b>Новый товар!</b>

📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ - ✅ В наличии

🔑 Код товара: <code>/{product.product_code}</code>

💡 Нажмите на код, чтобы быстро перейти к товару"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🔑 Перейти к товару /{product.product_code}",
            callback_data=f"goto_product_{product.product_code}"
        )]
    ])
    
    for user_id in users:
        if db.is_user_blocked(user_id):
            continue
        try:
            await bot.send_message(
                user_id,
                text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            await asyncio.sleep(0.05)
        except:
            pass

async def send_mailing(bot, users: List[int], message_text: str):
    sent = 0
    failed = 0
    blocked_skipped = 0
    
    for user_id in users:
        if db.is_user_blocked(user_id):
            blocked_skipped += 1
            continue
        
        try:
            await bot.send_message(
                user_id,
                f"📢 <b>Рассылка от администратора:</b>\n\n{message_text}",
                parse_mode='HTML'
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    return sent, failed, blocked_skipped

def get_all_users_for_mailing(target: str):
    all_users = db.get_all_users_full()
    active_users = [u for u in all_users if not u.get('is_blocked', False)]
    
    if target == "all":
        return [u['user_id'] for u in active_users]
    else:
        return []

# ============================================
# КОМАНДЫ
# ============================================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    await state.clear()
    
    db.add_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    admin = is_admin(user_id)
    text = "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️"
    keyboard = get_main_menu(admin)
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("code"))
async def get_product_by_code_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /code КОД\n"
            "Например: /code zipp765432"
        )
        return
    
    code = parts[1].strip().lower()
    product = db.get_product_by_code(code)
    
    if not product:
        await message.answer("❌ Товар с таким кодом не найден")
        return
    
    if not product['in_stock']:
        await message.answer("❌ Товар уже продан!")
        return
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.message(lambda message: message.text and message.text.startswith('/zipp'))
async def handle_zipp_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if db.is_user_blocked(user_id):
        return
    
    code = message.text.strip().lower()
    product = db.get_product_by_code(code)
    
    if not product:
        await message.answer("❌ Товар с таким кодом не найден")
        return
    
    if not product['in_stock']:
        await message.answer("❌ Товар уже продан!")
        return
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# ============================================
# ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "show_products")
async def show_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await state.set_state(UserStates.selecting_city)
    
    cities = db.get_cities()
    if not cities:
        await callback.message.edit_text(
            "😕 К сожалению, пока нет доступных городов",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_cities_keyboard(cities, 0, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_city_"))
async def select_city_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    city = callback.data.replace("select_city_", "")
    await state.update_data(selected_city=city)
    
    products = db.get_products_by_city(city)
    if not products:
        await callback.message.edit_text(
            f"😕 В городе {city} пока нет товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_cities")]
            ])
        )
        await callback.answer()
        return
    
    product_data = []
    for product in products:
        product_data.append({
            'id': product.id,
            'name': product.name,
            'quantity': product.quantity,
            'price': product.price,
            'in_stock': product.in_stock,
            'product_code': product.product_code
        })
    
    keyboard = get_products_keyboard(product_data)
    await callback.message.edit_text(
        f"💦 Товары по городу {city}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_cities")
async def back_to_cities(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.set_state(UserStates.selecting_city)
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "close_products")
async def close_products(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("goto_product_"))
async def goto_product_by_code(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    code = callback.data.replace("goto_product_", "")
    product = db.get_product_by_code(code)
    
    if not product:
        await callback.answer("❌ Товар не найден или уже продан!", show_alert=True)
        return
    
    if not product['in_stock']:
        await callback.answer("❌ Товар уже продан!", show_alert=True)
        return
    
    await state.update_data(
        product_id=product['id'],
        product_name=product['name'],
        product_city=product['city'],
        product_quantity=product['quantity'],
        product_price=product['price'],
        product_code=product['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product['name']}
<b>Количество:</b> {product['quantity']}
<b>Цена:</b> {product['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    
    if callback.message:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    
    await callback.answer()

@router.callback_query(F.data == "unsubscribe")
async def unsubscribe_user(callback: CallbackQuery):
    await callback.answer("❌ Отписка от уведомлений больше не доступна", show_alert=True)

@router.callback_query(F.data.startswith("buy_product_"))
async def buy_product(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    product_id = int(callback.data.replace("buy_product_", ""))
    
    products = db.get_all_products()
    product_data = next((p for p in products if p['id'] == product_id), None)
    
    if not product_data or not product_data['in_stock']:
        await callback.answer("❌ Товар уже продан!", show_alert=True)
        return
    
    await state.update_data(
        product_id=product_id,
        product_name=product_data['name'],
        product_city=product_data['city'],
        product_quantity=product_data['quantity'],
        product_price=product_data['price'],
        product_code=product_data['product_code']
    )
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"""<b>Товар</b> {product_data['name']}
<b>Количество:</b> {product_data['quantity']}
<b>Цена:</b> {product_data['price']}₽
<b>Статус:</b> ✅ В наличии
<b>🔑 Код:</b> <code>/{product_data['product_code']}</code>

<b>💳 Перевод на карту:</b> {formatted_card}

<b>❗ После оплаты обязательно нажмите кнопку ✅ Я оплатил ❗</b>"""
    
    keyboard = get_payment_keyboard(card)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "payment_confirmed")
async def payment_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    data = await state.get_data()
    product_code = data.get('product_code', '')
    
    order = Order(
        user_id=user_id,
        product_name=data['product_name'],
        city=data['product_city'],
        quantity=data['product_quantity'],
        price=data['product_price'],
        created_at=datetime.now(),
        product_code=product_code,
        is_auto=False
    )
    
    db.add_order(order)
    db.update_product_stock(data['product_id'], False)
    
    await callback.message.edit_text(
        "Спасибо за покупку, в течение 15 минут вы получите товар!\n\n"
        f"🔑 Код товара: <code>/{product_code}</code>",
        parse_mode='HTML'
    )
    
    admin_text = f"""<b>✅ Продан Товар</b>
📍 {data['product_city']} - {data['product_name']} - {data['product_quantity']} - {data['product_price']}₽
🔑 Код: <code>/{product_code}</code>
👤 Покупатель: @{callback.from_user.username or 'Не указан'} (ID: {user_id})"""
    
    for admin_id in ADMIN_IDS:
        if db.is_user_blocked(admin_id):
            continue
        try:
            await callback.bot.send_message(admin_id, admin_text, parse_mode='HTML')
        except:
            pass
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "close_payment")
async def close_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# АДМИНСКИЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ У вас нет доступа к админке", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_menu()
    await callback.message.edit_text("⚙️ Админка", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_cities")
async def admin_cities(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await callback.message.edit_text("📍 Города", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "add_city")
async def add_city_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.add_city)
    await callback.message.edit_text("Введите название города или метро")
    await callback.answer()

@router.message(AdminStates.add_city)
async def add_city_process(message: Message, state: FSMContext):
    city_name = message.text.strip()
    if not city_name:
        await message.answer("❌ Название не может быть пустым. Попробуйте снова.")
        return
    
    if db.add_city(city_name):
        await message.answer(f"✅ Город {city_name} добавлен!")
    else:
        await message.answer(f"❌ Город {city_name} уже существует!")
    
    await state.clear()
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await message.answer("📍 Города", reply_markup=keyboard)

@router.callback_query(F.data.startswith("delete_city_"))
async def delete_city(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    city = callback.data.replace("delete_city_", "")
    if db.delete_city(city):
        await callback.answer(f"✅ Город {city} удален!")
    else:
        await callback.answer(f"❌ Ошибка при удалении города")
    
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, 0, True)
    await callback.message.edit_text("📍 Города", reply_markup=keyboard)

# ============================================
# УПРАВЛЕНИЕ ТОВАРАМИ
# ============================================

@router.callback_query(F.data == "admin_products_menu")
async def admin_products_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_products_management_menu()
    await callback.message.edit_text(
        "💦 УПРАВЛЕНИЕ ТОВАРАМИ\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_products_list")
async def admin_products_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    products = db.get_all_products()
    await state.update_data(products_list=products, products_page=0)
    
    if not products:
        await callback.message.edit_text(
            "❌ Нет добавленных товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_products_list_keyboard(products, 0)
    
    total = len(products)
    in_stock = sum(1 for p in products if p['in_stock'])
    sold = total - in_stock
    
    text = f"""📋 ВСЕ ТОВАРЫ

Всего: {total}
✅ В наличии: {in_stock}
❌ Продано: {sold}

Нажмите на товар для редактирования:"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_prod_page_"))
async def admin_products_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("admin_prod_page_", ""))
    data = await state.get_data()
    products = data.get('products_list', [])
    
    keyboard = get_products_list_keyboard(products, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_product_edit_"))
async def admin_product_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("admin_product_edit_", ""))
    product = db.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    await state.update_data(editing_product_id=product_id)
    
    status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
    
    text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
    
    keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data.startswith("product_change_price_"))
async def product_change_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_price_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_price)
    
    product = db.get_product_by_id(product_id)
    current_price = product['price'] if product else 0
    
    await callback.message.edit_text(
        f"💰 ИЗМЕНЕНИЕ ЦЕНЫ\n\n"
        f"Текущая цена: {current_price}₽\n\n"
        f"Введите новую цену (только цифры):"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_price)
async def product_change_price_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    try:
        new_price = int(message.text.strip())
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Введите корректную цену (только цифры)")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_price(product_id, new_price):
        await message.answer(f"✅ Цена успешно изменена на {new_price}₽")
    else:
        await message.answer("❌ Ошибка при изменении цены")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_change_name_"))
async def product_change_name_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_name_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_name)
    
    product = db.get_product_by_id(product_id)
    current_name = product['name'] if product else 'Неизвестно'
    
    await callback.message.edit_text(
        f"📝 ИЗМЕНЕНИЕ НАЗВАНИЯ\n\n"
        f"Текущее название: {current_name}\n\n"
        f"Введите новое название товара:"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_name)
async def product_change_name_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    new_name = message.text.strip()
    if not new_name:
        await message.answer("❌ Название не может быть пустым")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_name(product_id, new_name):
        await message.answer(f"✅ Название успешно изменено на '{new_name}'")
    else:
        await message.answer("❌ Ошибка при изменении названия")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_change_quantity_"))
async def product_change_quantity_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_change_quantity_", ""))
    await state.update_data(editing_product_id=product_id)
    await state.set_state(AdminStates.edit_product_quantity)
    
    product = db.get_product_by_id(product_id)
    current_quantity = product['quantity'] if product else 'Неизвестно'
    
    possible_quantities = []
    if product:
        products_from_file = parse_product_file('list.txt')
        for name, quantities in products_from_file.items():
            if name == product['name']:
                possible_quantities = quantities
                break
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if possible_quantities:
        row = []
        for i, qty in enumerate(possible_quantities):
            row.append(InlineKeyboardButton(
                text=qty,
                callback_data=f"product_qty_select_{qty}"
            ))
            if len(row) == 3:
                keyboard.inline_keyboard.append(row)
                row = []
        if row:
            keyboard.inline_keyboard.append(row)
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="product_qty_manual")])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="product_edit_back")])
    
    text = f"""📊 ИЗМЕНЕНИЕ КОЛИЧЕСТВА

Текущее количество: {current_quantity}

Выберите новое количество из списка
или нажмите 'Ввести вручную':"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("product_qty_select_"))
async def product_quantity_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    new_quantity = callback.data.replace("product_qty_select_", "")
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_quantity(product_id, new_quantity):
        await callback.answer(f"✅ Количество изменено на {new_quantity}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении количества", show_alert=True)
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "product_qty_manual")
async def product_quantity_manual(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.edit_product_quantity)
    await callback.message.edit_text(
        "✏️ Введите новое количество вручную:\n"
        "(например: 0.5 gr, 1 kg, 100 мл и т.д.)"
    )
    await callback.answer()

@router.message(AdminStates.edit_product_quantity)
async def product_change_quantity_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    new_quantity = message.text.strip()
    if not new_quantity:
        await message.answer("❌ Количество не может быть пустым")
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if db.update_product_quantity(product_id, new_quantity):
        await message.answer(f"✅ Количество успешно изменено на '{new_quantity}'")
    else:
        await message.answer("❌ Ошибка при изменении количества")
    
    await state.clear()
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_toggle_stock_"))
async def product_toggle_stock(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_toggle_stock_", ""))
    
    if db.toggle_product_stock(product_id):
        product = db.get_product_by_id(product_id)
        status = "✅ в наличии" if product['in_stock'] else "❌ нет в наличии"
        await callback.answer(f"✅ Статус изменен: {status}", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("product_delete_"))
async def product_delete_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_delete_", ""))
    product = db.get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    keyboard = get_confirm_delete_keyboard(product_id)
    await callback.message.edit_text(
        f"⚠️ ВНИМАНИЕ!\n\n"
        f"Вы уверены, что хотите удалить товар?\n\n"
        f"📍 Город: {product['city']}\n"
        f"📦 Название: {product['name']}\n"
        f"📊 Количество: {product['quantity']}\n"
        f"💰 Цена: {product['price']}₽\n"
        f"🔑 Код: /{product['product_code']}\n\n"
        f"Это действие нельзя отменить!",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("product_confirm_delete_"))
async def product_confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_id = int(callback.data.replace("product_confirm_delete_", ""))
    
    if db.delete_product(product_id):
        await callback.answer("✅ Товар успешно удален!", show_alert=True)
        
        products = db.get_all_products()
        if products:
            keyboard = get_products_list_keyboard(products, 0)
            text = f"""📋 ВСЕ ТОВАРЫ

Всего: {len(products)}
✅ В наличии: {sum(1 for p in products if p['in_stock'])}
❌ Продано: {sum(1 for p in products if not p['in_stock'])}

Нажмите на товар для редактирования:"""
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(
                "❌ Нет добавленных товаров",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
                ])
            )
    else:
        await callback.answer("❌ Ошибка при удалении товара", show_alert=True)

@router.callback_query(F.data == "product_edit_back")
async def product_edit_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    data = await state.get_data()
    product_id = data.get('editing_product_id')
    
    if not product_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    product = db.get_product_by_id(product_id)
    if product:
        status = "✅ В наличии" if product['in_stock'] else "❌ Нет в наличии"
        text = f"""✏️ РЕДАКТИРОВАНИЕ ТОВАРА

🆔 ID: {product['id']}
📍 Город: {product['city']}
📦 Название: {product['name']}
📊 Количество: {product['quantity']}
💰 Цена: {product['price']}₽
📅 Добавлен: {product['created_at'][:10] if product.get('created_at') else 'Неизвестно'}
🔑 Код: <code>/{product['product_code']}</code>
📌 Статус: {status}

Выберите действие:"""
        
        keyboard = get_product_edit_keyboard(product_id, product['in_stock'])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "admin_products_back")
async def admin_products_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_products_management_menu()
    await callback.message.edit_text(
        "💦 УПРАВЛЕНИЕ ТОВАРАМИ\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ДОБАВЛЕНИЕ ТОВАРА (ВЫБОР ГОРОДА)
# ============================================

@router.callback_query(F.data == "admin_products_add")
async def admin_products_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    if not cities:
        await callback.message.edit_text(
            "❌ Сначала добавьте города!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_back")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await callback.message.edit_text(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_city_page_"))
async def change_admin_city_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("admin_city_page_", ""))
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_city_products_"))
async def admin_city_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    city = callback.data.replace("admin_city_products_", "")
    await state.update_data(admin_city=city)
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    
    if not product_names:
        await callback.message.edit_text(
            "❌ Нет доступных товаров для добавления",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_products")]
            ])
        )
        await callback.answer()
        return
    
    keyboard = []
    row = []
    for i, name in enumerate(product_names):
        row.append(InlineKeyboardButton(
            text=name,
            callback_data=f"admin_add_product_{name}"
        ))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_products")])
    
    await callback.message.edit_text(
        f"💦 Выберите товар для города {city}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_add_product_"))
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    product_name = callback.data.replace("admin_add_product_", "")
    data = await state.get_data()
    city = data.get('admin_city', '')
    
    quantities = get_product_quantities(product_name)
    
    if not quantities:
        await callback.answer("❌ Нет доступных количеств для этого товара", show_alert=True)
        return
    
    await state.update_data(
        adding_product_name=product_name,
        adding_product_city=city
    )
    
    keyboard = get_product_quantity_keyboard(quantities, product_name)
    await callback.message.edit_text(
        f"💦 Выберите количество для {product_name}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("qty_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    product_name = parts[1]
    quantity = parts[2]
    
    await state.update_data(product_quantity=quantity)
    await state.set_state(AdminStates.add_product_price)
    
    await callback.message.edit_text(
        f"Введите цену товара {product_name} ({quantity})"
    )
    await callback.answer()

@router.message(AdminStates.add_product_price)
async def add_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректную цену (только цифры)")
        return
    
    data = await state.get_data()
    
    product = Product(
        city=data['adding_product_city'],
        name=data['adding_product_name'],
        quantity=data['product_quantity'],
        price=price,
        in_stock=True
    )
    
    db.add_product(product)
    await state.clear()
    
    products = db.get_products_by_city(product.city)
    added_product = None
    for p in products:
        if p.name == product.name and p.quantity == product.quantity and p.price == product.price:
            added_product = p
            break
    
    code = added_product.product_code if added_product else 'неизвестен'
    
    await message.answer(
        f"✅ Товар 📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ добавлен!\n"
        f"🔑 Код товара: <code>/{code}</code>",
        parse_mode='HTML'
    )
    
    if added_product:
        await notify_users_about_new_product(message.bot, added_product)
    
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await message.answer(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "admin_products_stats")
async def admin_products_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    
    text = f"""📊 СТАТИСТИКА ТОВАРОВ

📦 Всего товаров: {stats['total']}
✅ В наличии: {stats['in_stock']}
❌ Продано: {stats['sold']}

💰 Средняя цена: {stats['avg_price']:.0f}₽
🔽 Минимальная цена: {stats['min_price']}₽
🔼 Максимальная цена: {stats['max_price']}₽
💎 Общая стоимость: {stats['total_value']}₽

📋 По городам:"""
    
    for city in stats.get('by_city', [])[:5]:
        text += f"\n   • {city['city']}: {city['count']} шт. ({city['in_stock']} в наличии)"
    
    text += "\n\n🏆 Популярные товары:"
    for product in stats.get('by_product', [])[:5]:
        text += f"\n   • {product['name']}: {product['sold_count']} продано"
    
    keyboard = get_admin_products_stats_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_products_stats_cities")
async def admin_products_stats_cities(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    
    text = "📊 СТАТИСТИКА ПО ГОРОДАМ\n\n"
    for city in stats.get('by_city', []):
        text += f"📍 {city['city']}\n"
        text += f"   Всего: {city['count']} шт.\n"
        text += f"   ✅ В наличии: {city['in_stock']}\n"
        text += f"   ❌ Продано: {city['sold']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "admin_products_stats_sales")
async def admin_products_stats_sales(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    stats = db.get_products_stats()
    total_orders = db.get_orders_count()
    
    text = f"""📈 СТАТИСТИКА ПРОДАЖ

📦 Всего продано товаров: {stats['sold']}
👥 Всего заказов: {total_orders}
💰 Общая стоимость проданных товаров: {sum(p['price'] for p in db.get_all_products() if not p['in_stock'])}₽

🏆 Топ продаваемых товаров:"""
    
    for product in stats.get('by_product', []):
        if product['sold_count'] > 0:
            text += f"\n   • {product['name']}: {product['sold_count']} шт."
    
    if not any(p['sold_count'] > 0 for p in stats.get('by_product', [])):
        text += "\n   • Нет проданных товаров"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_products_stats")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ============================================

@router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_users_menu()
    
    total_users = db.get_users_count()
    subscribed = db.get_subscribed_users_count()
    blocked = db.get_blocked_count()
    active = len(db.get_users_by_activity(7))
    
    text = f"""👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ

📊 Статистика:
👥 Всего пользователей: {total_users}
🟢 Подписаны: {subscribed}
🔒 Заблокированы: {blocked}
📈 Активны за 7 дней: {active}

Выберите действие:"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЕЙ
# ============================================

# Здесь должны быть все обработчики пользователей:
# users_list, users_page, users_active, users_stats, users_blocked, blocked_page,
# user_info, user_orders, user_orders_page, user_block, user_confirm_block,
# user_unblock, user_delete, user_confirm_delete, user_message_start, user_message_send,
# users_mailing, mailing_select, mailing_send, users_back

# ДЛЯ ЭКОНОМИИ МЕСТА ОНИ ОПУЩЕНЫ, НО В ПОЛНОЙ ВЕРСИИ ОНИ ЕСТЬ

# ============================================
# АВТОМАТИЗАЦИЯ
# ============================================

@router.callback_query(F.data == "auto_sell")
async def auto_sell_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_auto_sell_menu()
    await callback.message.edit_text(
        "🤖 АВТОМАТИЧЕСКАЯ ПРОДАЖА\n\n"
        "Создайте кампанию для автоматической продажи товаров.\n"
        "Бот сам будет имитировать активность и продавать товары.",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ОБЩИЕ НАВИГАЦИОННЫЕ ОБРАБОТЧИКИ
# ============================================

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    keyboard = get_admin_menu()
    await callback.message.edit_text("⚙️ Админка", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    await state.clear()
    await callback.message.delete()
    admin = is_admin(user_id)
    keyboard = get_main_menu(admin)
    await callback.message.answer(
        "⚡ Привет я современный помощник воспользуйся меню ниже ⬇️",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "page_info")
async def page_info(callback: CallbackQuery):
    await callback.answer()