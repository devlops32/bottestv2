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

@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    if not cities:
        await callback.message.edit_text(
            "❌ Сначала добавьте города!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
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

@router.callback_query(F.data == "admin_payment")
async def admin_payment(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    card = db.get_setting('card_number', '')
    formatted_card = format_card_number(card) if card else 'не указана'
    
    text = f"💳 Оплата\n\n<b>Ваша карта:</b> {formatted_card}"
    keyboard = get_admin_payment_keyboard()
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "change_card")
async def change_card_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.change_card)
    await callback.message.edit_text("Введите номер карты в любом формате")
    await callback.answer()

@router.message(AdminStates.change_card)
async def change_card_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    card = message.text.strip()
    db.set_setting('card_number', card)
    await state.clear()
    
    formatted_card = format_card_number(card)
    text = f"💳 Оплата\n\n<b>Ваша карта:</b> {formatted_card}"
    keyboard = get_admin_payment_keyboard()
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    orders_count = db.get_orders_count()
    cities_count = len(db.get_cities())
    products = db.get_all_products()
    products_count = len(products)
    in_stock = sum(1 for p in products if p['in_stock'])
    users_count = db.get_users_count()
    blocked_count = db.get_blocked_count()
    
    text = f"""📊 СТАТИСТИКА

👥 Пользователей: {users_count}
🔒 Заблокировано: {blocked_count}
👥 Заказов: {orders_count}
📍 Городов: {cities_count}
💦 Товаров всего: {products_count}
✅ В наличии: {in_stock}
❌ Продано: {products_count - in_stock}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
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

@router.callback_query(F.data == "users_list")
async def users_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_all_users_full()
    await state.update_data(users_list=users, users_page=0)
    
    keyboard = get_users_list_keyboard(users, 0)
    
    text = f"👥 ВСЕ ПОЛЬЗОВАТЕЛИ\n\nВсего: {len(users)}"
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("users_page_"))
async def users_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("users_page_", ""))
    data = await state.get_data()
    users = data.get('users_list', [])
    
    keyboard = get_users_list_keyboard(users, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_active")
async def users_active(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_users_by_activity(7)
    
    if not users:
        await callback.answer("❌ Нет активных пользователей за 7 дней", show_alert=True)
        return
    
    text = "📊 АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ (7 дней)\n\n"
    for user in users[:10]:
        username = user.get('username', 'Нет username')
        first_name = user.get('first_name', 'Без имени')
        text += f"👤 {first_name} (@{username}) - {user['orders_count']} заказов, {user['total_spent']}₽\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_stats")
async def users_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    total_users = db.get_users_count()
    subscribed = db.get_subscribed_users_count()
    blocked = db.get_blocked_count()
    
    all_orders = db.get_auto_orders(365)
    total_spent = sum(o.get('price', 0) for o in all_orders)
    
    cities = db.get_cities()
    city_stats = []
    for city in cities:
        products = db.get_products_by_city(city)
        city_stats.append(f"📍 {city}: {len(products)} товаров")
    
    text = f"""📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ

👥 Всего пользователей: {total_users}
🟢 Подписаны: {subscribed}
🔒 Заблокированы: {blocked}
📈 Всего заказов: {db.get_orders_count()}
💰 Общая выручка: {total_spent}₽

