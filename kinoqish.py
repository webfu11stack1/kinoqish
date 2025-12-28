import shutil
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, InputTextMessageContent, InlineQueryResultArticle
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.inline_keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, MessageToForwardNotFound, RetryAfter
import asyncio
import hashlib
import os

# Logging sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    
    # userid jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS userid (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        status TEXT DEFAULT 'active',
        joined_date TEXT DEFAULT CURRENT_DATE,
        last_active TEXT DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    
    # Kanal jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channel (
        id INTEGER PRIMARY KEY,
        channel_id TEXT,
        channel_url TEXT
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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        video_file_id TEXT,
        movie_code INTEGER UNIQUE,
        download_count INTEGER DEFAULT 0,
        added_date TEXT DEFAULT CURRENT_DATE
    )
    ''')
    
    # Saqlangan filmlar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_movies (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        movie_code INTEGER,
        saved_date TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_code) REFERENCES movies(movie_code) ON DELETE CASCADE
    )
    ''')
    
    # Premium foydalanuvchilar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS premium_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        full_name TEXT,
        start_date TEXT,
        end_date TEXT,
        amount INTEGER DEFAULT 12000,
        status TEXT DEFAULT 'active'
    )
    ''')
    
    # Statistikalar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        new_users INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0,
        movies_downloaded INTEGER DEFAULT 0,
        premium_sales INTEGER DEFAULT 0,
        daily_income INTEGER DEFAULT 0
    )
    ''')
    
    # Download log jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS download_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_code INTEGER,
        download_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Token
TOKEN = "8565115606:AAHIQUz8ibmr72AaMvesdo4Jb4fvIjL78QQ"
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Global o'zgaruvchilar
ZAYAF_KANAL = []
ADMIN_ID = 1996936737

# FSM holatlari
class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()

class SuggestionStates(StatesGroup):
    waiting_for_suggestion = State()

class AddMovieStates(StatesGroup):
    name = State()
    description = State()
    code = State()
    video = State()

# Yordamchi funksiyalar
def update_user_activity(user_id):
    """Foydalanuvchi faolligini yangilash"""
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE userid SET last_active = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def log_download(user_id, movie_code):
    """Yuklanishlar logini saqlash"""
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO download_log (user_id, movie_code) 
        VALUES (?, ?)
    """, (user_id, movie_code))
    
    # Kunlik statistika
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT OR IGNORE INTO statistics (date) VALUES (?)
    """, (today,))
    cursor.execute("""
        UPDATE statistics SET movies_downloaded = movies_downloaded + 1 
        WHERE date = ?
    """, (today,))
    
    conn.commit()
    conn.close()

def get_statistics():
    """To'liq statistika olish"""
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    
    # Umumiy foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM userid")
    total_users = cursor.fetchone()[0]
    
    # Faol foydalanuvchilar (oxirgi 7 kun ichida)
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) FROM download_log 
        WHERE download_date >= ?
    """, (week_ago,))
    active_users = cursor.fetchone()[0]
    
    # Nofaol foydalanuvchilar
    inactive_users = total_users - active_users
    
    # Kunlik yangi foydalanuvchilar
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(*) FROM userid 
        WHERE DATE(joined_date) = ?
    """, (today,))
    daily_new = cursor.fetchone()[0]
    
    # Haftalik yangi foydalanuvchilar
    week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(*) FROM userid 
        WHERE joined_date >= ?
    """, (week_start,))
    weekly_new = cursor.fetchone()[0]
    
    # Oylik yangi foydalanuvchilar
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(*) FROM userid 
        WHERE joined_date >= ?
    """, (month_start,))
    monthly_new = cursor.fetchone()[0]
    
    # Premium foydalanuvchilar
    cursor.execute("SELECT COUNT(*) FROM premium_users WHERE status = 'active'")
    premium_users = cursor.fetchone()[0]
    
    # Kunlik daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE DATE(start_date) = ? AND status = 'active'
    """, (today,))
    daily_income = cursor.fetchone()[0]
    
    # Oylik daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE strftime('%Y-%m', start_date) = strftime('%Y-%m', 'now') 
        AND status = 'active'
    """,)
    monthly_income = cursor.fetchone()[0]
    
    # Yuklangan filmlar
    cursor.execute("SELECT SUM(download_count) FROM movies")
    total_downloads = cursor.fetchone()[0] or 0
    
    # Kunlik yuklanganlar
    cursor.execute("""
        SELECT COUNT(*) FROM download_log 
        WHERE DATE(download_date) = ?
    """, (today,))
    daily_downloads = cursor.fetchone()[0]
    
    # Haftalik yuklanganlar
    cursor.execute("""
        SELECT COUNT(*) FROM download_log 
        WHERE download_date >= ?
    """, (week_start,))
    weekly_downloads = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'daily_new': daily_new,
        'weekly_new': weekly_new,
        'monthly_new': monthly_new,
        'premium_users': premium_users,
        'daily_income': daily_income,
        'monthly_income': monthly_income,
        'total_downloads': total_downloads,
        'daily_downloads': daily_downloads,
        'weekly_downloads': weekly_downloads
    }

