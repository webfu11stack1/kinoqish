


import shutil
import sqlite3
from aiogram import Bot, Dispatcher, types,executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import logging

from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup,KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.inline_keyboard import InlineKeyboardButton,InlineKeyboardMarkup
from aiogram.types import InputTextMessageContent
# from telegram import CallbackQuery, InlineQueryResultArticle

import sqlite3

conn = sqlite3.connect('kinoqish.db')
cursor = conn.cursor()

# userid jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS userid (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    status TEXT DEFAULT 'active'
);
''')

# Agar status ustuni yo‘q bo‘lsa — qo‘shish
try:
    cursor.execute("ALTER TABLE userid ADD COLUMN status TEXT DEFAULT 'active'")
except sqlite3.OperationalError:
    pass

# Kanal jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS channel (
    id INTEGER PRIMARY KEY,
    channel_id TEXT,
    channel_url TEXT
)
''')

# Bugungi ro‘yxatdan o‘tgan foydalanuvchilar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS userid_today (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id_tod INTEGER,
    registration_date TEXT
)
''')



# Adminlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY,
    admin_id INTEGER,
    admin_name TEXT
)
''')

# Filmlar jadvali
def init_db():
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            video_file_id TEXT,
            movie_code INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Saqlangan filmlar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS saved_movies (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    movie_code INTEGER
)
''')

# 🆕 Premium foydalanuvchilar jadvali
cursor.execute('''
CREATE TABLE IF NOT EXISTS premium_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    full_name TEXT,
    added_time TEXT,
    end_date TEXT
)
''')

import sqlite3

# Connect to the database
with sqlite3.connect('kinoqish.db') as conn:
    cursor = conn.cursor()

    # Check if the download_count column exists
    cursor.execute("PRAGMA table_info(movies)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'download_count' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN download_count INTEGER DEFAULT 0")
        conn.commit()
    else:
        print("Table yes")

    print("Column 'download_count' added successfully.")
conn.commit()
conn.close()

from datetime import datetime, timedelta

import sqlite3
from datetime import datetime, timedelta

def add_premium_user(user_id, full_name, days=30):
    """Foydalanuvchini premiumga qo‘shadi"""
    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()

    # Tugash vaqtini hisoblaymiz (30 kun)
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)

    cursor.execute('''CREATE TABLE IF NOT EXISTS premium_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        full_name TEXT,
        start_date TEXT,
        end_date TEXT
    )''')

    cursor.execute('''
        INSERT OR REPLACE INTO premium_users (user_id, full_name, start_date, end_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, full_name, start_date.strftime("%Y-%m-%d %H:%M"), end_date.strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    conn.close()



def is_premium(user_id):
    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()
    cursor.execute("SELECT end_date FROM premium_users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False

    end_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M")
    now = datetime.now()

    if now > end_date:
        cursor.execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return False

    conn.close()
    return True


TOKEN = "8565115606:AAHIQUz8ibmr72AaMvesdo4Jb4fvIjL78QQ"
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

async def search_data(query):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    # Qidiruvni bajarish
    if query:
        cursor.execute(
            '''SELECT name, description, video_file_id, movie_code, download_count
               FROM movies 
               WHERE LOWER(name) LIKE ? OR movie_code LIKE ?''', 
            ('%' + query.lower() + '%', '%' + query + '%')
        )
    else:
        cursor.execute('SELECT name, description, video_file_id, movie_code, download_count FROM movies')

    rows = cursor.fetchall()
    conn.close()

    # Qidiruv natijalarini qayta ishlash
    results = []
    for row in rows:
        name, description, file_id, movie_code,download_count = row

        if file_id:
            results.append({
                "name": name,
                "description": description,
                "file_id": file_id,
                "movie_code": movie_code,
                "download_count":download_count
            })
        else:
            logging.warning(f"Bo'sh file_id topildi: {row}")

    if not results:
        logging.info("Hech qanday natija topilmadi!")

    return results



# Add movie to database
def add_movie_to_db(name, description, video_file_id, movie_code, download_count=0):
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO movies (name, description, video_file_id, movie_code, download_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, video_file_id, movie_code, download_count))
        conn.commit()


# Fetch movies from database
def fetch_movies(query=None):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    if query:
        cursor.execute("SELECT name, description, video_file_id, movie_code,download_count FROM movies WHERE name OR movie_code LIKE ?", (f"%{query}%",))
    else:
        cursor.execute("SELECT name, description, video_file_id, movie_code,download_count FROM movies")

    rows = cursor.fetchall()
    conn.close()
    return rows


@dp.message_handler(commands=["help"], state="*")
async def panel(message: types.Message, state: FSMContext):
    await message.answer("<b>Botni ishga tushirish - /start\nAdmin bilan bog'lanish - @python_chi</b>",parse_mode="html")
    await state.finish()

#panel



from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup
import sqlite3
from datetime import datetime, timedelta

# --- ADMIN PANEL ---
@dp.message_handler(commands=["panel"], state="*")
async def panel(message: types.Message, state: FSMContext):
    mes_id = message.from_user.id
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admins")
    admin_user_ids = [admin[0] for admin in cursor.fetchall()]
    conn.close()

    if mes_id in admin_user_ids or mes_id == 1996936737:
        panel = ReplyKeyboardMarkup(
            keyboard=[
                ["📊Statistika", "⚪️Xabarlar bo'limi"],
                ["📑Users", "📑Baza"],
                ["🎥Kino bo'limi"],
                ["👤Admin bo'limi", "📢Kanal bo'limi"],
                ["💎Premium boshqaruvi"]
            ],
            resize_keyboard=True
        )
        await message.answer("✅ Panel bo‘limi!", reply_markup=panel)
        await state.set_state("panel")
    else:
        await message.answer("⛔ Siz admin emassiz!")

# --- PREMIUM BOSHQARUV ---
@dp.message_handler(text="💎Premium boshqaruvi", state="*")
async def premium_menu(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            ["➕ID orqali premium qo‘shish", "📋 Premiumlar ro‘yxati"],
            ["🗑 ID orqali premiumni o‘chirish"],
            ["⬅️ Orqaga"]
        ],
        resize_keyboard=True
    )
    await message.answer("💎 Premium foydalanuvchilarni boshqarish menyusi:", reply_markup=markup)
    await state.set_state("premium_menu")


# --- PREMIUM QO‘SHISH (BOSHLASH) ---
@dp.message_handler(text ="➕ID orqali premium qo‘shish", state="*")
async def ask_user_id(message: types.Message, state: FSMContext):
    await message.answer("👤 Premiumga qo‘shmoqchi bo‘lgan foydalanuvchining ID raqamini kiriting:")
    await state.set_state("add_premium_id")

# --- PREMIUM QO‘SHISH (ISHGA TUSHURISH) ---
@dp.message_handler(state="add_premium_id")
async def add_premium_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Noto‘g‘ri ID! Raqam kiriting.")
        return

    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    # Jadval mavjudligini tekshirish / yaratish
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            full_name TEXT,
            added_time TEXT,
            end_date TEXT
        )
    ''')

    # Foydalanuvchi ma’lumotlarini olish (agar botda saqlanmagan bo‘lsa)
    try:
        user = await bot.get_chat(user_id)
        full_name = user.full_name
    except Exception:
        full_name = "Noma’lum foydalanuvchi"

    added_time = datetime.now()
    end_date = added_time + timedelta(days=30)

    cursor.execute('''
        INSERT OR REPLACE INTO premium_users (user_id, full_name, added_time, end_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, full_name, added_time.strftime("%Y-%m-%d %H:%M"), end_date.strftime("%Y-%m-%d %H:%M")))

    conn.commit()
    conn.close()

    await message.answer(
        f"✅ <b>{full_name}</b> (ID: <code>{user_id}</code>) premiumga qo‘shildi!\n"
        f"📅 Tugash muddati: <b>{end_date.strftime('%Y-%m-%d')}</b>",
        parse_mode="HTML"
    )
    await state.set_state("premium_menu")

# --- PREMIUM OCHIRISH (TUGATISH) ---

@dp.message_handler(text="🗑 ID orqali premiumni o‘chirish", state="premium_menu")
async def ask_premium_remove_id(message: types.Message, state: FSMContext):
    await message.answer("🗑 Premiumdan o‘chirmoqchi bo‘lgan foydalanuvchi ID raqamini yuboring:")
    await state.set_state("remove_premium_user")
@dp.message_handler(state="remove_premium_user")
async def remove_premium_user(message: types.Message, state: FSMContext):
    ADMIN_ID = 1996936737  # 🔹 o‘zingizning Telegram ID'ingizni yozing

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu amalni bajarish huquqi yo‘q.")
        return

    try:
        user_id = int(message.text)

        with sqlite3.connect("kinoqish.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM premium_users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()

            if user:
                cursor.execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
                conn.commit()
                await message.answer(
                    f"✅ Foydalanuvchi (<code>{user_id}</code>) premium ro‘yxatdan o‘chirildi.",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Bu foydalanuvchi premium ro‘yxatda topilmadi.")

    except ValueError:
        await message.answer("⚠️ ID raqamini to‘g‘ri formatda kiriting (faqat raqam).")
    except Exception as e:
        await message.answer(f"⚠️ Xatolik yuz berdi: {e}")

    await state.set_state("premium_menu")

import sqlite3
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- PREMIUM USERLARNI OLISH FUNKSIYASI ---
def get_premium_users(page: int, limit: int = 10):
    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()

    # offset hisoblash
    offset = page * limit

    # limit va offset validligini tekshirish
    if page < 0:
        page = 0
        offset = 0

    cursor.execute(
        "SELECT user_id, full_name, end_date FROM premium_users ORDER BY end_date DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    users = cursor.fetchall()

    # Sahifalar sonini hisoblash
    cursor.execute("SELECT COUNT(*) FROM premium_users")
    total_users = cursor.fetchone()[0] or 0
    total_pages = (total_users + limit - 1) // limit if total_users > 0 else 1

    conn.close()
    return users, total_pages, total_users


# --- SAHIFA O‘ZGARTIRISH TUGMALARI ---
def generate_nav_markup(page: int, total_pages: int):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []

    # prev tugma
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"premium_prev_{page-1}"))
    # next tugma
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("➡️ Keyingi", callback_data=f"premium_next_{page+1}"))

    # Hozirgi sahifa ko'rsatish (faqat info sifatida)
    buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="premium_page_info"))

    markup.add(*buttons)
    return markup


# --- PREMIUMLARNI KO‘RSATISH HANDLER ---
@dp.message_handler(lambda msg: msg.text == "📋 Premiumlar ro‘yxati", state="premium_menu")
async def show_premium_users(message: types.Message, state: FSMContext):
    page = 0
    limit = 10
    users, total_pages, total_users = get_premium_users(page, limit=limit)

    if not users:
        await message.answer("❌ Hozircha premium foydalanuvchilar yo‘q.")
        return

    text = "<b>💎 Premium foydalanuvchilar ro‘yxati:</b>\n\n"
    start_index = page * limit + 1
    for i, (user_id, full_name, end_date) in enumerate(users, start=start_index):
        # full_name bo'lmasa fallback
        name = full_name if full_name else f"User {user_id}"
        text += f"{i}. <a href='tg://user?id={user_id}'>{name}</a> — {end_date}\n"

    markup = generate_nav_markup(page, total_pages)
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