🏙️ По городам:
{chr(10).join(city_stats[:5])}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "users_blocked")
async def users_blocked_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    users = db.get_blocked_users()
    await state.update_data(blocked_users=users)
    
    if not users:
        await callback.answer("❌ Нет заблокированных пользователей", show_alert=True)
        return
    
    keyboard = get_blocked_users_keyboard(users, 0)
    await callback.message.edit_text(
        f"🔒 ЗАБЛОКИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ\n\nВсего: {len(users)}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("blocked_page_"))
async def blocked_users_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("blocked_page_", ""))
    data = await state.get_data()
    users = data.get('blocked_users', [])
    
    keyboard = get_blocked_users_keyboard(users, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_info_"))
async def user_info(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_info_", ""))
    user_data = db.get_user_stats(user_id)
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    stats = user_data.get('stats', {})
    last_orders = user_data.get('last_orders', [])
    is_blocked = user_data.get('is_blocked', False)
    
    text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ{" 🔒" if is_blocked else ""}

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽
• Средний чек: {stats.get('avg_price', 0):.0f}₽

🔒 Статус: {'<b>ЗАБЛОКИРОВАН</b>' if is_blocked else '✅ Не заблокирован'}
{"📅 Заблокирован: " + user_data.get('blocked_at', '')[:10] if is_blocked else ''}

📦 Последние заказы:"""
    
    if last_orders:
        for order in last_orders[:3]:
            text += f"\n  • {order['product_name']} | {order['price']}₽ | {order.get('created_at', '')[:10]}"
    else:
        text += "\n  • Нет заказов"
    
    keyboard = get_user_info_keyboard(user_id, is_blocked)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data.startswith("user_orders_"))
async def user_orders(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_orders_", ""))
    orders = db.get_user_orders(user_id, 10)
    await state.update_data(user_orders=orders, user_orders_page=0)
    
    if not orders:
        await callback.answer("❌ У пользователя нет заказов", show_alert=True)
        return
    
    keyboard = get_user_orders_keyboard(orders, 0)
    await callback.message.edit_text(
        f"📦 ИСТОРИЯ ЗАКАЗОВ\n\nВсего: {len(orders)} заказов",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("user_orders_page_"))
async def user_orders_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("user_orders_page_", ""))
    data = await state.get_data()
    orders = data.get('user_orders', [])
    
    keyboard = get_user_orders_keyboard(orders, page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("user_block_"))
async def user_block(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_block_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, заблокировать", callback_data=f"user_confirm_block_{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"user_info_{user_id}")
        ]
    ])
    
    user_data = db.get_user_stats(user_id)
    if user_data:
        name = user_data.get('first_name', 'Пользователь')
        await callback.message.edit_text(
            f"⚠️ ВНИМАНИЕ!\n\n"
            f"Вы уверены, что хотите заблокировать пользователя {name}?\n\n"
            f"После блокировки:\n"
            f"❌ Пользователь не сможет пользоваться ботом\n"
            f"❌ Уведомления не будут отправляться\n"
            f"❌ При /start не будет ответа\n\n"
            f"Вы всегда сможете разблокировать его.",
            reply_markup=keyboard
        )
    await callback.answer()

@router.callback_query(F.data.startswith("user_confirm_block_"))
async def user_confirm_block(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_confirm_block_", ""))
    
    if db.block_user(user_id):
        await callback.answer("🔒 Пользователь заблокирован!", show_alert=True)
        
        user_data = db.get_user_stats(user_id)
        if user_data:
            stats = user_data.get('stats', {})
            text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ 🔒

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽

🔒 Статус: <b>ЗАБЛОКИРОВАН</b>
📅 Заблокирован: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            keyboard = get_user_info_keyboard(user_id, is_blocked=True)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.answer("❌ Ошибка при блокировке пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_unblock_"))
async def user_unblock(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_unblock_", ""))
    
    if db.unblock_user(user_id):
        await callback.answer("🔓 Пользователь разблокирован!", show_alert=True)
        
        user_data = db.get_user_stats(user_id)
        if user_data:
            stats = user_data.get('stats', {})
            text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽

🔓 Статус: <b>Разблокирован</b>"""
            
            keyboard = get_user_info_keyboard(user_id, is_blocked=False)
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        await callback.answer("❌ Ошибка при разблокировке пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_delete_"))
async def user_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_delete_", ""))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"user_confirm_delete_{user_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"user_info_{user_id}")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ ВНИМАНИЕ!\n\n"
        "Вы уверены, что хотите удалить этого пользователя?\n"
        "Все данные пользователя будут безвозвратно удалены.",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("user_confirm_delete_"))
async def user_confirm_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_confirm_delete_", ""))
    
    if db.delete_user(user_id):
        await callback.answer("✅ Пользователь удален!", show_alert=True)
        
        keyboard = get_users_menu()
        await callback.message.edit_text(
            "👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ\n\n"
            "Пользователь успешно удален.",
            reply_markup=keyboard
        )
    else:
        await callback.answer("❌ Ошибка при удалении пользователя", show_alert=True)