async def search_data(query):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()

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

    results = []
    for row in rows:
        name, description, file_id, movie_code, download_count = row

        if file_id:
            results.append({
                "name": name,
                "description": description,
                "file_id": file_id,
                "movie_code": movie_code,
                "download_count": download_count
            })
        else:
            logger.warning(f"Bo'sh file_id topildi: {row}")

    if not results:
        logger.info("Hech qanday natija topilmadi!")

    return results

def add_movie_to_db(name, description, video_file_id, movie_code):
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO movies (name, description, video_file_id, movie_code)
            VALUES (?, ?, ?, ?)
        ''', (name, description, video_file_id, movie_code))
        conn.commit()

def is_premium(user_id):
    """Premium tekshirish"""
    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT end_date FROM premium_users 
        WHERE user_id = ? AND status = 'active'
    """, (user_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return False

    try:
        end_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M")
        now = datetime.now()
        
        if now > end_date:
            cursor.execute("""
                UPDATE premium_users SET status = 'expired' 
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            conn.close()
            return False
            
        conn.close()
        return True
    except:
        conn.close()
        return False

# Komandalar
@dp.message_handler(commands=["help"], state="*")
async def help_command(message: types.Message, state: FSMContext):
    await message.answer(
        "<b>Botni ishga tushirish - /start\n"
        "Admin bilan bog'lanish - @python_chi\n"
        "Premium obuna - /premium\n"
        "Statistika - /stats</b>", 
        parse_mode="html"
    )
    await state.finish()

@dp.message_handler(commands=["stats"], state="*")
async def stats_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        # Adminlar ro'yxatini tekshirish
        conn = sqlite3.connect('kinoqish.db')
        cursor = conn.cursor()
        cursor.execute("SELECT admin_id FROM admins")
        admin_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if message.from_user.id not in admin_ids:
            await message.answer("⛔ Sizda bu amalni bajarish huquqi yo'q!")
            return
    
    stats = get_statistics()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    text = f"""
📊 <b>TO'LIQ STATISTIKA</b>
⏰ Vaqt: <b>{now}</b>

👥 <b>Foydalanuvchilar:</b>
• Umumiy: <b>{stats['total_users']}</b>
• Faol (7 kun): <b>{stats['active_users']}</b>
• Nofaol: <b>{stats['inactive_users']}</b>
• Premium: <b>{stats['premium_users']}</b>

📈 <b>O'sish:</b>
• Bugun: <b>{stats['daily_new']}</b>
• 7 kun: <b>{stats['weekly_new']}</b>
• Oylik: <b>{stats['monthly_new']}</b>

🎬 <b>Filmlar:</b>
• Yuklanganlar (umumiy): <b>{stats['total_downloads']}</b>
• Bugun yuklangan: <b>{stats['daily_downloads']}</b>
• Haftalik yuklangan: <b>{stats['weekly_downloads']}</b>

💰 <b>Daromad:</b>
• Bugungi: <b>{stats['daily_income']:,} so'm</b>
• Oylik: <b>{stats['monthly_income']:,} so'm</b>
    """
    
    await message.answer(text, parse_mode="HTML")

@dp.message_handler(commands=["panel"], state="*")
async def panel(message: types.Message, state: FSMContext):
    mes_id = message.from_user.id
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admins")
    admin_user_ids = [admin[0] for admin in cursor.fetchall()]
    conn.close()

    if mes_id in admin_user_ids or mes_id == ADMIN_ID:
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

# Premium boshqaruv
@dp.message_handler(text="💎Premium boshqaruvi", state="*")
async def premium_menu(message: types.Message, state: FSMContext):
    markup = ReplyKeyboardMarkup(
        keyboard=[
            ["➕ID orqali premium qo‘shish", "📋 Premiumlar ro‘yxati"],
            ["🗑 ID orqali premiumni o‘chirish", "💰Daromad statistikasi"],
            ["⬅️ Orqaga"]
        ],
        resize_keyboard=True
    )
    await message.answer("💎 Premium foydalanuvchilarni boshqarish menyusi:", reply_markup=markup)
    await state.set_state("premium_menu")

@dp.message_handler(text="➕ID orqali premium qo‘shish", state="*")
async def ask_user_id(message: types.Message, state: FSMContext):
    await message.answer("👤 Premiumga qo‘shmoqchi bo‘lgan foydalanuvchining ID raqamini kiriting:")
    await state.set_state("add_premium_id")

@dp.message_handler(state="add_premium_id")
async def add_premium_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Noto‘g‘ri ID! Raqam kiriting.")
        return

    try:
        user = await bot.get_chat(user_id)
        full_name = user.full_name
    except Exception:
        full_name = "Noma'lum foydalanuvchi"

    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)

    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO premium_users 
        (user_id, full_name, start_date, end_date, status)
        VALUES (?, ?, ?, ?, 'active')
    ''', (user_id, full_name, start_date.strftime("%Y-%m-%d %H:%M"), 
          end_date.strftime("%Y-%m-%d %H:%M")))
    
    # Daromad statistika
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT OR IGNORE INTO statistics (date) VALUES (?)
    """, (today,))
    cursor.execute("""
        UPDATE statistics SET 
        premium_sales = premium_sales + 1,
        daily_income = daily_income + 12000
        WHERE date = ?
    """, (today,))
    
    conn.commit()
    conn.close()

    await message.answer(
        f"✅ <b>{full_name}</b> (ID: <code>{user_id}</code>) premiumga qo'shildi!\n"
        f"📅 Boshlanish: <b>{start_date.strftime('%Y-%m-%d %H:%M')}</b>\n"
        f"📅 Tugash: <b>{end_date.strftime('%Y-%m-%d %H:%M')}</b>",
        parse_mode="HTML"
    )
    await state.set_state("premium_menu")

@dp.message_handler(text="💰Daromad statistikasi", state="*")
async def income_stats(message: types.Message):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    
    # Kunlik daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE DATE(start_date) = DATE('now') AND status = 'active'
    """)
    daily = cursor.fetchone()[0]
    
    # Haftalik daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE start_date >= DATE('now', '-7 days') AND status = 'active'
    """)
    weekly = cursor.fetchone()[0]
    
    # Oylik daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE strftime('%Y-%m', start_date) = strftime('%Y-%m', 'now') 
        AND status = 'active'
    """)
    monthly = cursor.fetchone()[0]
    
    # Umumiy daromad
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE status = 'active'
    """)
    total = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""
💰 <b>DAROMAD STATISTIKASI</b>

📊 Kunlik: <b>{daily:,} so'm</b>
📈 Haftalik: <b>{weekly:,} so'm</b>
📆 Oylik: <b>{monthly:,} so'm</b>
🏆 Umumiy: <b>{total:,} so'm</b>
    """
    
    await message.answer(text, parse_mode="HTML")

