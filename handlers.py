# handlers.py - Обработчики команд

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

# ============================================
# СОЗДАЕМ РОУТЕР
# ============================================
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
    
    # Добавляем пользователя с автоматической подпиской
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

# КОМАНДЫ /subscribe и /unsubscribe УДАЛЕНЫ

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

# ============================================
# ОБРАБОТЧИК ПРЯМОГО ВВОДА КОДА /zipp765432
# ============================================

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
# АДМИНСКИЕ ОБРАБОТЧИКИ (сокращены для экономии места)
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

# ... (остальные админские обработчики без изменений)
# Для экономии места здесь не все обработчики,
# но в полной версии они все есть

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