@router.callback_query(F.data.startswith("user_message_"))
async def user_message_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.replace("user_message_", ""))
    await state.update_data(message_user_id=user_id)
    await state.set_state(AdminStates.user_message)
    
    await callback.message.edit_text(
        "📝 Введите сообщение для пользователя:\n"
        "(можно использовать HTML-разметку)"
    )
    await callback.answer()

@router.message(AdminStates.user_message)
async def user_message_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    user_id = data.get('message_user_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    if db.is_user_blocked(user_id):
        await message.answer("❌ Пользователь заблокирован, сообщение не отправлено")
        await state.clear()
        return
    
    try:
        await message.bot.send_message(
            user_id,
            f"📨 <b>Сообщение от администратора:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
        await message.answer("✅ Сообщение отправлено пользователю!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()
    
    user_data = db.get_user_stats(user_id)
    if user_data:
        stats = user_data.get('stats', {})
        is_blocked = user_data.get('is_blocked', False)
        text = f"""👤 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ{" 🔒" if is_blocked else ""}

🆔 ID: {user_data['user_id']}
👤 Имя: {user_data.get('first_name', 'Не указано')}
📛 Username: @{user_data.get('username', 'Не указан')}
📅 Зарегистрирован: {user_data.get('created_at', '')[:10]}

📊 Статистика:
• Всего заказов: {stats.get('total_orders', 0)}
• Потрачено: {stats.get('total_spent', 0)}₽"""
        
        keyboard = get_user_info_keyboard(user_id, is_blocked)
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "users_mailing")
async def mailing_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    keyboard = get_mailing_keyboard()
    await callback.message.edit_text(
        "📬 РАССЫЛКА\n\n"
        "Выберите получателей:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("mailing_"))
async def mailing_select(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    target = callback.data.replace("mailing_", "")
    await state.update_data(mailing_target=target)
    await state.set_state(AdminStates.mailing_message)
    
    users = get_all_users_for_mailing(target)
    total = len(users)
    
    if target == "all":
        text = f"👥 Всем пользователям ({total} чел.)"
    else:
        await callback.answer("❌ Неверный выбор", show_alert=True)
        return
    
    if total == 0:
        await callback.answer("❌ Нет получателей для рассылки", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📬 РАССЫЛКА\n\n"
        f"Получатели: {text}\n\n"
        f"📝 Введите сообщение для рассылки:\n"
        f"(можно использовать HTML-разметку)"
    )
    await callback.answer()

@router.message(AdminStates.mailing_message)
async def mailing_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    target = data.get('mailing_target')
    
    users = get_all_users_for_mailing(target)
    
    if not users:
        await message.answer("❌ Нет получателей для рассылки")
        await state.clear()
        return
    
    sent, failed, blocked_skipped = await send_mailing(message.bot, users, message.text)
    
    await state.clear()
    
    await message.answer(
        f"✅ РАССЫЛКА ЗАВЕРШЕНА!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}\n"
        f"🔒 Пропущено (заблокированы): {blocked_skipped}"
    )
    
    keyboard = get_users_menu()
    await message.answer(
        "👥 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "users_back")
async def users_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.clear()
    await admin_users_menu(callback, state)

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

@router.callback_query(F.data == "auto_create")
async def auto_create_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AutoSellStates.enter_campaign_name)
    await callback.message.edit_text(
        "📝 Введите название кампании:\n"
        "(например: 'Осенняя распродажа 2024')"
    )
    await callback.answer()

@router.message(AutoSellStates.enter_campaign_name)
async def auto_create_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    name = message.text.strip()
    await state.update_data(campaign_name=name)
    await state.set_state(AutoSellStates.select_cities)
    
    cities = db.get_cities()
    if not cities:
        await message.answer(
            "❌ Сначала добавьте города в разделе '📍 Города'",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_sell")]
            ])
        )
        return
    
    keyboard = get_campaign_cities_keyboard(cities, [])
    await message.answer(
        f"📍 Выберите города для кампании '{name}':\n"
        "(нажмите на город для выбора, ✅ - выбран)",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("camp_city_"))
async def auto_select_city(callback: CallbackQuery, state: FSMContext):
    city = callback.data.replace("camp_city_", "")
    data = await state.get_data()
    selected_cities = data.get('selected_cities', [])
    
    if city in selected_cities:
        selected_cities.remove(city)
    else:
        selected_cities.append(city)
    
    await state.update_data(selected_cities=selected_cities)
    
    cities = db.get_cities()
    keyboard = get_campaign_cities_keyboard(cities, selected_cities)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "camp_cities_clear")
async def auto_clear_cities(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_cities=[])
    cities = db.get_cities()
    keyboard = get_campaign_cities_keyboard(cities, [])
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Выбор очищен")

@router.callback_query(F.data == "camp_cities_done")
async def auto_cities_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_cities = data.get('selected_cities', [])
    
    if not selected_cities:
        await callback.answer("❌ Выберите хотя бы один город!", show_alert=True)
        return
    
    await state.set_state(AutoSellStates.select_products)
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    
    keyboard = get_campaign_products_keyboard(product_names, [])
    await callback.message.edit_text(
        f"📦 Выберите товары для кампании:\n"
        f"Города: {', '.join(selected_cities)}",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("camp_prod_"))
async def auto_select_product(callback: CallbackQuery, state: FSMContext):
    product = callback.data.replace("camp_prod_", "")
    data = await state.get_data()
    selected_products = data.get('selected_products', [])
    
    if product in selected_products:
        selected_products.remove(product)
    else:
        selected_products.append(product)
    
    await state.update_data(selected_products=selected_products)
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    keyboard = get_campaign_products_keyboard(product_names, selected_products)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "camp_products_clear")
async def auto_clear_products(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_products=[])
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    keyboard = get_campaign_products_keyboard(product_names, [])
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Выбор очищен")