# Kino bo'limi
@dp.message_handler(text="🎥Kino bo'limi", state="*")
async def kinobol(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            ["📽Kino qo'shish", "⛔️Kino o'chirish"],
            ["📊Kino statistikasi", "🗄Bosh panel"]
        ], resize_keyboard=True
    )
    await message.answer('Kino bo\'limidasiz!', reply_markup=kb)
    await state.set_state("kbbol")

@dp.message_handler(text="📊Kino statistikasi", state="*")
async def movie_stats(message: types.Message):
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    
    # Eng ko'p yuklangan 10 ta film
    cursor.execute("""
        SELECT name, movie_code, download_count 
        FROM movies 
        ORDER BY download_count DESC 
        LIMIT 10
    """)
    top_movies = cursor.fetchall()
    
    # Bugun eng ko'p yuklangan
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT m.name, COUNT(dl.id) as downloads
        FROM download_log dl
        JOIN movies m ON dl.movie_code = m.movie_code
        WHERE DATE(dl.download_date) = ?
        GROUP BY dl.movie_code
        ORDER BY downloads DESC
        LIMIT 5
    """, (today,))
    today_top = cursor.fetchall()
    
    # Jami filmlar soni
    cursor.execute("SELECT COUNT(*) FROM movies")
    total_movies = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""
🎬 <b>KINO STATISTIKASI</b>

📁 Jami filmlar: <b>{total_movies}</b>

🏆 <b>TOP 10 FILMLAR:</b>
"""
    
    for i, (name, code, count) in enumerate(top_movies, 1):
        text += f"{i}. {name} - 👁 {count}\n"
    
    if today_top:
        text += "\n🔥 <b>BUGUN TOP 5:</b>\n"
        for i, (name, count) in enumerate(today_top, 1):
            text += f"{i}. {name} - {count} marta\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message_handler(text="📽Kino qo'shish", state="*")
