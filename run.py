import asyncio
import logging
import os
import sys
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(i.strip()) for i in ADMIN_IDS_RAW.split(",") if i.strip().isdigit()]

if not TOKEN or TOKEN == "TOKEN_SHU_YERGA_YOZILADI":
    print("XATO: BOT_TOKEN topilmadi yoki .env faylga yozilmadi!")
    sys.exit(1)

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("pdf", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def init_db():
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            volume TEXT,
            price INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            phone TEXT,
            status INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        products_list = [
            ("Paxta asali", "175 g", 23500),
            ("Paxta asali", "250 g", 31500),
            ("Paxta asali", "500 g", 62000),
            ("Paxta asali", "900 g", 96500),
            ("Grechka asali", "175 g", 26000),
            ("Grechka asali", "250 g", 35500),
            ("Grechka asali", "500 g", 70000),
            ("Boshqird asali", "175 g", 32000),
            ("Boshqird asali", "250 g", 43500),
            ("Boshqird asali", "500 g", 86500),
            ("Kungaboqar asali", "250 g", 33000),
            ("Kungaboqar asali", "500 g", 54000),
            ("Tog‘ asali", "175 g", 31500),
            ("Tog‘ asali", "250 g", 42500),
            ("Tog‘ asali", "500 g", 83000),
            ("Tog‘ asali", "700 g", 112000),
            ("Tog‘ asali", "900 g", 133500),
            ("Oltoy tog‘ asali", "175 g", 29000),
            ("Oltoy tog‘ asali", "250 g", 39500),
            ("Oltoy tog‘ asali", "500 g", 78500),
            ("Juka (Lipa) asali", "175 g", 37500),
            ("Juka (Lipa) asali", "250 g", 52000),
            ("Juka (Lipa) asali", "500 g", 103000),
        ]
        cursor.executemany("INSERT INTO products (name, volume, price) VALUES (?, ?, ?)", products_list)
    else:
        cursor.execute("SELECT COUNT(*) FROM products WHERE name = 'Oltoy tog‘ asali' AND volume = '250 g'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO products (name, volume, price) VALUES (?, ?, ?)", ("Oltoy tog‘ asali", "250 g", 39500))
        
    conn.commit()
    conn.close()

init_db()

bot = Bot(token=TOKEN)
dp = Dispatcher()

class AgentOrderState(StatesGroup):
    selecting_market = State()
    entering_new_market = State()
    selecting_honey_type = State()
    selecting_honey_volume = State()
    entering_quantity = State()
    managing_cart = State()

def get_user_status(user_id):
    if user_id in ADMIN_IDS:
        return 1
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def generate_pdf_nakladnoy(order_id, market_name, agent_name, items):
    filename = f"pdf/nakladnoy_{order_id}.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "CHASHMA - BUYURTMA NAKLADNOYI")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 75, f"Buyurtma raqami: #{order_id}")
    c.drawString(50, height - 90, f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.drawString(50, height - 105, f"Market nomi: {market_name}")
    c.drawString(50, height - 120, f"Agent: {agent_name}")
    
    c.line(50, height - 135, width - 50, height - 135)
    
    y = height - 160
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Mahsulot")
    c.drawString(250, y, "Hajmi")
    c.drawString(330, y, "Soni")
    c.drawString(400, y, "Narxi")
    c.drawString(480, y, "Summa")
    
    y -= 20
    c.setFont("Helvetica", 10)
    total_sum = 0
    
    for item in items:
        p_name = item['name']
        p_vol = item['volume']
        qty = item['quantity']
        price = item['price']
        subtotal = qty * price
        total_sum += subtotal
        
        c.drawString(50, y, p_name)
        c.drawString(250, y, p_vol)
        c.drawString(330, y, str(qty))
        c.drawString(400, y, f"{price:,}")
        c.drawString(480, y, f"{subtotal:,}")
        y -= 20
        
        if y < 100:
            c.showPage()
            y = height - 50
            
    c.line(50, y - 5, width - 50, y - 5)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y, f"Jami summa: {total_sum:,} so'm")
    
    c.save()
    return filename

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    status = get_user_status(user_id)

    if status == 1:
        await show_main_menu(message)
    elif status == 0:
        await message.answer("Sizning so'rovingiz admin tomonidan ko'rib chiqilmoqda. Iltimos, kuting ⏳")
    else:
        builder = ReplyKeyboardBuilder()
        builder.button(text="📱 Telefon raqamni ulashish", request_contact=True)
        builder.adjust(1)
        await message.answer(
            f"Assalomu alaykum, <b>{message.from_user.full_name}</b>! 🍯\n\n"
            "Botdan foydalanish uchun admin ruxsat berishi kerak, buning uchun pastdagi tugma orqali kontaktni ulashing:",
            reply_markup=builder.as_markup(resize_keyboard=True),
            parse_mode="HTML"
        )

async def show_main_menu(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Buyurtma qabul qilish", callback_data="start_agent_order")
    builder.button(text="📞 Biz bilan aloqa", callback_data="contact")
    if message.from_user.id in ADMIN_IDS:
        builder.button(text="⚙️ Admin panel", callback_data="admin_panel")
    builder.adjust(1)

    rm = types.ReplyKeyboardRemove()
    await message.answer("Asosiy menyu:", reply_markup=rm)
    await message.answer(
        f"Xush kelibsiz, <b>{message.from_user.full_name}</b>! 🍯\n"
        "Buyurtma qabul qilish uchun quyidagi tugmani bosing:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@dp.message(F.contact)
async def process_contact(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    phone = message.contact.phone_number

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, full_name, username, phone, status)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET full_name=?, username=?, phone=?, status=0
    """, (user_id, full_name, username, phone, full_name, username, phone))
    conn.commit()
    conn.close()

    await message.answer(
        "Raqamingiz adminga yuborildi! ✅\nAdmin tasdiqlagach, botdan foydalanishingiz mumkin bo'ladi.",
        reply_markup=types.ReplyKeyboardRemove()
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ruxsat berish", callback_data=f"approve_{user_id}")
    builder.button(text="❌ Rad etish", callback_data=f"reject_{user_id}")
    builder.adjust(2)

    admin_text = (
        f"🔔 <b>Yangi foydalanuvchi so'rovi!</b>\n\n"
        f"👤 Ism: {full_name}\n"
        f"tg Username: {username}\n"
        f"📞 Telefon: <code>{phone}</code>\n"
        f"🆔 ID: <code>{user_id}</code>"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[0]
    target_user_id = int(parts[1])

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    if action == "approve":
        cursor.execute("UPDATE users SET status = 1 WHERE user_id = ?", (target_user_id,))
        conn.commit()
        conn.close()

        await callback.message.edit_text(callback.message.text + "\n\n<b>STATUS: ✅ Tasdiqlandi</b>", parse_mode="HTML")
        await callback.answer("Foydalanuvchiga ruxsat berildi!")

        try:
            await bot.send_message(
                target_user_id, 
                "🎉 Tabriklaymiz! Admin sizning so'rovingizni tasdiqladi.\nBotdan foydalanishingiz mumkin. /start ni bosing:"
            )
        except Exception:
            pass
    else:
        cursor.execute("UPDATE users SET status = 2 WHERE user_id = ?", (target_user_id,))
        conn.commit()
        conn.close()

        await callback.message.edit_text(callback.message.text + "\n\n<b>STATUS: ❌ Rad etildi</b>", parse_mode="HTML")
        await callback.answer("Foydalanuvchi rad etildi.")

        try:
            await bot.send_message(target_user_id, "❌ Afsuski, admin sizning so'rovingizni rad etdi.")
        except Exception:
            pass

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_handler(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name, phone, status FROM users")
    users = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for u_id, name, phone, status in users:
        st_icon = "⏳" if status == 0 else ("✅" if status == 1 else "❌")
        builder.button(text=f"{st_icon} {name} ({phone})", callback_data=f"manage_user_{u_id}")
    builder.button(text="🔙 Ortga", callback_data="back_home")
    builder.adjust(1)

    await callback.message.edit_text(
        "⚙️ <b>Admin panel — Foydalanuvchilar boshqaruvi:</b>\nFoydalanuvchi ustiga bosib uning statusini o'zgartirishingiz mumkin:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("manage_user_"))
async def manage_specific_user(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    u_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, username, phone, status FROM users WHERE user_id = ?", (u_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    name, uname, phone, status = user
    st_text = "Kutilmoqda ⏳" if status == 0 else ("Tasdiqlangan ✅" if status == 1 else "Bloklangan ❌")

    builder = InlineKeyboardBuilder()
    if status != 1:
        builder.button(text="✅ Ruxsat berish", callback_data=f"setstatus_{u_id}_1")
    if status != 2:
        builder.button(text="❌ Bloklash / Rad etish", callback_data=f"setstatus_{u_id}_2")
    builder.button(text="🔙 Admin panelga qaytish", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"Ism: {name}\nUsername: {uname}\nTelefon: {phone}\nStatus: <b>{st_text}</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("setstatus_"))
async def set_user_status_action(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    parts = callback.data.split("_")
    u_id = int(parts[1])
    new_status = int(parts[2])

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (new_status, u_id))
    conn.commit()
    conn.close()

    await callback.answer("Status o'zgardi!")
    await admin_panel_handler(callback)

@dp.callback_query(F.data == "start_agent_order")
async def start_agent_order(callback: types.CallbackQuery, state: FSMContext):
    if get_user_status(callback.from_user.id) != 1:
        await callback.answer("Sizga admin tomonidan ruxsat berilmagan!", show_alert=True)
        return

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM markets ORDER BY name")
    markets = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for m_id, m_name in markets:
        builder.button(text=f"🏪 {m_name}", callback_data=f"market_{m_id}")
    builder.button(text="➕ Yangi market qo'shish", callback_data="new_market")
    builder.button(text="🔙 Ortga", callback_data="back_home")
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Marketni tanlang:</b>\nAgar ro‘yxatda bo‘lmasa, yangi market qo‘shishingiz mumkin:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AgentOrderState.selecting_market)
    await callback.answer()

@dp.callback_query(F.data == "new_market", AgentOrderState.selecting_market)
async def ask_new_market(callback: types.CallbackQuery, state: FSMContext):
    if get_user_status(callback.from_user.id) != 1: return
    await callback.message.edit_text("Yangi market nomini kiriting (masalan: <i>Supermarket 'Baraka'</i>):", parse_mode="HTML")
    await state.set_state(AgentOrderState.entering_new_market)
    await callback.answer()

@dp.message(AgentOrderState.entering_new_market)
async def process_new_market(message: types.Message, state: FSMContext):
    if get_user_status(message.from_user.id) != 1: return
    market_name = message.text.strip()
    if not market_name:
        await message.answer("Market nomi bo'sh bo'lishi mumkin emas. Qaytadan kiriting:")
        return

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO markets (name) VALUES (?)", (market_name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

    await state.update_data(market_name=market_name, cart=[])
    await show_honey_types(message, state)

@dp.callback_query(F.data.startswith("market_"), AgentOrderState.selecting_market)
async def select_existing_market(callback: types.CallbackQuery, state: FSMContext):
    if get_user_status(callback.from_user.id) != 1: return
    m_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM markets WHERE id = ?", (m_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await callback.answer("Market topilmadi!", show_alert=True)
        return

    market_name = row[0]
    await state.update_data(market_name=market_name, cart=[])
    
    await callback.message.delete()
    await show_honey_types_msg(callback.message, state)
    await callback.answer()

async def show_honey_types(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM products")
    types_list = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for row in types_list:
        t_name = row[0]
        builder.button(text=f"🍯 {t_name}", callback_data=f"type_{t_name}")
    
    data = await state.get_data()
    cart = data.get('cart', [])
    if cart:
        builder.button(text="🛒 Savatchani ko'rish / O'zgartirish (+/-)", callback_data="view_cart")
        builder.button(text="✅ Buyurtmani yakunlash", callback_data="finish_order")
    
    builder.button(text="🗑️ Savatchani tozalash", callback_data="clear_cart")
    builder.adjust(1)

    market_name = data.get('market_name', '')

    cart_summary = ""
    if cart:
        total = sum(i['quantity'] * i['price'] for i in cart)
        cart_summary = f"\n\n<b>🛒 Savatchadagilar:</b>\n"
        for idx, item in enumerate(cart, 1):
            cart_summary += f"{idx}. {item['name']} ({item['volume']}) x {item['quantity']} = {item['quantity']*item['price']:,} so'm\n"
        cart_summary += f"<b>Jami: {total:,} so'm</b>\n"

    await message.answer(
        f"🏪 Market: <b>{market_name}</b>{cart_summary}\n\n<b>Asal turini tanlang yoki buyurtmani yakunlang:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AgentOrderState.selecting_honey_type)

async def show_honey_types_msg(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT name FROM products")
    types_list = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for row in types_list:
        t_name = row[0]
        builder.button(text=f"🍯 {t_name}", callback_data=f"type_{t_name}")
    
    data = await state.get_data()
    cart = data.get('cart', [])
    if cart:
        builder.button(text="🛒 Savatchani ko'rish / O'zgartirish (+/-)", callback_data="view_cart")
        builder.button(text="✅ Buyurtmani yakunlash", callback_data="finish_order")
    
    builder.button(text="🗑 Savatchani tozalash", callback_data="clear_cart")
    builder.adjust(1)

    market_name = data.get('market_name', '')

    cart_summary = ""
    if cart:
        total = sum(i['quantity'] * i['price'] for i in cart)
        cart_summary = f"\n\n<b>🛒 Savatchadagilar:</b>\n"
        for idx, item in enumerate(cart, 1):
            cart_summary += f"{idx}. {item['name']} ({item['volume']}) x {item['quantity']} = {item['quantity']*item['price']:,} so'm\n"
        cart_summary += f"<b>Jami: {total:,} so'm</b>\n"

    await message.answer(
        f"🏪 Market: <b>{market_name}</b>{cart_summary}\n\n<b>Asal turini tanlang yoki buyurtmani yakunlang:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(AgentOrderState.selecting_honey_type)

@dp.callback_query(F.data == "clear_cart", AgentOrderState.selecting_honey_type)
async def clear_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await callback.message.delete()
    await show_honey_types_msg(callback.message, state)
    await callback.answer("Savatcha tozalandi.")

@dp.callback_query(F.data.startswith("type_"), AgentOrderState.selecting_honey_type)
async def select_honey_type(callback: types.CallbackQuery, state: FSMContext):
    honey_type = callback.data.replace("type_", "", 1)
    await state.update_data(selected_type=honey_type)

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, volume, price FROM products WHERE name = ?", (honey_type,))
    volumes = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for p_id, volume, price in volumes:
        builder.button(text=f"{volume} — {price:,} so'm", callback_data=f"fvol_{p_id}")
    builder.button(text="🔙 Asal turlariga qaytish", callback_data="back_to_types")
    builder.adjust(1)

    data = await state.get_data()
    cart = data.get('cart', [])
    existing_info = ""
    for item in cart:
        if item['name'] == honey_type:
            existing_info += f"• {item['volume']}: hozirda savatchada <b>{item['quantity']} ta</b> bor\n"

    msg_text = f"🍯 Tanlangan asal: <b>{honey_type}</b>\n"
    if existing_info:
        msg_text += f"\n<b>Sizning buyurtmangizda:</b>\n{existing_info}\n"
    msg_text += "<b>Hajmini (grammini) tanlang:</b>"

    await callback.message.edit_text(msg_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AgentOrderState.selecting_honey_volume)
    await callback.answer()

@dp.callback_query(F.data == "back_to_types", AgentOrderState.selecting_honey_volume)
async def back_to_types(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await show_honey_types_msg(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data.startswith("fvol_"), AgentOrderState.selecting_honey_volume)
async def select_honey_volume(callback: types.CallbackQuery, state: FSMContext):
    p_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, volume, price FROM products WHERE id = ?", (p_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    data = await state.get_data()
    cart = data.get('cart', [])
    current_qty = 0
    for item in cart:
        if item['name'] == product[0] and item['volume'] == product[1]:
            current_qty = item['quantity']
            break

    await state.update_data(current_product={"name": product[0], "volume": product[1], "price": product[2]})
    
    await callback.message.edit_text(
        f"Tanlandi: <b>{product[0]} ({product[1]})</b> — {product[2]:,} so'm\n"
        f"🛒 Hozirgi savatchadagi miqdori: <b>{current_qty} ta</b>\n\n"
        f"Iltimos, sonini kiriting:\n"
        f"• Qo'shish uchun: <code>3</code> (yoki <code>+3</code>)\n"
        f"• Ayirish uchun: <code>-2</code> (agar miqdor 0 bo'lib qolsa, o'chib ketadi)", 
        parse_mode="HTML"
    )
    await state.set_state(AgentOrderState.entering_quantity)
    await callback.answer()

@dp.message(AgentOrderState.entering_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    text = message.text.strip()
    
    is_negative = False
    if text.startswith("-"):
        is_negative = True
        num_str = text[1:]
    elif text.startswith("+"):
        num_str = text[1:]
    else:
        num_str = text

    if not num_str.isdigit():
        await message.answer("Iltimos, to'g'ri son kiriting (masalan: <code>3</code> yoki <code>-2</code>):", parse_mode="HTML")
        return

    val = int(num_str)
    if val == 0:
        await message.answer("Soni 0 bo'lishi mumkin emas. Qaytadan kiriting:")
        return

    qty_change = -val if is_negative else val

    data = await state.get_data()
    curr_prod = data.get('current_product')
    cart = data.get('cart', [])

    found = False
    for item in cart:
        if item['name'] == curr_prod['name'] and item['volume'] == curr_prod['volume']:
            item['quantity'] += qty_change
            found = True
            if item['quantity'] <= 0:
                cart.remove(item)
            break
    
    if not found:
        if qty_change > 0:
            curr_prod['quantity'] = qty_change
            cart.append(curr_prod)
        else:
            await message.answer("Bu mahsulot savatchada yo'q, shuning uchun ayirib bo'lmaydi. Son kiriting (masalan: 3):")
            return
    
    selected_type = curr_prod['name']
    await state.update_data(cart=cart, current_product=None)

    conn = sqlite3.connect("data/chashma.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, volume, price FROM products WHERE name = ?", (selected_type,))
    volumes = cursor.fetchall()
    conn.close()

    builder = InlineKeyboardBuilder()
    for p_id, volume, price in volumes:
        builder.button(text=f"{volume} — {price:,} so'm", callback_data=f"fvol_{p_id}")
    builder.button(text="✅ Yetarli (Asal turlariga qaytish)", callback_data="back_to_types_from_vol")
    builder.adjust(1)

    total = sum(item['quantity'] * item['price'] for item in cart)
    cart_text = f"<b>✅ Yangilandi! Savatcha:</b>\n"
    if cart:
        for idx, item in enumerate(cart, 1):
            cart_text += f"{idx}. {item['name']} ({item['volume']}) x {item['quantity']} = {item['quantity']*item['price']:,} so'm\n"
        cart_text += f"\n<b>Jami: {total:,} so'm</b>\n\n"
    else:
        cart_text += f"Savatcha bo'sh.\n\n"

    cart_text += f"🍯 <b>{selected_type}</b> uchun yana boshqa hajmni tanlaysizmi yoki yetarlimi?"

    await message.answer(cart_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AgentOrderState.selecting_honey_volume)

@dp.callback_query(F.data == "back_to_types_from_vol", AgentOrderState.selecting_honey_volume)
async def back_to_types_from_vol(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await show_honey_types_msg(callback.message, state)
    await callback.answer()

@dp.callback_query(F.data == "view_cart")
async def view_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get('cart', [])
    
    if not cart:
        await callback.answer("Savatcha bo'sh!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for idx, item in enumerate(cart):
        builder.button(text=f"➖ {item['name']} ({item['volume']}) x{item['quantity']}", callback_data=f"cart_minus_{idx}")
        builder.button(text=f"➕ {item['name']} ({item['volume']}) x{item['quantity']}", callback_data=f"cart_plus_{idx}")
    
    builder.button(text="🔙 Asal turlariga qaytish", callback_data="back_to_types_from_vol")
    builder.button(text="✅ Buyurtmani yakunlash", callback_data="finish_order")
    builder.adjust(2, 2)

    total = sum(i['quantity'] * i['price'] for i in cart)
    cart_text = "<b>🛒 Savatchani boshqarish (+ va -):</b>\nMiqdorni o'zgartirish uchun tugmalarni bosing:\n\n"
    for idx, item in enumerate(cart, 1):
        cart_text += f"{idx}. {item['name']} ({item['volume']}) — {item['quantity']} ta = {item['quantity']*item['price']:,} so'm\n"
    cart_text += f"\n<b>Jami: {total:,} so'm</b>"

    await callback.message.edit_text(cart_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(AgentOrderState.selecting_honey_volume)
    await callback.answer()

@dp.callback_query(F.data.startswith("cart_plus_") | F.data.startswith("cart_minus_"))
async def modify_cart_item(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    action = parts[1]
    idx = int(parts[2])

    data = await state.get_data()
    cart = data.get('cart', [])

    if idx < len(cart):
        if action == "plus":
            cart[idx]['quantity'] += 1
        elif action == "minus":
            cart[idx]['quantity'] -= 1
            if cart[idx]['quantity'] <= 0:
                cart.pop(idx)

        await state.update_data(cart=cart)

    if not cart:
        await callback.message.delete()
        await show_honey_types_msg(callback.message, state)
        await callback.answer("Savatcha bo'shatildi.")
        return

    builder = InlineKeyboardBuilder()
    for i, item in enumerate(cart):
        builder.button(text=f"➖ {item['name']} ({item['volume']}) x{item['quantity']}", callback_data=f"cart_minus_{i}")
        builder.button(text=f"➕ {item['name']} ({item['volume']}) x{item['quantity']}", callback_data=f"cart_plus_{i}")
    
    builder.button(text="🔙 Asal turlariga qaytish", callback_data="back_to_types_from_vol")
    builder.button(text="✅ Buyurtmani yakunlash", callback_data="finish_order")
    builder.adjust(2, 2)

    total = sum(i['quantity'] * i['price'] for i in cart)
    cart_text = "<b>🛒 Savatchani boshqarish (+ va -):</b>\nMiqdorni o'zgartirish uchun tugmalarni bosing:\n\n"
    for i, item in enumerate(cart, 1):
        cart_text += f"{i}. {item['name']} ({item['volume']}) — {item['quantity']} ta = {item['quantity']*item['price']:,} so'm\n"
    cart_text += f"\n<b>Jami: {total:,} so'm</b>"

    await callback.message.edit_text(cart_text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer("Miqdor o'zgardi!")

@dp.callback_query(F.data == "finish_order")
async def finish_order_handler(callback: types.CallbackQuery, state: FSMContext):
    if get_user_status(callback.from_user.id) != 1:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    data = await state.get_data()
    market_name = data.get('market_name')
    cart = data.get('cart', [])
    agent_name = callback.from_user.full_name

    if not cart:
        await callback.answer("Savatcha bo'sh! Avval asal tanlab qo'shing.", show_alert=True)
        return

    order_id = int(datetime.now().timestamp())
    pdf_path = generate_pdf_nakladnoy(order_id, market_name, agent_name, cart)

    summary = (
        f"<b>✅ Buyurtma muvaffaqiyatli rasmiylashtirildi!</b>\n\n"
        f"🏪 Market: <b>{market_name}</b>\n"
        f"👤 Agent: {agent_name}\n\n"
        f"<b>Mahsulotlar:</b>\n"
    )
    total = 0
    for idx, item in enumerate(cart, 1):
        sub = item['quantity'] * item['price']
        total += sub
        summary += f"{idx}. {item['name']} ({item['volume']}) - {item['quantity']} ta ({sub:,} so'm)\n"
    summary += f"\n<b>Jami: {total:,} so'm</b>"

    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.message.answer(summary, parse_mode="HTML")
    document_agent = types.FSInputFile(pdf_path)
    await callback.message.answer_document(document=document_agent, caption="📄 Sizning buyurtma nakladnoyingiz (PDF)")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🔔 <b>Yangi agent buyurtmasi!</b>\n\n{summary}", parse_mode="HTML")
            doc_admin = types.FSInputFile(pdf_path)
            await bot.send_document(chat_id=admin_id, document=doc_admin, caption=f"📄 Nakladnoy #{order_id}")
        except Exception:
            pass

    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "contact")
async def contact_us(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Ortga", callback_data="back_home")
    await callback.message.edit_text("📞 Bog‘lanish uchun telefon: +998 90 342 67 69\nTelegram: @Bahodir_jamolov", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "back_home")
async def back_home_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_main_menu(callback.message)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