@router.callback_query(F.data == "camp_products_done")
async def auto_products_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_products = data.get('selected_products', [])
    
    if not selected_products:
        await callback.answer("❌ Выберите хотя бы один товар!", show_alert=True)
        return
    
    await state.set_state(AutoSellStates.select_quantities)
    
    all_quantities = set()
    for product in selected_products:
        quantities = get_product_quantities(product)
        all_quantities.update(quantities)
    
    keyboard = get_campaign_quantities_keyboard(list(all_quantities), [])
    await callback.message.edit_text(
        f"📊 Выберите количество для товаров:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("camp_qty_"))
async def auto_select_quantity(callback: CallbackQuery, state: FSMContext):
    qty = callback.data.replace("camp_qty_", "")
    data = await state.get_data()
    selected_quantities = data.get('selected_quantities', [])
    
    if qty in selected_quantities:
        selected_quantities.remove(qty)
    else:
        selected_quantities.append(qty)
    
    await state.update_data(selected_quantities=selected_quantities)
    
    selected_products = data.get('selected_products', [])
    all_quantities = set()
    for product in selected_products:
        quantities = get_product_quantities(product)
        all_quantities.update(quantities)
    
    keyboard = get_campaign_quantities_keyboard(list(all_quantities), selected_quantities)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "camp_qty_clear")
async def auto_clear_quantities(callback: CallbackQuery, state: FSMContext):
    await state.update_data(selected_quantities=[])
    
    data = await state.get_data()
    selected_products = data.get('selected_products', [])
    all_quantities = set()
    for product in selected_products:
        quantities = get_product_quantities(product)
        all_quantities.update(quantities)
    
    keyboard = get_campaign_quantities_keyboard(list(all_quantities), [])
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("✅ Выбор очищен")

@router.callback_query(F.data == "camp_qty_done")
async def auto_qty_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_quantities = data.get('selected_quantities', [])
    
    if not selected_quantities:
        await callback.answer("❌ Выберите хотя бы одно количество!", show_alert=True)
        return
    
    await state.set_state(AutoSellStates.select_days)
    keyboard = get_campaign_days_keyboard()
    
    await callback.message.edit_text(
        f"📅 Выберите длительность кампании (в днях):",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("camp_days_"))