async def start_adding_movie(message: types.Message):
    cancel_button = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_add")]]
    )
    await message.answer("Kino nomini kiriting:", reply_markup=cancel_button)
    await AddMovieStates.name.set()

@dp.message_handler(state=AddMovieStates.name, content_types=types.ContentTypes.TEXT)
async def get_movie_name(message: Message, state: FSMContext):
    movie_name = message.text.strip()
    await state.update_data(name=movie_name)
    await message.answer("Kino ta'rifini kiriting:")
    await AddMovieStates.description.set()

@dp.message_handler(state=AddMovieStates.description, content_types=types.ContentTypes.TEXT)
async def get_movie_description(message: Message, state: FSMContext):
    movie_description = message.text.strip()
    await state.update_data(description=movie_description)
    await message.answer("Kino uchun kodini kiriting:")
    await AddMovieStates.code.set()

@dp.message_handler(state=AddMovieStates.code, content_types=types.ContentTypes.TEXT)
async def get_movie_code(message: Message, state: FSMContext):
    try:
        movie_code = int(message.text.strip())
        # Kod unikal ekanligini tekshirish
        conn = sqlite3.connect('kinoqish.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies WHERE movie_code = ?", (movie_code,))
        if cursor.fetchone()[0] > 0:
            await message.answer("❌ Bu kod allaqachon mavjud. Boshqa kod kiriting:")
            return
        conn.close()
        
        await state.update_data(movie_code=movie_code)
        await message.answer("Kino uchun videoni yuboring:")
        await AddMovieStates.video.set()
    except ValueError:
        await message.answer("❌ Kod faqat raqamlardan iborat bo'lishi kerak!")

@dp.message_handler(state=AddMovieStates.video, content_types=types.ContentTypes.VIDEO)
async def get_movie_video(message: Message, state: FSMContext):
    video_id = message.video.file_id
    data = await state.get_data()
    
    add_movie_to_db(
        name=data['name'],
        description=data['description'],
        video_file_id=video_id,
        movie_code=data['movie_code']
    )
    
    await message.answer("✅ Kino muvaffaqiyatli qo'shildi!")
    await state.finish()

# Inline handler
@dp.inline_handler()
async def inline_query_handler(query: types.InlineQuery):
    query_text = query.query.strip()
    offset = int(query.offset) if query.offset else 0
    results = await search_data(query_text)
    
    inline_results = []
    for result in results[offset:offset + 50]:
        if result["file_id"]:
            unique_id = hashlib.md5(f"{result['movie_code']}{result['name']}".encode()).hexdigest()
            
            inline_results.append(
                InlineQueryResultArticle(
                    id=unique_id,
                    title=result["name"],
                    description=result["description"][:100] if len(result["description"]) > 100 else result["description"],
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
    
    next_offset = str(offset + 50) if offset + 50 < len(results) else None
    
    await bot.answer_inline_query(
        query.id,
        results=inline_results,
        cache_time=1,
        is_personal=True,
        next_offset=next_offset
    )

# Kino o'chirish
@dp.message_handler(text="⛔️Kino o'chirish", state="*")
async def dekkino(message: types.Message, state: FSMContext):
    await message.answer("Kino o'chirish uchun kodini yuboring!")
    await state.set_state("dkino")

@dp.message_handler(state="dkino")
async def dkin(message: types.Message, state: FSMContext):
    dk = message.text
    if not dk.isdigit():
        await message.answer("❌ Faqat raqam kiriting!")
        return
    
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM movies WHERE movie_code = ?", (dk,))
    movie = cursor.fetchone()
    conn.close()
    
    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi!")
        await state.finish()
        return
    
    dkk = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha", callback_data=f"del_yes_{dk}"),
             InlineKeyboardButton(text="❌ Yo'q", callback_data="del_no")]
        ], row_width=2
    )
    
    await message.answer(f"\"{movie[0]}\" kodli kino o'chirilsinmi?", reply_markup=dkk)