# --- SAHIFA TUGMALARINI QAYTA ISHLASH ---
@dp.callback_query_handler(lambda c: c.data and ("premium_prev_" in c.data or "premium_next_" in c.data))
async def change_page(call: types.CallbackQuery):
    await call.answer()  # spinnerni o'chirish

    try:
        parts = call.data.split("_")
        page = int(parts[-1])
    except:
        await call.message.answer("⚠️ Callback data noto‘g‘ri.")
        return

    limit = 10
    users, total_pages, total_users = get_premium_users(page, limit=limit)

    # Sahifa raqami chegarasini tekshirish
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    text = "<b>💎 Premium foydalanuvchilar ro‘yxati:</b>\n\n"
    start_index = page * limit + 1
    for i, (user_id, full_name, end_date) in enumerate(users, start=start_index):
        name = full_name if full_name else f"User {user_id}"
        text += f"{i}. <a href='tg://user?id={user_id}'>{name}</a> — {end_date}\n"

    markup = generate_nav_markup(page, total_pages)

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except:
        # edit_text ishlamasa reply bilan jo'natamiz
        await call.message.reply(text, parse_mode="HTML", reply_markup=markup)


# --- ORQAGA QAYTISH ---
@dp.message_handler(lambda msg: msg.text == "⬅️ Orqaga", state="premium_menu")
async def back_to_panel(message: types.Message, state: FSMContext):
    await panel(message, state)


@dp.message_handler(text="🎥Kino bo'limi",state="*")
async def kinobol(message:types.Message,state:FSMContext):
    kb=ReplyKeyboardMarkup(
        keyboard=[
            ["📽Kino qo'shish","⛔️Kino o'chirish"],
            ["🗄Bosh panel"]
        ],resize_keyboard=True
    )
    await message.answer('kino bolimidasiz!',reply_markup=kb)
    await state.finish()
    await state.set_state("kbbol")


@dp.message_handler(text="📽Kino qo'shish",state="*")
async def start_adding_movie(message: types.Message, state: FSMContext):
    cancel_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_add")]]
    )
    await message.answer("Kino nomini kiriting:", reply_markup=cancel_button)
    await state.set_state("add_movie_name")



@dp.message_handler(state="add_movie_name", content_types=types.ContentTypes.TEXT)
async def get_movie_name(message: Message, state: FSMContext):
    movie_name = message.text.strip()
    await state.update_data(name=movie_name)
    await message.answer("Kino ta'rifini kiriting:")
    await state.set_state("add_movie_description")

@dp.message_handler(state="add_movie_description", content_types=types.ContentTypes.TEXT)
async def get_movie_description(message: Message, state: FSMContext):
    movie_description = message.text.strip()
    await state.update_data(description=movie_description)
    await message.answer("Kino uchun kodini")
    await state.set_state("add_movie_code")

@dp.message_handler(state="add_movie_code", content_types=types.ContentTypes.TEXT)
async def get_movie_thumbnail(message: Message, state: FSMContext):
    movie_code = message.text.strip()
    await state.update_data(movie_code=movie_code)
    await message.answer("Kino uchun videoni yuboring:")
    await state.set_state("add_movie_video")

@dp.message_handler(state="add_movie_video", content_types=types.ContentTypes.VIDEO)
async def get_movie_video(message: Message, state: FSMContext):
    video_id = message.video.file_id
    data = await state.get_data()

    # Add movie to database, with default download_count of 0
    add_movie_to_db(
        name=data['name'],
        description=data['description'],
        video_file_id=video_id,
        movie_code=data['movie_code'],
        download_count=0  # Explicitly passing download_count as 0
    )
    await message.answer("Kino muvaffaqiyatli qo'shildi! ✅")
    await state.finish()




from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
import hashlib


@dp.inline_handler()
async def inline_query_handler(query: types.InlineQuery):
    query_text = query.query.strip()  # Foydalanuvchi kiritgan qidiruv matni
    offset = int(query.offset) if query.offset else 0  # Sahifa raqami
    results = await search_data(query_text)  # Qidiruv funksiyasidan natijalar

    inline_results = []
    for result in results[offset:offset + 50]:  # Faqat 50 ta natijani qaytarish
        if result["file_id"]:  # Faqat fayl ID mavjud bo'lsa
            # Unikal ID yaratish (hashlib orqali)
            unique_id = hashlib.md5(f"{result['movie_code']}{result['name']}".encode()).hexdigest()

            # InlineQueryResultArticle obyekti yaratish
            inline_results.append(
                InlineQueryResultArticle(
                    id=unique_id,
                    title=result["name"],
                    description=result["description"],
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"🎬 <b>{result['name']}</b>\n\n"
                            f"{result['description']}\n\n"
                            f"Kodni kiriting: <code>{result['movie_code']}</code>"
                        ),
                        parse_mode="HTML",
                    ),
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton(
                            "📽 Kinoni ko'rish",
                            url=f"https://t.me/kinoqishbot?start={result['movie_code']}"
                        )
                    )
                )
            )

    # Agar natijalar bo'lmasa, default javob qo'shing
    if not inline_results:
        inline_results.append(
            InlineQueryResultArticle(
                id="0",
                title="Natija topilmadi",
                input_message_content=InputTextMessageContent(
                    "Hech qanday mos keluvchi natija topilmadi. 🔍"
                )
            )
        )

    # Keyingi sahifani ko'rsatish uchun offset ni yangilash
    next_offset = str(offset + 50) if offset + 50 < len(results) else None

    # Inline queryga javob berish
    await bot.answer_inline_query(
        query.id,
        results=inline_results,
        cache_time=1,  # Tezkor javoblar uchun cache vaqtini minimal qilish
        is_personal=True,
        next_offset=next_offset  # Keyingi sahifani ko'rsatish
    )


@dp.message_handler(text="⛔️Kino o'chirish", state="*")
async def dekkino(message: types.Message, state: FSMContext):
    await message.answer("Kino o'chirish uchun kodini yuboring!")
    await state.set_state("dkino")


@dp.message_handler(state="dkino")
async def dkin(message: types.Message, state: FSMContext):
    dk = message.text
    dkk = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Yes", callback_data="yes"),
             InlineKeyboardButton(text="No", callback_data="no")]
        ], row_width=2
    )
    await state.update_data(dk=dk)  # Store dk in the FSMContext
    await message.answer(f"{dk} kodli kino o'chirilsinmi!", reply_markup=dkk)
    await state.set_state("kodo")