async def auto_select_days(callback: CallbackQuery, state: FSMContext):
    days = int(callback.data.replace("camp_days_", ""))
    await state.update_data(campaign_days=days)
    await state.set_state(AutoSellStates.enter_prices)
    
    data = await state.get_data()
    selected_products = data.get('selected_products', [])
    
    keyboard = get_campaign_price_keyboard(selected_products)
    await callback.message.edit_text(
        f"💰 Введите цены для товаров:\n"
        f"Нажмите на каждый товар и введите цену",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("camp_price_"))
async def auto_enter_price(callback: CallbackQuery, state: FSMContext):
    product = callback.data.replace("camp_price_", "")
    await state.update_data(current_price_product=product)
    await callback.message.edit_text(
        f"💰 Введите цену для товара {product}:\n"
        f"(только цифры)"
    )
    await callback.answer()

@router.message(AutoSellStates.enter_prices)
async def auto_process_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещен")
        return
    
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректную цену (только цифры)")
        return
    
    data = await state.get_data()
    product_prices = data.get('product_prices', {})
    current_product = data.get('current_price_product', '')
    
    if current_product:
        product_prices[current_product] = price
        await state.update_data(product_prices=product_prices)
        
        selected_products = data.get('selected_products', [])
        keyboard = get_campaign_price_keyboard(selected_products)
        
        price_status = []
        for p in selected_products:
            if p in product_prices:
                price_status.append(f"✅ {p} - {product_prices[p]}₽")
            else:
                price_status.append(f"⬜ {p} - не указана")
        
        await message.answer(
            f"💰 Цены:\n" + "\n".join(price_status),
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ Ошибка: не выбран товар")

@router.callback_query(F.data == "camp_price_done")
async def auto_price_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_prices = data.get('product_prices', {})
    selected_products = data.get('selected_products', [])
    
    missing_prices = [p for p in selected_products if p not in product_prices]
    
    if missing_prices:
        await callback.answer(
            f"❌ Не введены цены для: {', '.join(missing_prices)}",
            show_alert=True
        )
        return
    
    cities = data.get('selected_cities', [])
    quantities = data.get('selected_quantities', [])
    days = data.get('campaign_days', 3)
    name = data.get('campaign_name', 'Кампания')
    
    text = f"📋 ПОДТВЕРЖДЕНИЕ КАМПАНИИ\n\n"
    text += f"📝 Название: {name}\n"
    text += f"📍 Города: {', '.join(cities)}\n"
    text += f"📦 Товары: {', '.join(selected_products)}\n"
    text += f"📊 Количество: {', '.join(quantities)}\n"
    text += f"📅 Дней: {days}\n"
    text += f"💰 Цены:\n"
    for product, price in product_prices.items():
        text += f"  • {product}: {price}₽\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ СОЗДАТЬ КАМПАНИЮ", callback_data="camp_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="camp_cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "camp_confirm")
async def auto_confirm_campaign(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    from automation import auto_engine
    
    data = await state.get_data()
    
    campaign_data = {
        'name': data.get('campaign_name', 'Кампания'),
        'cities': data.get('selected_cities', []),
        'products': data.get('selected_products', []),
        'quantities': data.get('selected_quantities', []),
        'prices': [data.get('product_prices', {}).get(p, 0) for p in data.get('selected_products', [])],
        'days': data.get('campaign_days', 3)
    }
    
    campaign_id = await auto_engine.create_campaign_from_data(campaign_data)
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ КАМПАНИЯ СОЗДАНА!\n\n"
        f"ID: {campaign_id}\n"
        f"Название: {campaign_data['name']}\n"
        f"Городов: {len(campaign_data['cities'])}\n"
        f"Товаров: {len(campaign_data['products'])}\n"
        f"Дней: {campaign_data['days']}\n\n"
        f"Бот начал автоматическую продажу!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 К списку кампаний", callback_data="auto_campaigns")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="auto_sell")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "camp_cancel")