@dp.callback_query_handler(lambda d: d.data.startswith("del_yes_"))
async def yesdel(calmes: types.CallbackQuery, state: FSMContext):
    movie_code = calmes.data.split("_")[2]
    
    conn = sqlite3.connect("kinoqish.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM movies WHERE movie_code = ?", (movie_code,))
    movie_name = cursor.fetchone()
    
    if movie_name:
        cursor.execute("DELETE FROM movies WHERE movie_code = ?", (movie_code,))
        cursor.execute("DELETE FROM saved_movies WHERE movie_code = ?", (movie_code,))
        conn.commit()
        
        await calmes.answer(f"\"{movie_name[0]}\" kodli kino o'chirildi!✅", show_alert=True)
        await calmes.message.delete()
    else:
        await calmes.answer("Kino topilmadi!", show_alert=True)
    
    conn.close()
    await state.finish()

@dp.callback_query_handler(lambda d: d.data == "del_no")
async def nodel(calmes: types.CallbackQuery, state: FSMContext):
    await calmes.message.answer("⛔️ O'chirish bekor qilindi.")
    await calmes.message.delete()
    await state.finish()

# Xabarlar bo'limi (qisqartirildi - faqat strukturani ko'rsatish)
@dp.message_handler(text="⚪️Xabarlar bo'limi", state="*")
async def xabarbolim(message: types.Message, state: FSMContext):
    xabarlar = ReplyKeyboardMarkup(
        keyboard=[
            ["⚪️Inline Xabar", "🔗Forward xabar"],
            ["👤Userga xabar"],
            ["🖥Code xabar", "🗄Bosh panel"]
        ],
        resize_keyboard=True
    )
    await message.answer('Xabarlar bolimidasiz!', reply_markup=xabarlar)
    await state.finish()