@dp.callback_query_handler(lambda d: d.data == "yes", state="kodo")
async def yesdel(calmes: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    dk = data.get("dk")  # Retrieve dk (movie_code) from the state
    
    if dk and dk.isdigit():
        conn = sqlite3.connect("kinoqish.db")
        cursor = conn.cursor()

        # Delete the movie record from the 'movies' table using the movie_code (dk)
        cursor.execute("DELETE FROM movies WHERE movie_code = ?", (dk,))
        conn.commit()
        conn.close()

        # Use calmes.answer() to show an alert
        await calmes.answer(f"{dk} kodli kino o'chirildi!✅", show_alert=True)
    else:
        await calmes.answer("Raqam kiriting!", show_alert=True)

    await state.finish()




@dp.callback_query_handler(lambda d: d.data == "no", state="*")
async def nodel(calmes: types.CallbackQuery, state: FSMContext):
    await calmes.message.answer("⛔️ O'chirish bekor qilindi.")
    await state.finish()



    
@dp.callback_query_handler(lambda d:d.data=="end1",state="next1")
async def end(cal:types.CallbackQuery,state:FSMContext):
    await state.finish()
    await panel(cal.message,state)

@dp.message_handler(text="⚪️Xabarlar bo'limi",state="*")
async def xabarbolim(message:types.Message,state:FSMContext):
    xabarlar = ReplyKeyboardMarkup(
        keyboard=[
            ["⚪️Inline Xabar","🔗Forward xabar"],
            ["👤Userga xabar"],
            ["🖥Code xabar","🗄Bosh panel"]
        ],
        resize_keyboard=True
    )
    await message.answer('Xabarlar bolimidasiz!',reply_markup=xabarlar)
    await state.finish()
    await state.set_state("xabarbolim")

#Code xabar
@dp.message_handler(text="🖥Code xabar",state="*")
async def codemes(cmes:types.Message,state:FSMContext):
    await cmes.answer("Xabaringizi qoldiring!")
    await state.finish()
    await state.set_state("cmes")

@dp.message_handler(state="cmes")
async def ccmes(cmess:types.Message,state:FSMContext):
    cmessage = cmess.text
    yetkazilganlar = 0
    yetkazilmaganlar = 0

    cursor.execute("SELECT DISTINCT user_id FROM userid")
    user_ids = cursor.fetchall()

    for user_id in user_ids:
        try:
            
                await bot.send_message(user_id[0], text=f' ```\n {cmessage} \n```  ',parse_mode="MARKDOWN")
                yetkazilganlar += 1
           
        except Exception as e:
            print(f"Error: {e}")
            yetkazilmaganlar += 1

    await cmess.answer(
        f"<b>Xabar foydalanuvchilarga muvaffaqiyatli yuborildi!</b>✅\n\n"
        f"🚀Yetkazildi : <b>{yetkazilganlar}</b> ta\n"
        f"🛑Yetkazilmadi : <b>{yetkazilmaganlar}</b> ta",
        parse_mode="HTML"
    )
    await state.finish()

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# FSM state for sending a message to a specific user
class AdminStates(StatesGroup):
    waiting_for_user_id = State()  # Admin waiting for the user_id input
    waiting_for_message = State()  # Admin waiting for the message to send

# Admin triggers the action to send a message
@dp.message_handler(text="👤Userga xabar", state="*")
async def handle_send_message_to_user(call: types.Message):
    # Ask admin to input the user_id
    await call.answer("Iltimos, xabar yubormoqchi bo'lgan foydalanuvchining user_id sini kiriting:")
    
    # Set FSM state to waiting for user_id
    await AdminStates.waiting_for_user_id.set()

# Admin types the user_id
@dp.message_handler(state=AdminStates.waiting_for_user_id)
async def receive_user_id(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    
    # Store the user_id in FSM context
    await state.update_data(user_id=user_id)

    # Ask admin to type the message to send
    await message.answer(f"Foydalanuvchiga yuboriladigan xabarni yozing:")
    
    # Set FSM state to waiting for the message
    await AdminStates.waiting_for_message.set()



@dp.message_handler(state=AdminStates.waiting_for_message)
async def send_message_to_user(message: types.Message, state: FSMContext):
    # Get user_id and message content from FSM context
    user_data = await state.get_data()
    user_id = user_data.get("user_id")
    admin_message = message.text.strip()

    # Try sending the message to the specified user_id
    try:
        await bot.send_message(user_id, f"👤Admindan xabar:\n {admin_message} ")
        await message.answer("Xabar yuborildi.")
    except Exception as e:
        print(f"Error: {e}")
        await message.answer("Xabar yuborishda xatolik yuz berdi.")

    # Reset FSM state
    await state.finish()




import asyncio
import sqlite3
from aiogram import types
from aiogram.utils.exceptions import (
    BotBlocked, ChatNotFound, MessageToForwardNotFound, RetryAfter
)
from aiogram.dispatcher import FSMContext

@dp.message_handler(text="🔗Forward xabar", state="*")
async def forwardmes(message: types.Message, state: FSMContext):
    await message.answer("📨 Xabarni raqamini yoki linkini yuboring (masalan, 123).")
    await state.set_state("fmes")

@dp.message_handler(state="fmes")
async def fmes(message: types.Message, state: FSMContext):
    try:
        msg_id = int(message.text)
    except ValueError:
        return await message.answer("❌ Iltimos, faqat raqam kiriting (masalan, 123).")

    # 💬 Jarayon boshlandi — foydalanuvchiga xabar beramiz
    loading_msg = await message.answer("⏳ Xabar yuborilmoqda, biroz kuting...")

    # 🔹 Foydalanuvchilarni olish
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute(
    "SELECT DISTINCT user_id FROM userid WHERE status='active' AND user_id > 0"
)

    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    yetkazilgan, yetkazilmagan, blok_qilgan = 0, 0, 0

    async def forward_to_user(user_id):
        nonlocal yetkazilgan, yetkazilmagan, blok_qilgan
        try:
            await bot.forward_message(
                chat_id=user_id,
                from_chat_id=-1001736313573,  # 🎯 Kanal ID (bot admin bo‘lishi shart)
                message_id=msg_id
            )
            yetkazilgan += 1
        except BotBlocked:
            blok_qilgan += 1
        except ChatNotFound:
            yetkazilmagan += 1
        except MessageToForwardNotFound:
            pass
        except RetryAfter as e:
            await asyncio.sleep(e.timeout)
            return await forward_to_user(user_id)
        except Exception as e:
            print(f"⚠️ {user_id} da xato: {e}")
            yetkazilmagan += 1
        await asyncio.sleep(0.15)  # 🕐 Antiflood

    # 🔹 Guruhlab yuborish
    batch_size = 50
    for i in range(0, len(user_ids), batch_size):
        batch = user_ids[i:i + batch_size]
        await asyncio.gather(*(forward_to_user(uid) for uid in batch))

    # 🔹 Yakuniy natija — "yuborilmoqda..." xabarini yangilaymiz
    await loading_msg.edit_text(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"📊 <b>Natija:</b>\n"
        f"🚀 Yetkazilganlar: <b>{yetkazilgan}</b>\n"
        f"🛑 Yetkazilmaganlar: <b>{yetkazilmagan}</b>\n"
        f"❌ Blok qilganlar: <b>{blok_qilgan}</b>",
        parse_mode="HTML"
    )

    await state.finish()




    

@dp.message_handler(text="👤Admin bo'limi",state="*")
async def adminsb(message:types.Message,state:FSMContext):
    adminsbolim = ReplyKeyboardMarkup(
        keyboard=[
            ["👤Adminlar"],
            ["➕👤Admin qo'shish","⛔️👤Admin o'chirish"],
             ["🗄Bosh panel"]
        ],
        resize_keyboard=True
    ) 
    await message.answer("<b>Siz admin bo'limidasiz!</b>",reply_markup=adminsbolim,parse_mode="HTML")
    await state.finish()
    await state.set_state("admnbolim")


@dp.message_handler(text="➕👤Admin qo'shish", state="*")
async def admin_add(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    await message.answer("Admin qo'shish uchun idsini yuboring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("ad_add")

@dp.message_handler(state="ad_add")
async def admin_id(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    global admin_idd
    admin_idd = int(message.text)
    await message.answer("Ismini yuboring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("ad_ism")

@dp.message_handler(state="ad_ism")
async def admin_ism(message: types.Message, state: FSMContext):
    global admin_namee
    admin_namee = message.text
    ad_qoshish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Qo'shish", callback_data="qosh"),
             InlineKeyboardButton(text="Rad qilish", callback_data="radqil")]
        ], row_width=2
    )
    await message.answer(f"<b>Id:</b> {admin_idd} \n<b>Ism:</b> {admin_namee} ", reply_markup=ad_qoshish,
                         parse_mode="HTML")
    await state.finish()
    await state.set_state("q")

@dp.callback_query_handler(lambda q: q.data == "qosh", state="*")
async def qoshish(query: types.CallbackQuery, state: FSMContext):
   

    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()


    cursor.execute("INSERT INTO admins (admin_id, admin_name) VALUES (?, ?)", (admin_idd, admin_namee))

    conn.commit()

    await query.message.reply(
        f"<b>Yangi admin qo'shildi!</b>\n\n<b>ID</b>: {admin_idd}\n<b>Ism</b>: {admin_namee}",
        parse_mode="HTML"
    )

    await state.finish()

    conn.close()


#Admin o'chirish

@dp.message_handler(text="⛔️👤Admin o'chirish", state="*")
async def admin_add11(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    await message.answer("Admin O'chirish uchun idsini yuboring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("ad_addd")

@dp.message_handler(state="ad_addd")
async def admin_id1d(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    global admin_idd1
    admin_idd1 = int(message.text)
    await message.answer("Ismini yuboring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("ad_ismm")

@dp.message_handler(state="ad_ismm")
async def admin_ismm(message: types.Message, state: FSMContext):
    global admin_namee1
    admin_namee1 = message.text
    ad_qoshish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="O'chirish", callback_data="ochir"),
             InlineKeyboardButton(text="Rad qilish", callback_data="radqil")]
        ], row_width=2
    )
    await message.answer(f"<b>Id:</b> {admin_idd1} \n<b>Ism:</b> {admin_namee1} ", reply_markup=ad_qoshish,
                         parse_mode="HTML")
    await state.finish()
    await state.set_state("qq")

@dp.callback_query_handler(lambda q: q.data == "ochir", state="*")
async def ocir(query: types.CallbackQuery, state: FSMContext):
   

    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()


    cursor.execute("DELETE FROM admins WHERE admin_id=? AND admin_name=?", (admin_idd1,admin_namee1))
    conn.commit()

    await query.message.reply(
        f"<b>Admin o'chirildi!</b>\n\n<b>ID</b> : {admin_idd1}\n<b>Ism</b> : {admin_namee1}",
        parse_mode="HTML"
    )

    await state.finish()

    conn.close()


#Adminlar
@dp.message_handler(text="👤Adminlar", state="*")
async def admins_list(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, admin_id INTEGER , admin_name TEXT)''')

    cursor.execute('SELECT  admin_id, admin_name FROM admins')
    admins_data = cursor.fetchall()
    response = "Adminlar \n"

    if not admins_data:
        await message.reply("Adminlar ro'yxati bo'sh.")
        await state.finish()
    else:
        for admin_data in admins_data:
            admin_id, admin_name = admin_data[0], admin_data[1]
            response += f"ID: {admin_id} \nIsm: {admin_name} \nProfil: tg://user?id={admin_id}\n"

        await message.reply(response, parse_mode="Markdown")


        await state.finish()

    conn.close()



@dp.callback_query_handler(lambda s:s.data=="radqil",state="*")
async def rad(query:types.CallbackQuery,state:FSMContext):
    await query.message.delete()
    await state.finish()
    

from datetime import datetime as dt, timedelta

@dp.message_handler(text="📊Statistika", state="*")
async def statistika(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    # Umumiy foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM userid")
    total_users = cursor.fetchone()[0]

    # Faol
    cursor.execute("SELECT COUNT(*) FROM userid WHERE status='active'")
    active_users = cursor.fetchone()[0]

    # Nofaol
    cursor.execute("SELECT COUNT(*) FROM userid WHERE status='inactive'")
    inactive_users = cursor.fetchone()[0]

    # Sanalar
    today = dt.now().date()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)

    # String formatga o‘giramiz
    today_str = today.strftime("%Y-%m-%d")
    week_str = week_ago.strftime("%Y-%m-%d")
    month_str = month_start.strftime("%Y-%m-%d")

    # Bugun qo‘shilganlar
    cursor.execute("""
        SELECT COUNT(*) FROM userid_today
        WHERE registration_date = ?
    """, (today_str,))
    today_users = cursor.fetchone()[0]

    # 7 kunda qo‘shilganlar
    cursor.execute("""
        SELECT COUNT(*) FROM userid_today
        WHERE registration_date >= ?
    """, (week_str,))
    week_users = cursor.fetchone()[0]

    # Oylik qo‘shilganlar
    cursor.execute("""
        SELECT COUNT(*) FROM userid_today
        WHERE registration_date >= ?
    """, (month_str,))
    month_users = cursor.fetchone()[0]

    conn.close()

    now = dt.now().strftime("%Y-%m-%d %H:%M")

    await message.reply(
        f"📊 <b>STATISTIKA</b>\n\n"
        f"⏰ Vaqt: <b>{now}</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{total_users}</b>\n"
        f"🟢 Faol: <b>{active_users}</b>\n"
        f"🔴 Nofaol: <b>{inactive_users}</b>\n\n"
        f"📅 Bugun qo‘shilgan: <b>{today_users}</b>\n"
        f"🗓 7 kunda qo‘shilgan: <b>{week_users}</b>\n"
        f"📆 Oylik qo‘shilgan: <b>{month_users}</b>\n",
        parse_mode="HTML"
    )

    await state.finish()





@dp.message_handler(text="📢Kanal bo'limi",state="*")
async def kanalb(message:types.Message,state:FSMContext):
    kanalsbolim = ReplyKeyboardMarkup(
        keyboard=[
            ["📢Kanallar","➕Zayafka tugma"],
            ["❌Zayafka o'chirish"],
            ["➕Kanal qo'shish","⛔️Kanal o'chirish"],
            ["🗄Bosh panel"]
        ],
        resize_keyboard=True
    ) 
    await message.answer("<b>Siz 📢Kanal bo'limidasiz!</b>",reply_markup=kanalsbolim,parse_mode="HTML")
    await state.finish()
    await state.set_state("kanalbolim")

#kanal qoshish 
    
@dp.message_handler(text="➕Kanal qo'shish",state="*")
async def kanal_add(message:types.Message,state:FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    await message.answer("Kanal idsini yuboring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("kanal_id")

@dp.message_handler(state="kanal_id")
async def kanal_id(message:types.Message,state:FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )
    global kanal_idd;
    kanal_idd = (message.text)
    if kanal_idd.startswith('-100'):
        await message.answer("Kanal url yuboring !",reply_markup=tugatish)
        await state.finish()
        await state.set_state("kanal_url")
    else:
        await message.answer("Idda xatolik")    
        
        
@dp.message_handler(state="kanal_url")
async def kanal_url(message:types.Message,state:FSMContext):
    global kanal_urll;
    kanal_urll = message.text
    if  kanal_urll.startswith("https:"):
        conn = sqlite3.connect('kinoqish.db')
        cursor = conn.cursor()
    
        cursor.execute("INSERT INTO channel (channel_id, channel_url) VALUES (?, ?)", (kanal_idd, kanal_urll))

        conn.commit()
        await message.answer("Kanal qo'shildi")
        await state.finish()
    else:
        await message.answer("Kanal urlda xatolik!")


@dp.message_handler(text="🗄Bosh panel",state="*")
async def boshpanel(message:types.Message,state:FSMContext):
    await panel(message,state)
    await state.finish()

#Kanallar



@dp.message_handler(text="📢Kanallar",state="*")
async def kanallar(message:types.Message,state:FSMContext):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    cursor.execute("SELECT channel_url FROM channel")
    channels = cursor.fetchone()
    respons = "Bazadagi ulangan kanallar \n"
    try:

        for chan in channels:
            chan = channels[0]
            
            respons += f"Kanal : @{chan[13:]} \n"

        await message.answer(respons)
        await state.finish()
    except:
        await message.answer("Kanal mavjud emas!")
        await state.finish()
        
@dp.callback_query_handler(lambda c: c.data == "cancel_add",state="*")
async def cancel_addition(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Amal bekor qilindi.")
    await state.finish()

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import sqlite3

# Holatlar
class DeleteChannelState(StatesGroup):
    choosing = State()
    confirm = State()


# 1. Kanal o‘chirish tugmasi bosilganda
@dp.message_handler(text="⛔️Kanal o'chirish", state="*")
async def show_channel_list(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_url FROM channel")
    channels = cursor.fetchall()
    conn.close()

    if not channels:
        await message.answer("❌ Bazada hozircha hech qanday kanal yo‘q.")
        return

    kanal_text = "🗑 O‘chirmoqchi bo‘lgan kanal raqamini yuboring:\n\n"
    kanal_dict = {}

    for index, (chan_id, chan_url) in enumerate(channels, start=1):
        kanal_text += f"{index}) {chan_url}\n"
        kanal_dict[str(index)] = (chan_id, chan_url)

    await state.update_data(kanal_dict=kanal_dict)
    await message.answer(kanal_text)
    await state.set_state(DeleteChannelState.choosing)


# 2. Foydalanuvchi raqam yuboradi
@dp.message_handler(state=DeleteChannelState.choosing, content_types=types.ContentTypes.TEXT)
async def delete_selected_channel(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    kanal_dict = user_data.get("kanal_dict", {})

    choice = message.text.strip()

    if choice not in kanal_dict:
        await message.answer("❌ Noto‘g‘ri raqam. Iltimos, ro‘yxatdagi raqamdan birini yuboring.")
        return

    kanal_id, kanal_url = kanal_dict[choice]

    # Bazadan o‘chirish
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channel WHERE channel_id=? AND channel_url=?", (kanal_id, kanal_url))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Kanal o‘chirildi:\n{kanal_url}")
    await state.finish()
        
@dp.message_handler(text="⚪️Inline Xabar",state="*")
async def inline_xabar(message:types.Message,state:FSMContext):
    tugatish = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Tugatish",callback_data="tugat")]
        ],row_width=2
    )

    await message.answer("Xabaringiz qoldiring!",reply_markup=tugatish)
    await state.finish()
    await state.set_state("send_message")




# --- ODDIY MATNLI XABAR BOSHLANISHI ---
@dp.message_handler(state="send_message", content_types=types.ContentType.TEXT)
async def send_message_text(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(text_message=message.text)
    await message.answer("Inline tugma uchun link yuboring!", reply_markup=tugatish)
    await state.set_state("link")


@dp.message_handler(state="link")
async def link_state(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(link_url=message.text)
    await message.answer("Inline tugma uchun nom bering!", reply_markup=tugatish)
    await state.set_state("inline_nom")


@dp.message_handler(state="inline_nom")
async def inline_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text_message = data.get("text_message")
    link_url = data.get("link_url")
    button_name = message.text

    inline_preview = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{button_name}", url=f"{link_url}")],
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="send"),
            InlineKeyboardButton(text="❌ Rad qilish", callback_data="nosend")
        ]
    ])

    await state.update_data(button_name=button_name)

    await message.answer(
        f"{text_message}\n\nUshbu xabarni yuborasizmi?",
        reply_markup=inline_preview
    )
    await state.set_state("yuborish")


@dp.callback_query_handler(lambda d: d.data == "send", state="yuborish")
async def send_inline(query: types.CallbackQuery, state: FSMContext):
    await query.message.answer("📤 Xabar yuborilmoqda, biroz kuting...")

    data = await state.get_data()
    text_message = data.get("text_message")
    link_url = data.get("link_url")
    button_name = data.get("button_name")

    inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{button_name}", url=f"{link_url}")]
    ])

    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()
    cursor.execute(
    "SELECT DISTINCT user_id FROM userid WHERE status='active' AND user_id > 0"
)

    user_ids = cursor.fetchall()
    conn.close()

    yetkazilganlar = 0
    yetkazilmaganlar = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id[0], text_message, reply_markup=inline)
            yetkazilganlar += 1
        except Exception as e:
            logging.error(f"Error sending message to user {user_id[0]}: {e}")
            yetkazilmaganlar += 1

    await query.message.answer(
        f"<b>Xabar foydalanuvchilarga yuborildi!</b> ✅\n\n"
        f"🚀 Yetkazildi: <b>{yetkazilganlar}</b> ta\n"
        f"🛑 Yetkazilmadi: <b>{yetkazilmaganlar}</b> ta",
        parse_mode="HTML"
    )

    await state.finish()


@dp.callback_query_handler(lambda u:u.data=="nosend",state="*")
async def nosend(call:types.CallbackQuery,state:FSMContext):
    await call.message.delete()
    await state.finish()
    await panel(call.message,state)





# --- FOTO YUBORISH JARAYONI ---

@dp.message_handler(content_types=types.ContentType.PHOTO, state="send_message")
async def send_xabar(msg: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(photo_id=msg.photo[-1].file_id)
    await msg.answer("<b>✍️ Rasmning izohini kiriting:</b>", parse_mode="HTML", reply_markup=tugatish)
    await state.set_state('Rasm_izoh')


@dp.message_handler(state="Rasm_izoh")
async def rasm(msg: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(description=msg.text)
    await msg.answer("Inline tugma uchun link yuboring:", reply_markup=tugatish)
    await state.set_state("rasm_inline_link")


@dp.message_handler(state="rasm_inline_link")
async def rasm_inline(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(link=message.text)
    await message.answer("Inline tugma uchun nom kiriting:", reply_markup=tugatish)
    await state.set_state("rasminline_nom")


@dp.message_handler(state="rasminline_nom")
async def rasm_nom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get("photo_id")
    description = data.get("description")
    link = data.get("link")
    name = message.text

    # inline tugmalar
    yubor = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{name}", url=f"{link}")],
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="raketaa"),
            InlineKeyboardButton(text="❌ Rad qilish", callback_data="uchma")
        ]
    ])

    await state.update_data(button_name=name)
    await message.answer_photo(
        photo=photo_id,
        caption=f"{description}\n\nUshbu xabarni yuborasizmi?",
        reply_markup=yubor
    )
    await state.set_state("jonatish")


@dp.callback_query_handler(lambda c: c.data == "raketaa", state="jonatish")
async def izoh_pho(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_id = data.get("photo_id")
    description = data.get("description")
    link = data.get("link")
    button_name = data.get("button_name")

    inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{button_name}", url=f"{link}")]
    ])

    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute(
    "SELECT DISTINCT user_id FROM userid WHERE status='active' AND user_id > 0"
)

    user_ids = cursor.fetchall()
    conn.close()

    bordi = 0
    bormadi = 0

    for user_id in user_ids:
        try:
            await bot.send_photo(user_id[0], photo=photo_id, caption=description, reply_markup=inline)
            bordi += 1
        except Exception as e:
            logging.error(f"Error sending message to {user_id[0]}: {e}")
            bormadi += 1

    await call.message.answer(
        f"<b>Xabar yuborish yakunlandi ✅</b>\n\n"
        f"🚀 Yetkazildi: <b>{bordi}</b> ta\n"
        f"🛑 Yetkazilmadi: <b>{bormadi}</b> ta",
        parse_mode="HTML"
    )
    await state.finish()

@dp.callback_query_handler(lambda u:u.data=="uchma",state="*")
async def uchma(call:types.CallbackQuery,state:FSMContext):
    await call.message.delete()
    await state.finish()
    await panel(call.message,state)

#Tugatish
    


# --- VIDEO YUBORISH BOSHLANISHI ---
@dp.message_handler(content_types=types.ContentType.VIDEO, state="send_message")
async def send_xabar_video(msg: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    # video fayl id saqlanadi
    await state.update_data(video_id=msg.video.file_id)
    await msg.answer("<b>✍️ Videoning izohini yozing:</b>", parse_mode="HTML", reply_markup=tugatish)
    await state.set_state('Video_izoh')


@dp.message_handler(state="Video_izoh")
async def video_izoh(msg: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(video_caption=msg.text)
    await msg.answer("Inline tugma uchun link yuboring:", reply_markup=tugatish)
    await state.set_state("video_inline_link")


@dp.message_handler(state="video_inline_link")
async def video_inline(message: types.Message, state: FSMContext):
    tugatish = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tugatish", callback_data="tugat")]
    ])

    await state.update_data(video_link=message.text)
    await message.answer("Inline tugma uchun nom kiriting:", reply_markup=tugatish)
    await state.set_state("video_inline_nom")


@dp.message_handler(state="video_inline_nom")
async def video_nom(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_id = data.get("video_id")
    video_caption = data.get("video_caption")
    video_link = data.get("video_link")
    button_name = message.text

    yubor = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{button_name}", url=f"{video_link}")],
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="raketaaa"),
            InlineKeyboardButton(text="❌ Rad qilish", callback_data="uchmaaa")
        ]
    ])

    await state.update_data(button_name=button_name)

    await message.answer_video(
        video=video_id,
        caption=f"{video_caption}\n\nUshbu xabarni yuborasizmi?",
        reply_markup=yubor
    )

    await state.set_state("jonatish_video")


@dp.callback_query_handler(lambda c: c.data == "raketaaa", state="jonatish_video")
async def izoh_vid(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    video_id = data.get("video_id")
    video_caption = data.get("video_caption")
    video_link = data.get("video_link")
    button_name = data.get("button_name")

    inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{button_name}", url=f"{video_link}")]
    ])

    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute(
    "SELECT DISTINCT user_id FROM userid WHERE status='active' AND user_id > 0"
)

    user_ids = cursor.fetchall()
    conn.close()

    bordi = 0
    bormadi = 0

    for user_id in user_ids:
        try:
            await bot.send_video(user_id[0], video=video_id, caption=video_caption, reply_markup=inline)
            bordi += 1
        except Exception as e:
            logging.error(f"Error sending video to {user_id[0]}: {e}")
            bormadi += 1

    await call.message.answer(
        f"<b>🎬 Video xabar yuborish yakunlandi!</b>\n\n"
        f"🚀 Yetkazildi: <b>{bordi}</b> ta\n"
        f"🛑 Yetkazilmadi: <b>{bormadi}</b> ta",
        parse_mode="HTML"
    )

    await state.finish()

@dp.callback_query_handler(lambda t:t.data=="tugat",state="*")
async def tugat(query:types.CallbackQuery,state:FSMContext):
    await query.message.delete()
    await state.finish()


@dp.callback_query_handler(lambda u:u.data=="uchmaaa",state="*")
async def uchma(call:types.CallbackQuery,state:FSMContext):
    await call.message.delete()
    await state.finish()
    await panel(call.message,state)




@dp.message_handler(text='📑Users', state="*")
async def export_users_command(message: types.Message, state: FSMContext):

    await export_users()
    with open('user_ids.txt', 'rb') as file:
        await message.answer_document(file)
        await state.finish()

@dp.message_handler(text='📑Baza', state="*")
async def export_db_command(message: types.Message, state: FSMContext):
    # Bazaning asl faylini nusxalash
    db_file_path = 'kinoqish.db'  # Bazangizning yo'li
    backup_db_path = 'database_backup.db'  # Nusxasi saqlanadigan fayl nomi

    # Faylni nusxalash
    shutil.copy(db_file_path, backup_db_path)

    # Faylni yuborish
    with open(backup_db_path, 'rb') as file:
        await message.answer_document(file)

    # Holatni yakunlash
    await state.finish()


from aiogram import types
from aiogram.dispatcher import FSMContext

ZAYAF_KANAL = []

@dp.message_handler(text="➕Zayafka tugma", state="*")
async def zayaf(message: types.Message, state: FSMContext):
    await message.answer("Zayafka tugma qo'shish uchun kanal linkini yuboring!")
    await state.finish()
    await state.set_state("zayaf_link")

@dp.message_handler(content_types=["text"], state="zayaf_link")
async def zayaf_n(message: types.Message, state: FSMContext):
    zayaf_link = message.text.strip()

    if zayaf_link.startswith((
            'https://t.me/', 
            '@', 
            'https://instagram.com/', 
            'https://www.instagram.com/', 
            'https://youtube.com/', 
            'https://www.youtube.com/', 
            'https://youtu.be/'
        )):
        ZAYAF_KANAL.append(zayaf_link)
        await message.answer(
            f"✅ Zayafka link qo‘shildi!\n"
            f"🔗 Yuborilgan link: {zayaf_link}\n"
            f"📊 Jami zayafka linklar soni: {len(ZAYAF_KANAL)}"
        )
        await state.finish()
    else:
        await message.answer(
            "❌ Iltimos, to'g'ri link yuboring:\n"
            "- Telegram: https://t.me/... yoki @username\n"
            "- Instagram: https://instagram.com/username\n"
            "- YouTube: https://youtube.com/... yoki https://youtu.be/..."
        )


@dp.message_handler(text="❌Zayafka o'chirish", state="*")
async def delete_zayaf_menu(message: types.Message, state: FSMContext):
    if not ZAYAF_KANAL:
        await message.answer("Hozircha zayafka kanallari mavjud emas!")
        return
    
    # Kanal ro'yxatini chiqaramiz
    kanal_list = "\n".join([f"{i+1}. {link}" for i, link in enumerate(ZAYAF_KANAL)])
    await message.answer(
        f"Zayafka kanallari ro'yxati:\n{kanal_list}\n\n"
        "O'chirmoqchi bo'lgan kanal linkini yuboring yoki raqamini yozing:"
    )
    await state.set_state("delete_zayaf")

@dp.message_handler(state="delete_zayaf")
async def process_delete_zayaf(message: types.Message, state: FSMContext):
    user_input = message.text.strip()
    
    # Raqam orqali o'chirish
    if user_input.isdigit():
        index = int(user_input) - 1
        if 0 <= index < len(ZAYAF_KANAL):
            deleted_link = ZAYAF_KANAL.pop(index)
            await message.answer(
                f"✅ Kanal o'chirildi:\n{deleted_link}\n"
                f"Qolgan kanallar soni: {len(ZAYAF_KANAL)}"
            )
            await state.finish()
            return
    
    # Link orqali o'chirish
    if user_input in ZAYAF_KANAL:
        ZAYAF_KANAL.remove(user_input)
        await message.answer(
            f"✅ Kanal o'chirildi:\n{user_input}\n"
            f"Qolgan kanallar soni: {len(ZAYAF_KANAL)}"
        )
    else:
        await message.answer("❌ Noto'g'ri raqam yoki link kiritildi! Qaytadan urinib ko'ring:")
        return
    
    await state.finish()


@dp.message_handler(commands=["start"], state="*")
async def start(message: types.Message, state: FSMContext):
    
    user_id = message.from_user.id
    user_name_full = message.from_user.full_name
    movie_name = None
    
    from datetime import datetime as dt
    today = dt.now().strftime("%Y-%m-%d")  # STATISTIKA UCHUN

    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # 🔹 Premium foydalanuvchimi tekshirish
        cursor.execute("SELECT added_time FROM premium_users WHERE user_id = ?", (user_id,))
        premium_data = cursor.fetchone()
        is_premium = False

        if premium_data:
            from datetime import datetime, timedelta
            added_time = datetime.strptime(premium_data[0], "%Y-%m-%d %H:%M")
            now = datetime.now()

            if now - added_time < timedelta(days=30):
                is_premium = True
            else:
                cursor.execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
                conn.commit()

        # 🔹 Foydalanuvchini bazaga qo‘shish
        cursor.execute("SELECT COUNT(*) FROM userid WHERE user_id = ?", (user_id,))
        user_exists = cursor.fetchone()[0]

        if user_exists == 0:
            # Asosiy jadvalga qo‘shamiz
            cursor.execute("INSERT INTO userid (user_id, status) VALUES (?, ?)", (user_id, "active"))
            conn.commit()

            # 🔥 STATISTIKA UCHUN — bugungi jadvalga yozish
            cursor.execute(
                "INSERT INTO userid_today (user_id_tod, registration_date) VALUES (?, ?)",
                (user_id, today)
            )
            conn.commit()

            # 🔔 Admin kanalga xabar
            cursor.execute("SELECT COUNT(*) FROM userid")
            user_count = cursor.fetchone()[0]
            channel_id = '-1003251566589'
            message_text = (
                f"<b>Yangi foydalanuvchi:</b>\n"
                f"1. Ism: <i>{user_name_full}</i>\n"
                f"2. Profil: tg://user?id={user_id}\n"
                f"3. Jami Foydalanuvchi: {user_count}"
            )
            try:
                await bot.send_message(channel_id, message_text, parse_mode="HTML")
            except:
                pass

    


        # Agar foydalanuvchi kino kodi bilan kirgan bo‘lsa
        if " " in message.text:
            movie_name = message.text.split(" ", 1)[1].strip().lower()
            cursor.execute(
                '''SELECT name, description, video_file_id, movie_code, download_count 
                   FROM movies 
                   WHERE LOWER(name) LIKE ? OR movie_code LIKE ?''',
                ('%' + movie_name + '%', '%' + movie_name + '%')
            )
            movie_data = cursor.fetchone()

        # 🔹 Agar premium foydalanuvchi bo‘lsa — kanallarni tekshirmaymiz
        if is_premium:
            pass
        #     await bot.send_message(
        #     chat_id=message.chat.id,
        #     text=f"Assaloomu alaykum, Kino kodini jo'nating! ✍️",
        #     parse_mode="MARKDOWN"
        # )
        else:
            # Oddiy foydalanuvchilar uchun kanal obunasi tekshiriladi
            cursor.execute("SELECT channel_id, channel_url FROM channel")
            channels = cursor.fetchall()

            unsubscribed_channels = []
            for channel_id, _ in channels:
                status = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if status.status == "left":
                    unsubscribed_channels.append(channel_id)

            if unsubscribed_channels:
                keyboard = InlineKeyboardMarkup(row_width=1)
                

                for zayaf_url in ZAYAF_KANAL:
                    keyboard.add(InlineKeyboardButton(text="➕ Obuna bo'lish", url=zayaf_url))
                for _, channel_url in channels:
                    keyboard.add(InlineKeyboardButton(text="➕ Obuna bo'lish", url=channel_url))

                keyboard.add(InlineKeyboardButton(text="Tekshirish ✅", url="https://t.me/kinoqishbot?start=True"))
                keyboard.add(InlineKeyboardButton(text="💎Premium",callback_data="premium_info"))
                
                await message.reply(
                    """❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak.\n
                    ```💎 Premium obuna sotib olib, kanallarga obuna bo‘lmasdan foydalanishingiz mumkin.``` """,
                    reply_markup=keyboard,
                    parse_mode='MARKDOWN'
                )
                await state.set_state("byprm2")
                return

    # 🔹 Obunadan o‘tgan yoki premium foydalanuvchi uchun davom etamiz
    if movie_name and movie_data:
      
        name, description, video_file_id, movie_code, download_count = movie_data
        new_download_count = download_count + 1

        with sqlite3.connect('kinoqish.db') as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE movies SET download_count = ? WHERE movie_code = ?", (new_download_count, movie_code))
            conn.commit()

        inline = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Do'stlarga yuborish", switch_inline_query=f"{movie_code}"),
                    InlineKeyboardButton(text="📥 Saqlash", callback_data=f"save_movie:{movie_code}")
                ],
                [
                    InlineKeyboardButton(text="🛒 Saqlanganlar", callback_data="kor_kino")
                ],
                [
                    InlineKeyboardButton(text="🔍Nom orqali qidirish...", switch_inline_query_current_chat="")
                ]
            ],
            row_width=2
        )

        await bot.send_video(
            chat_id=message.chat.id,
            video=video_file_id,
            caption=f"<b>{name}</b>\n\n{description}\n👁:<b>{new_download_count}</b>",
            reply_markup=inline,
            parse_mode="HTML"
        )

    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text="Assalomu alaykum, Botimizga xush kelibsiz!\n\nKino kodini jo'nating! ✍️",
            parse_mode="MARKDOWN"
            
             
        )
        await state.set_state("name_qidir")


# ------------------ Premium tugmasi bosilganda ------------------
@dp.message_handler(commands=["premium"],state="*")
async def premium_menu(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    with sqlite3.connect("kinoqish.db") as conn:
        cursor = conn.cursor()
        # Tekshiradi: user premiumga ega yoki yo'q
        cursor.execute("SELECT added_time FROM premium_users WHERE user_id = ?", (user_id,))
        data = cursor.fetchone()

        now = datetime.now()

        if data:
            added_time = datetime.strptime(data[0], "%Y-%m-%d %H:%M")
            end_time = added_time + timedelta(days=30)

            if now < end_time:
                # Premium faolligi hali tugamagan
                text = (
                    f"💎 Sizning Premium obunangiz faol ✅\n\n"
                    f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
                    f"🕐 Boshlangan: {added_time.strftime('%Y-%m-%d %H:%M')}\n"
                    f"⏰ Tugash: {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"Reklamasiz va yuqori sifatli videolardan foydalanishingiz mumkin!"
                )
                await message.answer(text)
                return

        # Agar premium yo‘q bo‘lsa — info + sotib olish tugmasi
        text = (
            "🎟 <b>AR7 MOVIE Premium</b>\n\n"
            "💎 Premium obuna sizga quyidagi imkoniyatlarni beradi:\n"
            "• 📺 Kanallarga obunasiz kinolarni ko‘rish\n"
            "• 🎞 Yuqori sifatli kinolarni ko‘rish\n"
            "• 🚫 Reklamalarsiz foydalanish\n"
            "• ⚡ Tezroq video yuklanish\n"
            "• 🕐 Obuna muddati: <b>1 oy</b>\n\n"
            "💰 Narxi: <b>12 000 so‘m</b>\n\n"
            "💳 Sotib olish uchun quyidagi tugmani bosing 👇"
        )

        buy_button = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("💳 Sotib olish", callback_data="buy_premium"),
            InlineKeyboardButton("⬅️ Orqaga", url="https://t.me/kinoqishbot?start=True")
        )

        await message.answer(text, parse_mode="HTML", reply_markup=buy_button)
# ---------- PREMIUM-------------#

@dp.callback_query_handler(lambda c: c.data == "premium_info",state="*")
async def premium_info(callback_query: types.CallbackQuery,state:FSMContext):
    text = (
        "🎟 <b>AR7 MOVIE Premium</b>\n\n"
        "💎 Premium obuna sizga quyidagi imkoniyatlarni beradi:\n"
        "• 📺 Kanallarga obunasiz kinolarni ko‘rish\n"
        "• 🎞 Yuqori sifatli kinolarni ko‘rish\n"
        "• 🚫 Reklamalarsiz foydalanish\n"
        "• ⚡ Tezroq video yuklanish\n"
        "• 🕐 Obuna muddati: <b>1 oy</b>\n\n"
        "💰 Narxi: <b>12 000 so‘m</b>\n\n"
        "💳 Sotib olish uchun quyidagi tugmani bosing 👇"
    )
    buy_button = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("💳 Sotib olish", callback_data="buy_premium"),
        InlineKeyboardButton("⬅️ Orqaga", url="https://t.me/kinoqishbot?start=True")
    )
    await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=buy_button)
    await state.set_state("byprm3")


from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup



@dp.callback_query_handler(lambda c: c.data == "buy_premium",state="*")
async def buy_premium(callback_query: types.CallbackQuery, state: FSMContext):
    premium_text = (
        "💎 <b>Premium obuna</b>\n\n"
        "🕐 Muddati: <b>1 oy</b>\n"
        "💰 Narxi: <b>12 000 so‘m</b>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>To‘lov qabul qiluvchi:</b>\n"
        "   Asadbek Rahmonov\n\n"
        "💳 <b>Karta raqami:</b>\n"
        "   <code>9860 0121 2777 4144</code>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "✅ To‘lovni amalga oshirgandan so‘ng <b>chek rasmini shu yerga yuboring.</b>\n\n"
        "⚠️ <i>Faqat to‘lovni qilgan shaxsning cheki qabul qilinadi!</i>"
    )

    # 🔹 Inline tugmalar (Sotib olish + Orqaga)
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("⬅️ Orqaga", url="https://t.me/kinoqishbot?start=True")
    )

    # 🔹 O‘sha xabarni yangilab chiqarish
    await callback_query.message.edit_text(premium_text, parse_mode="HTML", reply_markup=markup)
  
    await callback_query.answer()
    await state.set_state("byprm4")




CHANNEL_ID_PRM = -1003327939504  # admin kanal ID
# ADMIN_ID_PRM = 123456789  # admin foydalanuvchi ID (xohlovchi rad/qo‘shish tugmasi bosadi)



@dp.message_handler(content_types=['photo'], state="byprm4")
async def handle_check(message: types.Message, state: FSMContext):
    global full_prem;
    user_id = message.from_user.id
    full_prem = message.from_user.full_name
    photo_id = message.photo[-1].file_id

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    caption = (
        f"📸 <b>Yangi Premium to‘lov:</b>\n\n"
        f"👤 Ism: <i>{full_prem}</i>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🕒 Vaqt: {now}\n\n"
        f"<b>Admin:</b> foydalanuvchini premiumga qo‘shish yoki rad eting 👇"
    )

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Qo‘shish", callback_data=f"approve_premium:{user_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_premium:{user_id}")
        ]
    ])

    await bot.send_photo(CHANNEL_ID_PRM, photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=buttons)
    await message.answer("✅ Chekingiz yuborildi. Admin tasdiqlashi kutilmoqda...")
    await state.finish()



from datetime import datetime, timedelta
import sqlite3

@dp.callback_query_handler(lambda c: c.data.startswith("approve_premium:"))
async def approve_premium(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split(":")[1])
    now = datetime.now()
    end_date = now + timedelta(days=30)  # ✅ 30 kunlik premium

    # Ma'lumotlar bazasiga yozish
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO premium_users (user_id, full_name, added_time, end_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, f"{full_prem}", now.strftime("%Y-%m-%d %H:%M"), end_date.strftime("%Y-%m-%d %H:%M")))
        conn.commit()

    # Foydalanuvchiga xabar
    try:
        await bot.send_message(
            user_id,
            f"🎉 Sizning Premium obunangiz faollashtirildi!\n"
            f"📅 Tugash muddati: {end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"Boshlash uchun /start ni bosing."
        )
    except:
        pass

    # “Javob yozish” tugmasi
    reply_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💬 Javob yozish", url=f"tg://user?id={user_id}")]
    ])

    await callback_query.message.edit_caption(
        caption=callback_query.message.caption + "\n\n✅ <b>Premium faollashtirildi (30 kunlik)</b>",
        parse_mode="HTML",
        reply_markup=reply_btn
    )

    await callback_query.answer("✅ Premium faollashtirildi.")



@dp.callback_query_handler(lambda c: c.data.startswith("reject_premium:"))
async def reject_premium(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split(":")[1])

    reply_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💬 Javob yozish", url=f"tg://user?id={user_id}")]
    ])

    await callback_query.message.edit_caption(
        caption=callback_query.message.caption + "\n\n❌ <b>To‘lov rad etildi</b>",
        parse_mode="HTML",
        reply_markup=reply_btn
    )

    try:
        await bot.send_message(
            user_id,
            "❌ Siz yuborgan Premium to‘lov rad etildi. Iltimos, to‘lovni tekshirib qaytadan urinib ko‘ring."
        )
    except:
        pass

    await callback_query.answer("❌ To‘lov rad etildi.")




@dp.callback_query_handler(lambda c: c.data == "random",state="*")
async def send_random_movie(callback_query: types.CallbackQuery):
    # Establish database connection and create cursor
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Select a random movie from the database
        cursor.execute("SELECT name, description, video_file_id, movie_code, download_count FROM movies ORDER BY RANDOM() LIMIT 1")
        movie = cursor.fetchone()

        if movie:
            name, description, video_file_id, movie_code, download_count = movie

            # Increment the download count
            new_download_count = download_count + 1
            cursor.execute(
                "UPDATE movies SET download_count = ? WHERE movie_code = ?",
                (new_download_count, movie_code)
            )
            conn.commit()

            # Inline button markup
            inline = InlineKeyboardMarkup(
                inline_keyboard=[ 
                    [
                        InlineKeyboardButton(
                            text="Do'stlarga yuborish",
                            switch_inline_query=f"{movie_code}"  # movie_code ni yuborish
                        ),
                        InlineKeyboardButton(
                            text="📥 Saqlash", callback_data=f"save_movie:{movie_code}"  # Callbackda movie_codeni berish
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🛒 Saqlanganlar", callback_data="kor_kino"
                        )
                    ],
                    [
                        InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat=""),
                        InlineKeyboardButton(text="Keyingisi⏩", callback_data="rand2")
                    ]
                ],
                row_width=2
            )

            # Delete the previous message before sending the new one
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id
            )

            # Send the video with updated download count
            if video_file_id:
                await bot.send_video(
                    chat_id=callback_query.from_user.id,
                    caption=f"🎬 **{name}**\n\n📖 {description}\n👁️: <b>{new_download_count}</b>",
                    video=video_file_id,
                    reply_markup=inline,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=callback_query.from_user.id,
                    text=f"🎬 **{name}**\n\n📖 {description}\n👁️: <b>{new_download_count}</b>",
                    reply_markup=inline,
                    parse_mode="HTML"
                )
        else:
            await bot.send_message(
                chat_id=callback_query.from_user.id,
                text="Hozircha kinolar bazada yo'q."
            )

    # Acknowledge callback query
    await callback_query.answer()



@dp.callback_query_handler(lambda c: c.data == "rand2",state="*")
async def send_random_movie(callback_query: types.CallbackQuery):
    # Establish database connection and create cursor
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Select a random movie from the database
        cursor.execute("SELECT name, description, video_file_id, movie_code, download_count FROM movies ORDER BY RANDOM() LIMIT 1")
        movie = cursor.fetchone()

        if movie:
            name, description, video_file_id, movie_code, download_count = movie

            # Increment the download count
            new_download_count = download_count + 1
            cursor.execute(
                "UPDATE movies SET download_count = ? WHERE movie_code = ?",
                (new_download_count, movie_code)
            )
            conn.commit()

            # Inline button markup
            inline = InlineKeyboardMarkup(
                inline_keyboard=[ 
                    [
                        InlineKeyboardButton(
                            text="Do'stlarga yuborish",
                            switch_inline_query=f"{movie_code}"  # movie_code ni yuborish
                        ),
                        InlineKeyboardButton(
                            text="📥 Saqlash", callback_data=f"save_movie:{movie_code}"  # Callbackda movie_codeni berish
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🛒 Saqlanganlar", callback_data="kor_kino"
                        )
                    ],
                    [
                        InlineKeyboardButton(text="🔍Nom orqali qidirish...", switch_inline_query_current_chat=""),
                        InlineKeyboardButton(text="Keyingisi⏩", callback_data="rand2")
                    ]
                ],
                row_width=2
            )

            # Delete the previous message before sending the new one
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id
            )

            # Send the video with updated download count
            if video_file_id:
                await bot.send_video(
                    chat_id=callback_query.message.chat.id,
                    video=video_file_id,
                    caption=f"🎬 **{name}**\n\n📖 {description}\n👁️: <b>{new_download_count}</b>",
                    reply_markup=inline,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=f"🎬 **{name}**\n\n📖 {description}\n👁️: <b>{new_download_count}</b>",
                    reply_markup=inline,
                    parse_mode="HTML"
                )
        else:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text="Hozircha kinolar bazada yo'q."
            )

    # Acknowledge callback query
    await callback_query.answer()




from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked
# Admin's user ID for direct communication (replace with actual admin ID)
ADMIN_USER_ID = 1996936737  # Example, replace with your admin's user ID
CHANNEL_ID = "-1002295487802"  # Replace with your actual channel ID
# States for suggestion handling
class SuggestionStates(StatesGroup):
    waiting_for_suggestion = State()

# Handle "Savol yoki Taklif Yuborish" button click
@dp.callback_query_handler(lambda call: call.data == "send_suggestion_", state="*")
async def ask_suggestion(call: types.CallbackQuery, state: FSMContext):
    savekb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bekorx")]
        ],
        row_width=2
    )
    
    try:
        await call.message.edit_text(
            "🎬 Kino so'rash :\n\n"
            "Iltimos, Kerakli kino kodini yozing:",
            reply_markup=savekb
        )
        await SuggestionStates.waiting_for_suggestion.set()
    except Exception as e:
        print(f"Error in ask_suggestion: {e}")
        await call.answer("Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.", show_alert=True)

# Handle cancellation
@dp.callback_query_handler(lambda c: c.data == "bekorx", state=SuggestionStates.waiting_for_suggestion)
async def cancel_suggestion(callback_query: types.CallbackQuery, state: FSMContext):
    kanalim = InlineKeyboardMarkup(
             inline_keyboard=[
                [InlineKeyboardButton(text="🎥 Top Filmlar Kanali", url="https://t.me/+uqrl9b1_rPIyOTQy"),
                 InlineKeyboardButton(text="🗒 Kategoriya",callback_data="name_search")],
                [InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat=""),
                 InlineKeyboardButton(text="Kop qidirilganlar | 10", callback_data="top_movies")],
                [InlineKeyboardButton(
                        text="🛒 Saqlanganlar", callback_data="kor_kino"
                    ),
                    InlineKeyboardButton(
                        text="🎲Random", callback_data="random")
                        ],
                [InlineKeyboardButton("Kino so'rash | Savol yoki Taklif ", callback_data=f"send_suggestion_")]  
            ],row_width=2
        )
    
    try:
        await callback_query.message.edit_text(
            "Kino kerakmi?✍️ Kerakli kino kodini botga jonating. Bot kinoni tashlab beradi.",
            parse_mode="HTML",
            reply_markup=kanalim
        )
        await state.finish()
    except Exception as e:
        print(f"Error in cancel_suggestion: {e}")
        await callback_query.answer("Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.", show_alert=True)

@dp.message_handler(state=SuggestionStates.waiting_for_suggestion, content_types=types.ContentTypes.TEXT)
async def handle_suggestion(message: types.Message, state: FSMContext):
    savekb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bosh sahifa", callback_data="cancel")]
        ],
        row_width=2
    )
    
    user_full = message.from_user.full_name
    user_id = message.from_user.id
    suggestion_text = message.text

    # Xabardan raqamni ajratib olish
    movie_code = None
    for word in suggestion_text.split():
        # Faqat raqamlarni ajratib olamiz
        digits = ''.join(filter(str.isdigit, word))
        if digits:  # Agar raqam topilsa
            movie_code = digits
            break

    try:
        if movie_code:
            # Avtomatik javob yuboramiz
            response_text = (
                f"🎬 Siz yuborgan {movie_code} kodli kinoni ko'rish uchun quyidagi tugmani bosing:\n\n"
                f"🔢 Kino kodi: {movie_code}"
            )
            
            # Tugma yaratamiz
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    text="🎥 Kino ko'rish", 
                    url=f"https://t.me/kinoqishbot?start={movie_code}"
                )
            )
            
            # Foydalanuvchiga javob yuboramiz
            await bot.send_message(
                chat_id=user_id,
                text=response_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Admin ga xabar beramiz (avtomatik javob yuborilganligi haqida)
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📩 *Avtomatik javob yuborildi*\n\n"
                     f"👤 Foydalanuvchi: [{user_full}](tg://user?id={user_id})\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"🔢 Topilgan kod: `{movie_code}`\n"
                     f"📝 Xabar: `{suggestion_text}`",
                parse_mode="Markdown"
            )
            
            await message.answer(
                "✅ Sizning so'rovingiz qabul qilindi va avtomatik javob yuborildi.",
                reply_markup=savekb
            )
        else:
            # Agar kod topilmasa, admin ko'rib chiqadi
            botga = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Botga o'tish", url="https://t.me/kinoqishbot"),
                     InlineKeyboardButton(text="Javob yozish", url=f"tg://user?id={user_id}")]
                ],
                row_width=2
            )
            
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📩 *Yangi kino so'rovi (Avtomatik javob topilmadi)*\n\n"
                     f"👤 Foydalanuvchi: [{user_full}](tg://user?id={user_id})\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"📝 Xabar: `{suggestion_text}`",
                parse_mode="Markdown",
                reply_markup=botga
            )
            
            await message.answer(
                "✅ Xabaringiz adminga yuborildi. Tez orada javob beriladi.",
                reply_markup=savekb
            )
            
    except BotBlocked:
        await message.answer("❌ Botni bloklagansiz. Iltimos, blokni olib tashlang.")
    except Exception as e:
        print(f"Error in handle_suggestion: {e}")
        await message.answer("❌ Xatolik yuz berdi, iltimos qaytadan urinib ko'ring.")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("autojavob:"), state="*")
async def send_auto_response(callback_query: types.CallbackQuery):
    try:
        # Callback datani ajratib olamiz: user_id:message_text
        parts = callback_query.data.split(":")
        if len(parts) < 3:
            await callback_query.answer("❌ Xatolik: Noto'g'ri format!", show_alert=True)
            return
            
        user_id = parts[1]
        original_message = ":".join(parts[2:])  # Qolgan qismini birlashtiramiz
        
        # Xabardan raqamni ajratib olish
        movie_code = None
        for word in original_message.split():
            # Faqat raqamlarni ajratib olamiz
            digits = ''.join(filter(str.isdigit, word))
            if digits:  # Agar raqam topilsa
                movie_code = digits
                break

        if movie_code:
            # Javob matnini tayyorlaymiz
            response_text = (
                f"🎬 Siz yuborgan {movie_code} kodli kinoni ko'rish uchun quyidagi tugmani bosing:\n\n"
                f"🔢 Kino kodi: {movie_code}"
            )
            
            # Tugma yaratamiz
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton(
                    text="🎥 Kino ko'rish", 
                    url=f"https://t.me/kinoqishbot?start={movie_code}"
                )
            )
        else:
            response_text = "✅ Sizning so'rovingiz qabul qilindi. Tez orada javob beramiz."
            keyboard = None

        try:
            # Foydalanuvchiga javob yuboramiz
            await bot.send_message(
                chat_id=user_id,
                text=response_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Admin ga xabar beramiz
            await callback_query.answer("✅ Avtomatik javob yuborildi!", show_alert=True)
            
            # Xabarga "Javob berildi" belgisini qo'yamiz
            await callback_query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Javob berildi", callback_data="already_responded")]
                    ]
                )
            )
            
        except Exception as send_error:
            print(f"Xatolik: {send_error}")
            await callback_query.answer("❌ Javob yuborib bo'lmadi!", show_alert=True)
            
    except Exception as e:
        print(f"Xatolik: {e}")
        await callback_query.answer("❌ Xatolik yuz berdi!", show_alert=True)
        
@dp.callback_query_handler(lambda c: c.data == "already_responded", state="*")
async def already_responded(callback_query: types.CallbackQuery):
    await callback_query.answer("Bu xabarga allaqachon javob berilgan", show_alert=True)

# 
    
async def export_users():
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM userid')
    user_ids = cursor.fetchall()

    existing_user_ids = set()
    try:
        with open('user_ids.txt', 'r') as existing_file:
            existing_user_ids = set(map(int, existing_file.read().split()))
    except FileNotFoundError:
        pass

    new_user_ids = [str(user_id[0]) for user_id in user_ids if user_id[0] not in existing_user_ids]

    with open('user_ids.txt', 'a') as file:
        file.write('\n'.join(new_user_ids) + '\n')

    conn.close()



import aiogram.utils
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
import sqlite3
from datetime import datetime

@dp.message_handler(lambda message: message.text.isdigit(), state="*")
async def check_movie_code(msg: Message, state: FSMContext):
    user_id = msg.from_user.id
    movie_code = msg.text

    # 🔹 Premium holatini tekshirish
    is_premium = False
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT added_time, end_date
            FROM premium_users
            WHERE user_id = ?
        """, (user_id,))
        user = cursor.fetchone()

    if user:
        added_time, end_date = user
        if end_date:
            try:
                # 🔸 Formatni avtomatik aniqlash
                try:
                    expiry_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M")
                except ValueError:
                    expiry_date = datetime.strptime(end_date, "%Y-%m-%d")

                if expiry_date > datetime.now():
                    is_premium = True
                else:
                    # Premium muddati tugagan — o‘chirish
                    with sqlite3.connect('kinoqish.db') as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM premium_users WHERE user_id=?", (user_id,))
                        conn.commit()
            except Exception as e:
                print(f"Premium date parse error: {e}")
        else:
            # Agar end_date bo‘lmasa ham, premium deb hisoblaymiz (xato saqlangan bo‘lishi mumkin)
            is_premium = True

    # 🔹 Agar premium bo‘lsa — kanal tekshiruvisiz davom etadi
    if is_premium:
        pass
    else:
        # 🔹 Premium bo‘lmasa, kanalga obuna bo‘lishni so‘rash
        with sqlite3.connect('kinoqish.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, channel_url FROM channel")
            channels = cursor.fetchall()

        unsubscribed_channels = []
        for channel_id, _ in channels:
            try:
                status = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if status.status == "left":
                    unsubscribed_channels.append(channel_id)
            except:
                continue

        if unsubscribed_channels:
            keyboard = InlineKeyboardMarkup(row_width=1)
            

            for zayaf_url in ZAYAF_KANAL:
                keyboard.add(InlineKeyboardButton(text="➕ Obuna bo‘lish", url=zayaf_url))

            for _, channel_url in channels:
                keyboard.add(InlineKeyboardButton(text="➕ Obuna bo‘lish", url=channel_url))

            keyboard.add(InlineKeyboardButton(text="✅ Tekshirish", url="https://t.me/kinoqishbot?start=True"))
            keyboard.add(InlineKeyboardButton(text="💎 Premium olish", callback_data="premium_info"))

            await msg.reply(
                    """❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak.\n
                    ```💎 Premium obuna sotib olib, kanallarga obuna bo‘lmasdan foydalanishingiz mumkin.``` """,
                    reply_markup=keyboard,
                    parse_mode='MARKDOWN'
                )
            await state.finish()
            await state.set_state("byprm1")
            return

    # 🔹 Kino ma‘lumotlarini olish
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, video_file_id, download_count FROM movies WHERE movie_code = ?", (movie_code,))
        movie_data = cursor.fetchone()

    if not movie_data:
        await msg.answer("❌ Bunday kodli kino hozircha mavjud emas.")
        return

    name, description, video_file_id, download_count = movie_data

    if not video_file_id:
        await msg.answer("❌ Video fayli topilmadi yoki noto‘g‘ri ID.")
        return

    try:
        # 🔹 Yuklab olish hisobini yangilash
        new_download_count = download_count + 1
        with sqlite3.connect('kinoqish.db') as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE movies SET download_count = ? WHERE movie_code = ?", (new_download_count, movie_code))
            conn.commit()

        inline = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Do‘stlarga yuborish", switch_inline_query=f"{movie_code}"),
                    InlineKeyboardButton(text="📥 Saqlash", callback_data=f"save_movie:{movie_code}")
                ],
                [
                    InlineKeyboardButton(text="🛒 Saqlanganlar", callback_data="kor_kino")
                ],
                [
                    InlineKeyboardButton(text="🔍Nom orqali qidirish...", switch_inline_query_current_chat="")
                ]
            ],
            row_width=2
        )

        await bot.send_video(
            chat_id=msg.chat.id,
            video=video_file_id,
            caption=f"{name}\n\n{description}\n👁:<b>{new_download_count}</b>",
            reply_markup=inline,
            parse_mode="HTML"
        )

    except aiogram.utils.exceptions.WrongFileIdentifier:
        await msg.answer("❌ Noto‘g‘ri video fayli yoki ID. Iltimos, ma‘lumotlarni yangilang.")


@dp.callback_query_handler(lambda c: c.data == "top_movies",state="*")
async def show_top_movies(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    savekb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙Bosh sahifa", callback_data="backs")]
        ],row_width=2
    )

    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Eng ko'p yuklangan 10 ta kinoni olish
        cursor.execute("""
            SELECT movie_code, name, download_count 
            FROM movies 
            ORDER BY download_count DESC 
            LIMIT 10
        """)
        top_movies = cursor.fetchall()

    if not top_movies:
        await callback_query.message.edit_text("Hozircha top filmlar mavjud emas! 🔥",reply_markup=savekb)
        return

    # Top filmlar ro'yxatini yaratish
    movie_list = "\n".join([f"{idx + 1}. {movie[1]} - 👁 {movie[2]}" for idx, movie in enumerate(top_movies)])

    # Inline tugmalarni yaratish
    inline = InlineKeyboardMarkup(row_width=5)
    for idx, movie in enumerate(top_movies):
        inline.add(InlineKeyboardButton(text=str(idx + 1), callback_data=f"movie__{movie[0]}"))
    inline.add(InlineKeyboardButton(text="🔙Bosh sahifa",callback_data="backs"))

    # Xabarni yangilash
    await callback_query.message.edit_text(
        f"🔥 Eng ko'p yuklangan filmlar:\n\n{movie_list}",
        reply_markup=inline
    )


@dp.callback_query_handler(lambda c:c.data=="backs",state="*")
async def backs(calmes:types.CallbackQuery):
    
    kanalim = InlineKeyboardMarkup(
             inline_keyboard=[
                [InlineKeyboardButton(text="🎥 Top Filmlar Kanali", url="https://t.me/+uqrl9b1_rPIyOTQy"),
                 InlineKeyboardButton(text="🗒 Kategoriya",callback_data="name_search")],
                [InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat=""),
                 InlineKeyboardButton(text="Kop qidirilganlar | 10", callback_data="top_movies")],
                [InlineKeyboardButton(
                        text="🛒 Saqlanganlar", callback_data="kor_kino"
                    ),
                    InlineKeyboardButton(
                        text="🎲Random", callback_data="random")
                        ],
                [InlineKeyboardButton("Kino so'rash | Savol yoki Taklif ", callback_data=f"send_suggestion_")]  
            ],row_width=2
        )
    await calmes.message.edit_text("Kino kerakmi? \n\nKerakli kino <b>kodini, nomini</b> kiriting yoki <b>Qidirish</b> tugmasi orqali kinolarni qidiring!",parse_mode="HTML",reply_markup=kanalim)

@dp.callback_query_handler(lambda c: c.data.startswith("movie__"),state="*")
async def send_movie_from_top(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    movie_code = callback_query.data.split("__")[1]  # Movie code ni ajratib olish
    inline = InlineKeyboardMarkup(
            inline_keyboard=[ 
                [
                    InlineKeyboardButton(
                        text="Do'stlarga yuborish",
                        switch_inline_query=f"{movie_code}"  # movie_code ni yuborish
                    ),
                    InlineKeyboardButton(
                        text="📥 Saqlash", callback_data=f"save_movie:{movie_code}"  # Callbackda movie_codeni berish
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🛒 Saqlanganlar", callback_data="kor_kino"
                    ),
                    
                ],
                [InlineKeyboardButton(text="🔍Nom orqali qidirish...", switch_inline_query_current_chat="")]
            ],
            row_width=2
        )

    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Kino ma'lumotlarini olish
        cursor.execute("SELECT name, description, video_file_id, download_count FROM movies WHERE movie_code = ?", (movie_code,))
        movie_data = cursor.fetchone()

    if not movie_data:
        await callback_query.answer("❌ Kino topilmadi!", show_alert=True)
        return

    name, description, video_file_id, download_count = movie_data

    # Yuklashlar sonini yangilash
    new_download_count = download_count + 1
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movies SET download_count = ? WHERE movie_code = ?", (new_download_count, movie_code))
        conn.commit()

    # Videoni yuborish
    try:
        await bot.send_video(
            chat_id=callback_query.message.chat.id,
            video=video_file_id,
            caption=f"<b>{name}</b>\n\n{description}\n👁:<b>{new_download_count}</b>",
            reply_markup=inline,
            parse_mode="HTML"
        )
        
    except aiogram.utils.exceptions.WrongFileIdentifier:
        await callback_query.answer("❌ Noto'g'ri video fayli yoki ID!", show_alert=True)



@dp.callback_query_handler(lambda c: c.data.startswith("save_movie:"),state="*")
async def save_movie(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    # Callback data'dan movie_code ni olish
    movie_code = callback_query.data.split(":")[1]  # "save_movie:<movie_code>" dan movie_code ni ajratib olish

    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Kino allaqachon saqlanganligini tekshirish
        cursor.execute(
            "SELECT COUNT(*) FROM saved_movies WHERE user_id = ? AND movie_code = ?",
            (user_id, movie_code)
        )
        is_saved = cursor.fetchone()[0] > 0

        if is_saved:
            # Agar kino allaqachon saqlangan bo'lsa, foydalanuvchini xabardor qilish
            await callback_query.answer("Bu kino allaqachon saqlangan!", show_alert=True)
        else:
            # Saqlanmagan bo'lsa, bazaga qo'shish
            cursor.execute(
                "INSERT INTO saved_movies (user_id, movie_code) VALUES (?, ?)",
                (user_id, movie_code)
            )
            conn.commit()

            await callback_query.answer("✅Kino muvaffaqiyatli saqlandi!", show_alert=True)

# "Saqlanganlar" tugmasi uchun callback handler
@dp.callback_query_handler(lambda c: c.data == "kor_kino",state="*")
async def show_saved_movies(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    savekb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙Bosh sahifa", callback_data="cancel")]
        ],row_width=2
    )
    # Fetch saved movies for the user
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT m.name, m.description, m.video_file_id, m.movie_code "
            "FROM saved_movies s "
            "JOIN movies m ON s.movie_code = m.movie_code "
            "WHERE s.user_id = ?",
            (user_id,)
        )
        saved_movies = cursor.fetchall()

    if not saved_movies:
        try:
            await callback_query.message.edit_text("❌ Siz hali kino saqlamadingiz.",reply_markup=savekb)
        except aiogram.utils.exceptions.BadRequest as e:
            if "message to edit" in str(e):
                await callback_query.answer("Xatolik: Xabarni tahrir qilib bo'lmaydi, yangi xabar yuboriladi.")
                await callback_query.message.reply("❌ Siz hali kino saqlamadingiz.",reply_markup=savekb)
        return

    # Prepare the list of movies with numbers
    movie_list = "\n".join(
        [f"{idx + 1}. {name}" for idx, (name, _, _, _) in enumerate(saved_movies)]
    )

    # Prepare inline buttons for selecting movies
    keyboard = InlineKeyboardMarkup(row_width=5)
    for idx, (_, _, _, movie_code) in enumerate(saved_movies):
        keyboard.insert(InlineKeyboardButton(text=str(idx + 1), callback_data=f"select_movie:{movie_code}"))

    # Add a cancel button
    keyboard.add(InlineKeyboardButton(text="🔙Bosh sahifa", callback_data="cancel"))
    keyboard.add(InlineKeyboardButton(text="Tozalash 🗑", callback_data="clear_saved_movies"))

    try:
        # Send or edit the message
        await callback_query.message.edit_text(
            f"🎥 Saqlangan kinolar:\n\n{movie_list}\n\nRaqamni tanlang:",
            reply_markup=keyboard
        )
    except aiogram.utils.exceptions.BadRequest as e:
        if "message to edit" in str(e):
            # Send a new message if editing fails
            await callback_query.message.reply(
                f"🎥 Saqlangan kinolar:\n\n{movie_list}\n\nRaqamni tanlang:",
                reply_markup=keyboard
            )

# Callback handler for selecting a movie by number
@dp.callback_query_handler(lambda c: c.data.startswith("select_movie:"),state="*")
async def send_selected_movie(callback_query: types.CallbackQuery):
    movie_code = callback_query.data.split(":")[1]  # Extract movie code
    inline = InlineKeyboardMarkup(
        inline_keyboard=[ 
            [
                InlineKeyboardButton(
                    text="Do'stlarga yuborish",
                    switch_inline_query=f"{movie_code}"  # movie_code ni yuborish
                ),
                InlineKeyboardButton(
                    text="📥 Saqlash", callback_data=f"save_movie:{movie_code}"  # Callbackda movie_codeni berish
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛒 Saqlanganlar", callback_data="kor_kino"
                )
                
            ],
            [
                InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat="")
            ]
        ],
        row_width=2
    )

    # Fetch movie details from the database
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, video_file_id, download_count FROM movies WHERE movie_code = ?", (movie_code,))
        movie_data = cursor.fetchone()

    if not movie_data:
        await callback_query.answer("❌ Kino topilmadi yoki noto'g'ri ID.", show_alert=True)
        return

    name, description, video_file_id, download_count = movie_data

    if not video_file_id:
        await callback_query.answer("❌ Video fayli topilmadi yoki noto'g'ri ID.", show_alert=True)
        return

    description = description or "Tavsif mavjud emas."

    # Update download count (increase by 1)
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE movies SET download_count = download_count + 1 WHERE movie_code = ?", (movie_code,))
        conn.commit()

    # Send the selected movie
    try:
        await bot.send_video(
            chat_id=callback_query.message.chat.id,
            video=video_file_id,
            caption=f"<b>{name}</b>\n\n{description}\n👁:<b>{download_count + 1}</b>",  # Show updated download count
            reply_markup=inline,
            parse_mode="HTML"
        )
        await callback_query.answer("✅ Kino yuborildi!")
    except aiogram.utils.exceptions.WrongFileIdentifier:
        await callback_query.answer("❌ Noto'g'ri video fayli yoki ID.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "clear_saved_movies",state="*")
async def clear_saved_movies(callback_query: types.CallbackQuery):
    savekb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙Bosh sahifa", callback_data="cancel")]
        ],row_width=2
    )
    user_id = callback_query.from_user.id

    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()

        # Foydalanuvchining barcha saqlangan kinolarini o'chirish
        cursor.execute("DELETE FROM saved_movies WHERE user_id = ?", (user_id,))
        conn.commit()

    await callback_query.answer("Barcha saqlangan kinolar o'chirildi!", show_alert=True)

    # Foydalanuvchiga xabar yuborish
    await callback_query.message.edit_text(
        "Saqlangan kinolar ro'yxati tozalandi! 🎉",
        reply_markup=savekb
    )

# Cancel button handler
@dp.callback_query_handler(lambda c: c.data == "cancel",state="*")
async def cancel_action(callback_query: types.CallbackQuery,state:FSMContext):
    
    kanalim = InlineKeyboardMarkup(
             inline_keyboard=[
                [InlineKeyboardButton(text="🎥 Top Filmlar Kanali", url="https://t.me/+uqrl9b1_rPIyOTQy"),
                 InlineKeyboardButton(text="🗒 Kategoriya",callback_data="name_search")],
                [InlineKeyboardButton(text="🔍Nom orqali qidirish...", switch_inline_query_current_chat=""),
                 InlineKeyboardButton(text="Top 10 Filmlar", callback_data="top_movies")],
                [InlineKeyboardButton(
                        text="🛒 Saqlanganlar", callback_data="kor_kino"
                    ),
                    InlineKeyboardButton(
                        text="🎲Random", callback_data="random")
                        ],
                [InlineKeyboardButton("Kino so'rash | Savol yoki Taklif ", callback_data=f"send_suggestion_")]  
            ],row_width=2
        )
    InlineKeyboardButton(text="🗒 Kategoriya",callback_data="name_search")
    await callback_query.message.edit_text("Kino kerakmi? \n<i>Kino kodini botga jonating!</i>",parse_mode="HTML",reply_markup=kanalim)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'name_search',state="*")
async def kodlik_callback(call: types.CallbackQuery,state:FSMContext):
    await call.answer("❌ Hozirda bu bo'lim mavjud emas! Kino kerak bo‘lsa, botga kodini jo‘nating!", show_alert=True)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'kodlik',state="*")
async def kodlik_callback(call: types.CallbackQuery,state:FSMContext):
    await call.answer("🎬 Kino kerak bo‘lsa, botga kodini jo‘nating!", show_alert=True)
    await state.finish()

# Dasturni ishga tushurish
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