async def auto_cancel_campaign(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = get_auto_sell_menu()
    await callback.message.edit_text(
        "🤖 АВТОМАТИЧЕСКАЯ ПРОДАЖА\n\n"
        "Создание кампании отменено.",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "auto_campaigns")
async def auto_campaigns_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    campaigns = db.get_active_campaigns()
    keyboard = get_campaign_list_keyboard(campaigns)
    
    await callback.message.edit_text(
        "📋 Активные кампании:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("camp_info_"))
async def auto_campaign_info(callback: CallbackQuery):
    campaign_id = int(callback.data.replace("camp_info_", ""))
    campaign = db.get_campaign_by_id(campaign_id)
    
    if not campaign:
        await callback.answer("❌ Кампания не найдена", show_alert=True)
        return
    
    days_left = campaign['days'] - (datetime.now() - datetime.fromisoformat(campaign['started_at'])).days
    
    text = f"📊 ИНФОРМАЦИЯ О КАМПАНИИ\n\n"
    text += f"ID: {campaign['id']}\n"
    text += f"Название: {campaign['name']}\n"
    text += f"Статус: {'🟢 Активна' if campaign['is_active'] else '🔴 Завершена'}\n"
    text += f"Дней осталось: {max(0, days_left)}\n"
    text += f"Продано: {campaign['sold_count']} шт.\n"
    text += f"Выручка: {campaign['total_revenue']}₽\n"
    text += f"Городов: {len(campaign['cities'])}\n"
    text += f"Товаров: {len(campaign['products'])}"
    
    keyboard = get_campaign_info_keyboard(campaign_id)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("camp_stop_"))
async def auto_stop_campaign(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    from automation import auto_engine
    
    campaign_id = int(callback.data.replace("camp_stop_", ""))
    await auto_engine.end_campaign(campaign_id)
    
    await callback.answer("✅ Кампания остановлена", show_alert=True)
    
    campaigns = db.get_active_campaigns()
    keyboard = get_campaign_list_keyboard(campaigns)
    await callback.message.edit_text(
        "📋 Активные кампании:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "auto_stats")
async def auto_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    total_orders = db.get_orders_count()
    auto_orders = db.get_auto_orders(30)
    
    text = f"📊 СТАТИСТИКА АВТО-ПРОДАЖ\n\n"
    text += f"Всего заказов: {total_orders}\n"
    text += f"Авто-заказов (30д): {len(auto_orders)}\n"
    
    if auto_orders:
        total_revenue = sum(order['price'] for order in auto_orders)
        avg_price = total_revenue // len(auto_orders) if auto_orders else 0
        text += f"Выручка (30д): {total_revenue}₽\n"
        text += f"Средний чек: {avg_price}₽\n"
    
    product_stats = {}
    for order in auto_orders:
        name = order['product_name']
        product_stats[name] = product_stats.get(name, 0) + 1
    
    if product_stats:
        text += "\n🏆 Топ товаров:\n"
        for name, count in sorted(product_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
            text += f"  • {name}: {count} шт.\n"
    
    keyboard = get_auto_stats_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "auto_stop_all")
async def auto_stop_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    from automation import auto_engine
    
    campaigns = db.get_active_campaigns()
    for camp in campaigns:
        await auto_engine.end_campaign(camp['id'])
    
    await callback.answer("✅ Все кампании остановлены", show_alert=True)
    
    keyboard = get_auto_sell_menu()
    await callback.message.edit_text(
        "🤖 АВТОМАТИЧЕСКАЯ ПРОДАЖА\n\n"
        "Все кампании остановлены.",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "auto_sell_back")
async def auto_sell_back(callback: CallbackQuery, state: FSMContext):
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

@router.callback_query(F.data.startswith("city_page_"))
async def change_city_page(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.is_user_blocked(user_id):
        await callback.answer()
        return
    
    page = int(callback.data.replace("city_page_", ""))
    cities = db.get_cities()
    keyboard = get_cities_keyboard(cities, page, False)
    await callback.message.edit_text("💦 Выберите город", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_city_page_"))
async def change_admin_city_page(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    page = int(callback.data.replace("admin_city_page_", ""))
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, page)
    await callback.message.edit_text(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_admin_products")
async def back_to_admin_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    cities = db.get_cities()
    keyboard = get_admin_city_products_keyboard(cities, 0)
    await callback.message.edit_text(
        "💦 Товары\n📍 Выберите город для товара",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_city_products")
async def back_to_city_products(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    data = await state.get_data()
    city = data.get('admin_city', '')
    
    products_from_file = parse_product_file('list.txt')
    product_names = list(products_from_file.keys())
    
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