# Start handler
@dp.message_handler(commands=["start"], state="*")
async def start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user_name_full = message.from_user.full_name
    
    # Foydalanuvchi faolligini yangilash
    update_user_activity(user_id)
    
    # Premium tekshirish
    premium_status = is_premium(user_id)
    
    # Bazaga qo'shish
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        
        # Yangi foydalanuvchini qo'shish
        cursor.execute("""
            INSERT OR IGNORE INTO userid (user_id, joined_date) 
            VALUES (?, DATE('now'))
        """, (user_id,))
        
        # Yangi foydalanuvchi bo'lsa statistika
        if cursor.rowcount > 0:
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT OR IGNORE INTO statistics (date) VALUES (?)
            """, (today,))
            cursor.execute("""
                UPDATE statistics SET new_users = new_users + 1 
                WHERE date = ?
            """, (today,))
        
        conn.commit()
    
    # Agar premium bo'lmasa, kanallarni tekshirish
    if not premium_status:
        with sqlite3.connect('kinoqish.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, channel_url FROM channel")
            channels = cursor.fetchall()
        
        unsubscribed = []
        for channel_id, _ in channels:
            try:
                status = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if status.status == "left":
                    unsubscribed.append(channel_id)
            except:
                continue
        
        if unsubscribed:
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            # Asosiy kanal
            if channels:
                for _, channel_url in channels:
                    keyboard.add(InlineKeyboardButton(text="➕ Obuna bo'lish", url=channel_url))
            
            # Zayafka kanallari
            for zayaf_url in ZAYAF_KANAL:
                keyboard.add(InlineKeyboardButton(text="➕ Obuna bo'lish", url=zayaf_url))
            
            keyboard.add(InlineKeyboardButton(text="✅ Tekshirish", url="https://t.me/kinoqishbot?start=True"))
            keyboard.add(InlineKeyboardButton(text="💎 Premium olish", callback_data="premium_info"))
            
            await message.reply(
                """❌ Kechirasiz, botimizdan foydalanish uchun kanallarga obuna bo'lishingiz kerak.\n
                ```💎 Premium obuna sotib olib, kanallarga obuna bo'lmasdan foydalanishingiz mumkin.``` """,
                reply_markup=keyboard,
                parse_mode='MARKDOWN'
            )
            return
    
    # Kino kodini tekshirish
    if len(message.text.split()) > 1:
        movie_code = message.text.split()[1]
        
        with sqlite3.connect('kinoqish.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, description, video_file_id, download_count 
                FROM movies WHERE movie_code = ?
            """, (movie_code,))
            movie_data = cursor.fetchone()
        
        if movie_data:
            name, description, video_file_id, download_count = movie_data
            
            # Yuklanish sonini yangilash va log qilish
            new_count = download_count + 1
            with sqlite3.connect('kinoqish.db') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE movies SET download_count = ? 
                    WHERE movie_code = ?
                """, (new_count, movie_code))
                log_download(user_id, movie_code)
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
                caption=f"<b>{name}</b>\n\n{description}\n👁:<b>{new_count}</b>",
                reply_markup=inline,
                parse_mode="HTML"
            )
            return
    
    # Asosiy menyu
    kanalim = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎥 Top Filmlar Kanali", url="https://t.me/+SM0BNsff0QtmMDUy"),
             InlineKeyboardButton(text="🗒 Kategoriya", callback_data="name_search")],
            [InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat=""),
             InlineKeyboardButton(text="Top 10 Filmlar", callback_data="top_movies")],
            [InlineKeyboardButton(text="🛒 Saqlanganlar", callback_data="kor_kino"),
             InlineKeyboardButton(text="🎲Random", callback_data="random")],
            [InlineKeyboardButton("Kino so'rash | Savol yoki Taklif ", callback_data="send_suggestion_")]
        ],
        row_width=2
    )
    
    welcome_text = f"Assalomu alaykum, {user_name_full}!\n\n"
    if premium_status:
        welcome_text += "💎 Siz premium foydalanuvchisiz!\n"
    welcome_text += "Kino kodini yuboring yoki qidiring ✍️"
    
    await message.answer(welcome_text, reply_markup=kanalim)

# Export users
async def export_users():
    conn = sqlite3.connect('kinoqish.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM userid')
    user_ids = cursor.fetchall()
    conn.close()
    
    with open('user_ids.txt', 'w', encoding='utf-8') as file:
        for user_id in user_ids:
            file.write(str(user_id[0]) + '\n')

@dp.message_handler(text='📑Users', state="*")
async def export_users_command(message: types.Message, state: FSMContext):
    await export_users()
    with open('user_ids.txt', 'rb') as file:
        await message.answer_document(file)
    await state.finish()

@dp.message_handler(text='📑Baza', state="*")
async def export_db_command(message: types.Message, state: FSMContext):
    shutil.copy('kinoqish.db', 'database_backup.db')
    with open('database_backup.db', 'rb') as file:
        await message.answer_document(file)
    await state.finish()

# Premium buy
@dp.callback_query_handler(lambda c: c.data == "buy_premium", state="*")
async def buy_premium(callback_query: types.CallbackQuery):
    premium_text = """
💎 <b>Premium obuna</b>

🕐 Muddati: <b>1 oy</b>
💰 Narxi: <b>12 000 so'm</b>

━━━━━━━━━━━━━━━━━━
👤 <b>To'lov qabul qiluvchi:</b>
   Asadbek Rahmonov

💳 <b>Karta raqami:</b>
   <code>9860 0121 2777 4144</code>
━━━━━━━━━━━━━━━━━━

✅ To'lovni amalga oshirgandan so'ng <b>chek rasmini shu yerga yuboring.</b>

⚠️ <i>Faqat to'lovni qilgan shaxsning cheki qabul qilinadi!</i>
    """
    
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_back")
    )
    
    await callback_query.message.edit_text(premium_text, parse_mode="HTML", reply_markup=markup)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "premium_back")
async def premium_back(callback_query: types.CallbackQuery):
    await premium_info(callback_query)

# Qolgan callback handlerlar (qisqartirildi)
@dp.callback_query_handler(lambda c: c.data == "random", state="*")
async def send_random_movie(callback_query: types.CallbackQuery):
    with sqlite3.connect('kinoqish.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, video_file_id, movie_code, download_count FROM movies ORDER BY RANDOM() LIMIT 1")
        movie = cursor.fetchone()
        
        if movie:
            name, description, video_file_id, movie_code, download_count = movie
            new_download_count = download_count + 1
            
            cursor.execute(
                "UPDATE movies SET download_count = ? WHERE movie_code = ?",
                (new_download_count, movie_code)
            )
            log_download(callback_query.from_user.id, movie_code)
            conn.commit()
            
            inline = InlineKeyboardMarkup(
                inline_keyboard=[ 
                    [
                        InlineKeyboardButton(text="Do'stlarga yuborish", switch_inline_query=f"{movie_code}"),
                        InlineKeyboardButton(text="📥 Saqlash", callback_data=f"save_movie:{movie_code}")
                    ],
                    [
                        InlineKeyboardButton(text="🛒 Saqlanganlar", callback_data="kor_kino"),
                        InlineKeyboardButton(text="🎲Random", callback_data="random")
                    ],
                    [
                        InlineKeyboardButton(text="🔍Kino qidirish...", switch_inline_query_current_chat="")
                    ]
                ],
                row_width=2
            )
            
            await bot.send_video(
                chat_id=callback_query.from_user.id,
                video=video_file_id,
                caption=f"🎬 **{name}**\n\n{description}\n👁️: <b>{new_download_count}</b>",
                reply_markup=inline,
                parse_mode="HTML"
            )
            await callback_query.message.delete()
        else:
            await callback_query.answer("Hozircha kinolar bazada yo'q.", show_alert=True)
    
    await callback_query.answer()

# Orqaga qaytish handlerlari
@dp.message_handler(text="⬅️ Orqaga", state="premium_menu")
async def back_to_panel(message: types.Message, state: FSMContext):
    await panel(message, state)

@dp.message_handler(text="🗄Bosh panel", state="*")
async def boshpanel(message: types.Message, state: FSMContext):
    await panel(message, state)
    await state.finish()

# Dasturni ishga tushurish
if __name__ == '__main__':
    logger.info("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)