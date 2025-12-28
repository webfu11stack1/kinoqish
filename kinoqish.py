import shutil
import sqlite3
import logging
import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, InputTextMessageContent, InlineQueryResultArticle, InputFile
from aiogram.types.reply_keyboard import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types.inline_keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, MessageToForwardNotFound, RetryAfter, BadRequest

# Logging sozlash
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== MA'LUMOTLAR BAZASI SOZLASH ====================
def init_db():
    """Ma'lumotlar bazasini yaratish va sozlash"""
    conn = sqlite3.connect('kinosaroy1bot.db')
    cursor = conn.cursor()
    
    # userid jadvali - barcha foydalanuvchilar
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS userid (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        status TEXT DEFAULT 'active',
        joined_date DATE DEFAULT CURRENT_DATE,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_premium INTEGER DEFAULT 0,
        premium_until DATE
    )
    ''')
    
    # Kanallar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT UNIQUE,
        channel_url TEXT,
        channel_name TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Adminlar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER UNIQUE,
        admin_name TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        permissions TEXT DEFAULT 'all'
    )
    ''')
    
    # Filmlar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        video_file_id TEXT,
        movie_code INTEGER UNIQUE,
        download_count INTEGER DEFAULT 0,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT DEFAULT 'Boshqa',
        added_by INTEGER,
        size_mb REAL DEFAULT 0
    )
    ''')
    
    # Saqlangan filmlar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS saved_movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id INTEGER,
        saved_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
    )
    ''')
    
    # Premium foydalanuvchilar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS premium_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        full_name TEXT,
        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_date TIMESTAMP,
        amount INTEGER DEFAULT 12000,
        status TEXT DEFAULT 'active',
        payment_method TEXT,
        transaction_id TEXT
    )
    ''')
    
    # Yuklanishlar logi
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS download_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id INTEGER,
        download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        device_info TEXT
    )
    ''')
    
    # Kunlik statistika
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE UNIQUE DEFAULT CURRENT_DATE,
        new_users INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0,
        movies_downloaded INTEGER DEFAULT 0,
        premium_sales INTEGER DEFAULT 0,
        total_income INTEGER DEFAULT 0,
        messages_sent INTEGER DEFAULT 0
    )
    ''')
    
    # Xabarlar logi
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS message_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        message_type TEXT,
        sent_to_count INTEGER,
        success_count INTEGER,
        fail_count INTEGER,
        sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        message_text TEXT
    )
    ''')
    
    # Zayafka kanallari
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS zayafka_channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_url TEXT UNIQUE,
        channel_name TEXT,
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Indexlar yaratish
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_userid_user_id ON userid(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_movies_movie_code ON movies(movie_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_logs_date ON download_logs(download_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium_users_end_date ON premium_users(end_date)')
    
    conn.commit()
    conn.close()
    logger.info("Ma'lumotlar bazasi yaratildi/yangilandi")

# ==================== KONFIGURATSIYA ====================
TOKEN = "8565115606:AAHIQUz8ibmr72AaMvesdo4Jb4fvIjL78QQ"
ADMIN_ID = 1996936737
CHANNEL_ID_PRM = -1003327939504  # Premium tasdiqlash kanali

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Global o'zgaruvchilar
ZAYAF_KANAL = []

# ==================== FSM HOLATLARI ====================
class AddMovieStates(StatesGroup):
    name = State()
    description = State()
    code = State()
    video = State()

class AdminMessageStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()

class SuggestionStates(StatesGroup):
    waiting_for_suggestion = State()

class PremiumAddStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_days = State()

class ChannelAddStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_url = State()

class ZayafkaStates(StatesGroup):
    waiting_for_zayafka_url = State()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def get_db_connection():
    """Ma'lumotlar bazasi ulanishini olish"""
    conn = sqlite3.connect('kinosaroy1bot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def update_daily_stats():
    """Kunlik statistika yangilash"""
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute('''
        INSERT OR IGNORE INTO daily_stats (date) VALUES (?)
    ''', (today,))
    
    # Faol foydalanuvchilar (bugun harakat qilgan)
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) FROM download_logs 
        WHERE DATE(download_date) = ?
    ''', (today,))
    active_users = cursor.fetchone()[0]
    
    # Yangi foydalanuvchilar
    cursor.execute('''
        SELECT COUNT(*) FROM userid WHERE DATE(joined_date) = ?
    ''', (today,))
    new_users = cursor.fetchone()[0]
    
    # Yuklangan filmlar
    cursor.execute('''
        SELECT COUNT(*) FROM download_logs WHERE DATE(download_date) = ?
    ''', (today,))
    movies_downloaded = cursor.fetchone()[0]
    
    # Premium sotuvlar
    cursor.execute('''
        SELECT COUNT(*) FROM premium_users WHERE DATE(start_date) = ? AND status = 'active'
    ''', (today,))
    premium_sales = cursor.fetchone()[0]
    
    # Daromad
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) FROM premium_users 
        WHERE DATE(start_date) = ? AND status = 'active'
    ''', (today,))
    total_income = cursor.fetchone()[0]
    
    cursor.execute('''
        UPDATE daily_stats SET 
        new_users = ?,
        active_users = ?,
        movies_downloaded = ?,
        premium_sales = ?,
        total_income = ?
        WHERE date = ?
    ''', (new_users, active_users, movies_downloaded, premium_sales, total_income, today))
    
    conn.commit()
    conn.close()

def log_download(user_id, movie_id):
    """Yuklanishni log qilish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO download_logs (user_id, movie_id) VALUES (?, ?)
    ''', (user_id, movie_id))
    
    # Filmning yuklanish sonini yangilash
    cursor.execute('''
        UPDATE movies SET download_count = download_count + 1 WHERE id = ?
    ''', (movie_id,))
    
    conn.commit()
    conn.close()
    update_daily_stats()

def update_user_activity(user_id, username=None, full_name=None):
    """Foydalanuvchi faolligini yangilash"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO userid (user_id, username, full_name, last_active) 
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET 
        last_active = CURRENT_TIMESTAMP,
        username = COALESCE(?, username),
        full_name = COALESCE(?, full_name)
    ''', (user_id, username, full_name, username, full_name))
    
    conn.commit()
    conn.close()

def is_user_admin(user_id):
    """Foydalanuvchi admin ekanligini tekshirish"""
    if user_id == ADMIN_ID:
        return True
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None

def is_user_premium(user_id):
    """Foydalanuvchi premium ekanligini tekshirish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT end_date FROM premium_users 
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return False
    
    end_date = datetime.strptime(result['end_date'], "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    
    if now > end_date:
        cursor.execute("UPDATE premium_users SET status = 'expired' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return False
    
    conn.close()
    return True

def get_user_channels(user_id):
    """Foydalanuvchi obuna bo'lishi kerak bo'lgan kanallarni olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_url FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    return [dict(channel) for channel in channels]

def get_zayafka_channels():
    """Zayafka kanallarini olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_url FROM zayafka_channels")
    channels = cursor.fetchall()
    conn.close()
    
    return [channel['channel_url'] for channel in channels]

def add_zayafka_channel(channel_url, channel_name=""):
    """Zayafka kanalini qo'shish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO zayafka_channels (channel_url, channel_name) 
            VALUES (?, ?)
        ''', (channel_url, channel_name))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Zayafka kanalini qo'shishda xatolik: {e}")
        return False
    finally:
        conn.close()

def remove_zayafka_channel(channel_url):
    """Zayafka kanalini o'chirish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM zayafka_channels WHERE channel_url = ?", (channel_url,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Zayafka kanalini o'chirishda xatolik: {e}")
        return False
    finally:
        conn.close()

def get_comprehensive_stats():
    """To'liq statistika olish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Umumiy foydalanuvchilar
    cursor.execute("SELECT COUNT(*) as count FROM userid")
    stats['total_users'] = cursor.fetchone()['count']
    
    # Faol foydalanuvchilar (oxirgi 7 kun)
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) as count FROM download_logs 
        WHERE download_date >= ?
    ''', (week_ago,))
    stats['active_users'] = cursor.fetchone()['count']
    
    # Premium foydalanuvchilar
    cursor.execute("SELECT COUNT(*) as count FROM premium_users WHERE status = 'active'")
    stats['premium_users'] = cursor.fetchone()['count']
    
    # Bugungi statistikalar
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT new_users, active_users, movies_downloaded, premium_sales, total_income 
        FROM daily_stats WHERE date = ?
    ''', (today,))
    daily = cursor.fetchone()
    
    if daily:
        stats['daily_new_users'] = daily['new_users']
        stats['daily_active_users'] = daily['active_users']
        stats['daily_downloads'] = daily['movies_downloaded']
        stats['daily_premium_sales'] = daily['premium_sales']
        stats['daily_income'] = daily['total_income']
    else:
        stats.update({
            'daily_new_users': 0,
            'daily_active_users': 0,
            'daily_downloads': 0,
            'daily_premium_sales': 0,
            'daily_income': 0
        })
    
    # Haftalik o'sish
    cursor.execute('''
        SELECT COUNT(*) as count FROM userid WHERE joined_date >= ?
    ''', (week_ago,))
    stats['weekly_new_users'] = cursor.fetchone()['count']
    
    # Oylik o'sish
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*) as count FROM userid WHERE joined_date >= ?
    ''', (month_start,))
    stats['monthly_new_users'] = cursor.fetchone()['count']
    
    # Filmlar statistikasi
    cursor.execute("SELECT COUNT(*) as count FROM movies")
    stats['total_movies'] = cursor.fetchone()['count']
    
    cursor.execute("SELECT SUM(download_count) as count FROM movies")
    stats['total_downloads'] = cursor.fetchone()['count'] or 0
    
    # Bugun eng ko'p yuklangan filmlar
    cursor.execute('''
        SELECT m.name, COUNT(dl.id) as downloads
        FROM download_logs dl
        JOIN movies m ON dl.movie_id = m.id
        WHERE DATE(dl.download_date) = ?
        GROUP BY dl.movie_id
        ORDER BY downloads DESC
        LIMIT 5
    ''', (today,))
    stats['today_top_movies'] = cursor.fetchall()
    
    # Daromad statistikasi
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) as total FROM premium_users 
        WHERE status = 'active'
    ''')
    stats['total_income'] = cursor.fetchone()['total']
    
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) as weekly FROM premium_users 
        WHERE start_date >= ? AND status = 'active'
    ''', (week_ago,))
    stats['weekly_income'] = cursor.fetchone()['weekly']
    
    cursor.execute('''
        SELECT COALESCE(SUM(amount), 0) as monthly FROM premium_users 
        WHERE start_date >= ? AND status = 'active'
    ''', (month_start,))
    stats['monthly_income'] = cursor.fetchone()['monthly']
    
    conn.close()
    return stats

def export_users_to_file():
    """Foydalanuvchilarni faylga eksport qilish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, username, full_name, joined_date, last_active, 
               CASE WHEN is_premium = 1 THEN 'Premium' ELSE 'Oddiy' END as status
        FROM userid
        ORDER BY joined_date DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()
    
    filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Sarlavha
        f.write("ID,Username,Ism,Qo'shilgan sana,Oxirgi faollik,Status\n")
        
        # Ma'lumotlar
        for user in users:
            f.write(f"{user['user_id']},{user['username'] or ''},{user['full_name'] or ''},"
                   f"{user['joined_date']},{user['last_active']},{user['status']}\n")
    
    return filename

# ==================== START KOMANDASI ====================
@dp.message_handler(commands=["start"], state="*")
async def start_command(message: types.Message, state: FSMContext):
    await state.finish()
    
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Foydalanuvchi ma'lumotlarini yangilash
    update_user_activity(user_id, username, full_name)
    
    # Premium tekshirish
    is_premium = is_user_premium(user_id)
    
    # Agar premium bo'lmasa, kanallarni tekshirish
    if not is_premium:
        channels = get_user_channels(user_id)
        zayafka_channels = get_zayafka_channels()
        
        unsubscribed = []
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        # Asosiy kanallar
        for channel in channels:
            try:
                status = await bot.get_chat_member(chat_id=channel['channel_id'], user_id=user_id)
                if status.status == "left":
                    unsubscribed.append(channel)
                    keyboard.add(InlineKeyboardButton(
                        text=f"➕ {channel['channel_url'].split('/')[-1]} kanal", 
                        url=channel['channel_url']
                    ))
            except Exception as e:
                logger.error(f"Kanal tekshirishda xatolik: {e}")
        
        # Zayafka kanallari
        for zayaf_url in zayafka_channels:
            keyboard.add(InlineKeyboardButton(
                text=f"➕ {zayaf_url.split('/')[-1]} kanal", 
                url=zayaf_url
            ))
        
        if unsubscribed:
            keyboard.add(InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription"))
            keyboard.add(InlineKeyboardButton(text="💎 Premium sotib olish", callback_data="premium_info"))
            
            await message.answer(
                "🤖 *KinoQish Botiga xush kelibsiz!*\n\n"
                "📺 Botdan to'liq foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
                f"💎 *Premium obuna* sotib olib, reklamasiz va cheklovlarsiz foydalanishingiz mumkin!",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
    
    # Agar kino kodi bilan kirilgan bo'lsa
    if len(message.text.split()) > 1:
        movie_code = message.text.split()[1]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, video_file_id, download_count, movie_code 
            FROM movies WHERE movie_code = ?
        ''', (movie_code,))
        
        movie = cursor.fetchone()
        
        if movie:
            # Yuklanishni log qilish
            log_download(user_id, movie['id'])
            
            inline = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📤 Do'stlarga yuborish", switch_inline_query=str(movie['movie_code'])),
                        InlineKeyboardButton(text="💾 Saqlash", callback_data=f"save_{movie['id']}")
                    ],
                    [
                        InlineKeyboardButton(text="📋 Saqlanganlar", callback_data="saved_movies"),
                        InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="random_movie")
                    ]
                ]
            )
            
            await message.answer_video(
                video=movie['video_file_id'],
                caption=f"🎬 *{movie['name']}*\n\n"
                       f"📝 {movie['description'] or 'Tavsif mavjud emas'}\n\n"
                       f"👁️ {movie['download_count'] + 1} marotaba ko'rilgan\n"
                       f"🔢 Kino kodi: `{movie['movie_code']}`",
                parse_mode="Markdown",
                reply_markup=inline
            )
        else:
            await message.answer("❌ Bunday kodli kino topilmadi!")
        
        conn.close()
        return
    
    # Asosiy menyu
    main_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Kino qidirish", switch_inline_query_current_chat=""),
                InlineKeyboardButton(text="📊 Statistika", callback_data="user_stats")
            ],
            [
                InlineKeyboardButton(text="💾 Saqlanganlar", callback_data="saved_movies"),
                InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="random_movie")
            ],
            [
                InlineKeyboardButton(text="🏆 Top 10 filmlar", callback_data="top_movies"),
                InlineKeyboardButton(text="📢 Bizning kanal", url="https://t.me/+uqrl9b1_rPIyOTQy")
            ],
            [
                InlineKeyboardButton(text="💎 Premium", callback_data="premium_info"),
                InlineKeyboardButton(text="❓ Yordam", callback_data="help_info")
            ]
        ]
    )
    
    welcome_text = f"🎬 *Salom, {full_name}!*\n\n"
    
    if is_premium:
        welcome_text += "✨ *Siz Premium foydalanuvchisiz!*\n"
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT end_date FROM premium_users WHERE user_id = ?", (user_id,))
        premium_data = cursor.fetchone()
        conn.close()
        
        if premium_data:
            end_date = datetime.strptime(premium_data['end_date'], "%Y-%m-%d %H:%M:%S")
            days_left = (end_date - datetime.now()).days
            welcome_text += f"📅 Premium muddati tugashiga: *{days_left} kun*\n\n"
    
    welcome_text += ("🤖 *KinoQish Bot* - eng yangi va sara filmlar!\n\n"
                    "🔢 Kino kodini yuboring yoki 🔍 qidiruv orqali toping.\n"
                    "💎 Premium obuna - cheksiz va reklamasiz foydalanish!")
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_menu)

# ==================== ADMIN PANEL ====================
@dp.message_handler(commands=["admin", "panel"], state="*")
async def admin_panel(message: types.Message, state: FSMContext):
    if not is_user_admin(message.from_user.id):
        await message.answer("⛔ *Siz admin emassiz!*", parse_mode="Markdown")
        return
    
    await state.finish()
    
    admin_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["📊 Statistika", "📈 To'liq statistika"],
            ["👥 Foydalanuvchilar", "🎬 Filmlar"],
            ["💎 Premium boshqaruv", "📢 Kanal boshqaruv"],
            ["✉️ Xabar yuborish", "⚙️ Sozlamalar"],
            ["🔙 Asosiy menyu"]
        ],
        resize_keyboard=True,
        row_width=2
    )
    
    await message.answer(
        "🛠 *Admin paneliga xush kelibsiz!*\n\n"
        "Kerakli bo'limni tanlang:",
        parse_mode="Markdown",
        reply_markup=admin_keyboard
    )

# ==================== STATISTIKA ====================
@dp.message_handler(text="📊 Statistika")
async def show_stats(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    stats = get_comprehensive_stats()
    
    text = f"""
📊 *UMUMIY STATISTIKA*

👥 *Foydalanuvchilar:*
• Jami: {stats['total_users']:,}
• Faol (7 kun): {stats['active_users']:,}
• Premium: {stats['premium_users']:,}

📈 *Bugungi ko'rsatkichlar:*
• Yangi: {stats['daily_new_users']:,}
• Faol: {stats['daily_active_users']:,}
• Yuklangan: {stats['daily_downloads']:,}
• Premium sotuv: {stats['daily_premium_sales']:,}

🎬 *Filmlar:*
• Jami: {stats['total_movies']:,}
• Yuklangan: {stats['total_downloads']:,}

💰 *Daromad:*
• Bugun: {stats['daily_income']:,} so'm
• Hafta: {stats['weekly_income']:,} so'm
• Oylik: {stats['monthly_income']:,} so'm
• Jami: {stats['total_income']:,} so'm
    """
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(text="📈 To'liq statistika")
async def show_full_stats(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    stats = get_comprehensive_stats()
    
    text = f"""
📈 *TO'LIQ STATISTIKA*

📅 *Sana:* {datetime.now().strftime('%Y-%m-%d %H:%M')}

👤 *FOYDALANUVCHILAR STATISTIKASI*
├─ Jami: {stats['total_users']:,}
├─ Faol (7 kun): {stats['active_users']:,}
├─ Premium: {stats['premium_users']:,}
├─ Bugun qo'shilgan: {stats['daily_new_users']:,}
├─ Haftalik o'sish: {stats['weekly_new_users']:,}
└─ Oylik o'sish: {stats['monthly_new_users']:,}

🎬 *FILMLAR STATISTIKASI*
├─ Jami filmlar: {stats['total_movies']:,}
├─ Jami yuklangan: {stats['total_downloads']:,}
├─ Bugun yuklangan: {stats['daily_downloads']:,}
└─ Bugun eng mashhur filmlar:
"""
    
    if stats['today_top_movies']:
        for i, movie in enumerate(stats['today_top_movies'], 1):
            text += f"   {i}. {movie['name']} - {movie['downloads']} marta\n"
    else:
        text += "   Bugun hali film yuklanmadi\n"
    
    text += f"""
💰 *DAROMAD STATISTIKASI*
├─ Bugungi daromad: {stats['daily_income']:,} so'm
├─ Haftalik daromad: {stats['weekly_income']:,} so'm
├─ Oylik daromad: {stats['monthly_income']:,} so'm
└─ Umumiy daromad: {stats['total_income']:,} so'm

📊 *BUGUNGI FAOLIYAT*
├─ Premium sotuvlar: {stats['daily_premium_sales']:,}
└─ Premium daromad: {stats['daily_income']:,} so'm
    """
    
    await message.answer(text, parse_mode="Markdown")

# ==================== FOYDALANUVCHILAR BO'LIMI ====================
@dp.message_handler(text="👥 Foydalanuvchilar")
async def users_management(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["📥 Foydalanuvchilarni yuklab olish", "🔍 Foydalanuvchi qidirish"],
            ["📊 Faollik statistikasi", "🗑️ Noaktivlarni o'chirish"],
            ["🔙 Orqaga"]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "👥 *Foydalanuvchilar boshqaruvi*\n\n"
        "Kerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message_handler(text="📥 Foydalanuvchilarni yuklab olish")
async def export_users(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await message.answer("⏳ Foydalanuvchilar ma'lumotlari yuklanmoqda...")
    
    try:
        filename = export_users_to_file()
        
        with open(filename, 'rb') as file:
            await message.answer_document(
                document=InputFile(file, filename=filename),
                caption=f"📊 {datetime.now().strftime('%Y-%m-%d')} sanadagi foydalanuvchilar ro'yxati"
            )
        
        # Faylni o'chirish
        os.remove(filename)
        
    except Exception as e:
        logger.error(f"Foydalanuvchilarni eksport qilishda xatolik: {e}")
        await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

# ==================== FILMLAR BO'LIMI ====================
@dp.message_handler(text="🎬 Filmlar")
async def movies_management(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["🎥 Film qo'shish", "🗑️ Film o'chirish"],
            ["📊 Film statistikasi", "🔍 Film qidirish"],
            ["📈 Top filmlar", "📁 Kategoriyalar"],
            ["🔙 Orqaga"]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "🎬 *Filmlar boshqaruvi*\n\n"
        "Kerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message_handler(text="🎥 Film qo'shish")
async def add_movie_start(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await AddMovieStates.name.set()
    await message.answer(
        "🎬 *Yangi film qo'shish*\n\n"
        "1. Film nomini yuboring:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton("❌ Bekor qilish")]],
            resize_keyboard=True
        )
    )

@dp.message_handler(state=AddMovieStates.name)
async def add_movie_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.finish()
        await movies_management(message)
        return
    
    await state.update_data(name=message.text)
    await AddMovieStates.description.set()
    await message.answer("2. Film tavsifini yuboring:")

@dp.message_handler(state=AddMovieStates.description)
async def add_movie_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await AddMovieStates.code.set()
    await message.answer("3. Film kodini (raqam) yuboring:")

@dp.message_handler(state=AddMovieStates.code)
async def add_movie_code(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Film kodi faqat raqamlardan iborat bo'lishi kerak!")
        return
    
    movie_code = int(message.text)
    
    # Kod takrorlanmasligini tekshirish
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies WHERE movie_code = ?", (movie_code,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        await message.answer("❌ Bu kod allaqachon mavjud. Boshqa kod kiriting:")
        return
    conn.close()
    
    await state.update_data(code=movie_code)
    await AddMovieStates.video.set()
    await message.answer("4. Film videosini yuboring:")

@dp.message_handler(state=AddMovieStates.video, content_types=types.ContentType.VIDEO)
async def add_movie_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO movies (name, description, video_file_id, movie_code, added_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['name'], data['description'], message.video.file_id, data['code'], message.from_user.id))
        
        conn.commit()
        movie_id = cursor.lastrowid
        
        await message.answer(
            f"✅ *Film muvaffaqiyatli qo'shildi!*\n\n"
            f"🎬 Nomi: {data['name']}\n"
            f"🔢 Kodi: {data['code']}\n"
            f"📝 Tavsif: {data['description'][:100]}...\n\n"
            f"🎯 Film havolasi: `https://t.me/kinoqishbot?start={data['code']}`",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Film qo'shishda xatolik: {e}")
        await message.answer("❌ Film qo'shishda xatolik yuz berdi!")
    
    finally:
        conn.close()
        await state.finish()
        await movies_management(message)

@dp.message_handler(text="📊 Film statistikasi")
async def movies_stats(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Umumiy statistika
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(download_count) as downloads,
            AVG(download_count) as avg_downloads,
            MAX(download_count) as max_downloads
        FROM movies
    ''')
    stats = cursor.fetchone()
    
    # Eng ko'p yuklangan 5 ta film
    cursor.execute('''
        SELECT name, download_count, movie_code 
        FROM movies 
        ORDER BY download_count DESC 
        LIMIT 5
    ''')
    top_movies = cursor.fetchall()
    
    # Oxirgi qo'shilgan 5 ta film
    cursor.execute('''
        SELECT name, added_date, movie_code 
        FROM movies 
        ORDER BY id DESC 
        LIMIT 5
    ''')
    recent_movies = cursor.fetchall()
    
    conn.close()
    
    text = f"""
🎬 *FILMLAR STATISTIKASI*

📊 *Umumiy:*
├─ Jami filmlar: {stats['total']:,}
├─ Yuklanganlar: {stats['downloads']:,}
├─ O'rtacha yuklanish: {stats['avg_downloads']:.1f}
└─ Eng ko'p yuklangan: {stats['max_downloads']:,}

🏆 *TOP 5 FILMLAR:*
"""
    
    for i, movie in enumerate(top_movies, 1):
        text += f"{i}. {movie['name']} - {movie['download_count']:,} yuklangan\n"
    
    text += "\n🆕 *OXIRGI 5 FILM:*\n"
    
    for i, movie in enumerate(recent_movies, 1):
        added_date = datetime.strptime(movie['added_date'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        text += f"{i}. {movie['name']} ({added_date}) - Kod: {movie['movie_code']}\n"
    
    await message.answer(text, parse_mode="Markdown")

# ==================== PREMIUM BOSHQARUV ====================
@dp.message_handler(text="💎 Premium boshqaruv")
async def premium_management(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["➕ Premium qo'shish", "📋 Premiumlar ro'yxati"],
            ["🗑️ Premiumni o'chirish", "💰 Daromad statistikasi"],
            ["📊 Premium aktivlik", "⏳ Muddati tugaydiganlar"],
            ["🔙 Orqaga"]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "💎 *Premium boshqaruvi*\n\n"
        "Kerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message_handler(text="➕ Premium qo'shish")
async def add_premium_start(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await PremiumAddStates.waiting_for_user_id.set()
    await message.answer(
        "💎 *Premium qo'shish*\n\n"
        "1. Foydalanuvchi ID sini yuboring:",
        parse_mode="Markdown"
    )

@dp.message_handler(state=PremiumAddStates.waiting_for_user_id)
async def add_premium_user_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID faqat raqamlardan iborat bo'lishi kerak!")
        return
    
    user_id = int(message.text)
    
    try:
        user = await bot.get_chat(user_id)
        await state.update_data(user_id=user_id, user_name=user.full_name)
        
        await PremiumAddStates.waiting_for_days.set()
        await message.answer(
            f"2. *{user.full_name}* uchun premium muddatini kunlarda kiriting (masalan: 30):",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer("❌ Foydalanuvchi topilmadi yoki bot uni bloklagan!")
        await state.finish()

@dp.message_handler(state=PremiumAddStates.waiting_for_days)
async def add_premium_days(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Kunlar soni faqat raqamlardan iborat bo'lishi kerak!")
        return
    
    days = int(message.text)
    data = await state.get_data()
    
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO premium_users 
            (user_id, full_name, start_date, end_date, status)
            VALUES (?, ?, ?, ?, 'active')
        ''', (data['user_id'], data['user_name'], 
              start_date.strftime("%Y-%m-%d %H:%M:%S"),
              end_date.strftime("%Y-%m-%d %H:%M:%S")))
        
        # Foydalanuvchi ma'lumotlarini yangilash
        cursor.execute('''
            UPDATE userid SET is_premium = 1, premium_until = ?
            WHERE user_id = ?
        ''', (end_date.strftime("%Y-%m-%d"), data['user_id']))
        
        conn.commit()
        
        # Foydalanuvchiga xabar
        try:
            await bot.send_message(
                data['user_id'],
                f"🎉 *Tabriklaymiz!*\n\n"
                f"Sizga {days} kunlik Premium obuna aktivlashtirildi!\n"
                f"📅 Tugash muddati: {end_date.strftime('%d.%m.%Y')}\n\n"
                f"💎 Endi siz kanallarga obuna bo'lmagan holda botdan foydalanishingiz mumkin!",
                parse_mode="Markdown"
            )
        except:
            pass
        
        await message.answer(
            f"✅ *Premium muvaffaqiyatli qo'shildi!*\n\n"
            f"👤 Foydalanuvchi: {data['user_name']}\n"
            f"🆔 ID: {data['user_id']}\n"
            f"📅 Muddati: {days} kun\n"
            f"⏰ Tugash vaqti: {end_date.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Premium qo'shishda xatolik: {e}")
        await message.answer("❌ Premium qo'shishda xatolik yuz berdi!")
    
    finally:
        conn.close()
        await state.finish()
        await premium_management(message)

@dp.message_handler(text="📋 Premiumlar ro'yxati")
async def premium_list(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, full_name, start_date, end_date, status 
        FROM premium_users 
        ORDER BY end_date DESC
        LIMIT 50
    ''')
    
    premiums = cursor.fetchall()
    conn.close()
    
    if not premiums:
        await message.answer("ℹ️ Hozircha premium foydalanuvchilar yo'q.")
        return
    
    text = "💎 *PREMIUM FOYDALANUVCHILAR RO'YXATI*\n\n"
    
    for i, premium in enumerate(premiums, 1):
        start_date = datetime.strptime(premium['start_date'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        end_date = datetime.strptime(premium['end_date'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        days_left = (datetime.strptime(premium['end_date'], "%Y-%m-%d %H:%M:%S") - datetime.now()).days
        
        status_icon = "🟢" if premium['status'] == 'active' else "🔴"
        
        text += f"{i}. {status_icon} *{premium['full_name']}*\n"
        text += f"   🆔: `{premium['user_id']}`\n"
        text += f"   📅: {start_date} → {end_date}\n"
        text += f"   ⏳: {days_left} kun qoldi\n\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(text="💰 Daromad statistikasi")
async def income_statistics(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kunlik daromad (oxirgi 7 kun)
    cursor.execute('''
        SELECT date, total_income 
        FROM daily_stats 
        WHERE date >= DATE('now', '-7 days')
        ORDER BY date DESC
    ''')
    daily_incomes = cursor.fetchall()
    
    # Oylik daromad
    cursor.execute('''
        SELECT strftime('%Y-%m', start_date) as month, 
               COUNT(*) as sales, 
               SUM(amount) as income
        FROM premium_users 
        WHERE status = 'active'
        GROUP BY strftime('%Y-%m', start_date)
        ORDER BY month DESC
        LIMIT 6
    ''')
    monthly_incomes = cursor.fetchall()
    
    # Umumiy statistika
    cursor.execute('''
        SELECT 
            COUNT(*) as total_sales,
            SUM(amount) as total_income,
            AVG(amount) as avg_price
        FROM premium_users 
        WHERE status = 'active'
    ''')
    total_stats = cursor.fetchone()
    
    conn.close()
    
    text = "💰 *DAROMAD STATISTIKASI*\n\n"
    
    text += f"💵 *Umumiy:*\n"
    text += f"├─ Sotuvlar: {total_stats['total_sales']:,}\n"
    text += f"├─ Daromad: {total_stats['total_income']:,} so'm\n"
    text += f"└─ O'rtacha narx: {total_stats['avg_price']:,} so'm\n\n"
    
    text += "📊 *Oylik daromad:*\n"
    for income in monthly_incomes:
        month_name = datetime.strptime(income['month'], "%Y-%m").strftime("%B %Y")
        text += f"├─ {month_name}: {income['income']:,} so'm ({income['sales']} ta)\n"
    
    text += "\n📈 *Oxirgi 7 kun:*\n"
    for income in daily_incomes:
        date_str = datetime.strptime(income['date'], "%Y-%m-%d").strftime("%d.%m")
        text += f"├─ {date_str}: {income['total_income']:,} so'm\n"
    
    await message.answer(text, parse_mode="Markdown")

# ==================== KANAL BOSHQARUV ====================
@dp.message_handler(text="📢 Kanal boshqaruv")
async def channel_management(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["➕ Kanal qo'shish", "🗑️ Kanal o'chirish"],
            ["📋 Kanallar ro'yxati", "➕ Zayafka tugma"],
            ["🗑️ Zayafka o'chirish", "📋 Zayafka ro'yxati"],
            ["🔙 Orqaga"]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "📢 *Kanal boshqaruvi*\n\n"
        "Kerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message_handler(text="➕ Kanal qo'shish")
async def add_channel_start(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await ChannelAddStates.waiting_for_channel_id.set()
    await message.answer(
        "📢 *Kanal qo'shish*\n\n"
        "1. Kanal ID sini yuboring (masalan: -1001234567890):",
        parse_mode="Markdown"
    )

@dp.message_handler(state=ChannelAddStates.waiting_for_channel_id)
async def add_channel_id(message: types.Message, state: FSMContext):
    channel_id = message.text.strip()
    
    if not channel_id.startswith('-100'):
        await message.answer("❌ Noto'g'ri kanal ID formati. ID -100 bilan boshlanishi kerak.")
        return
    
    await state.update_data(channel_id=channel_id)
    await ChannelAddStates.waiting_for_channel_url.set()
    await message.answer("2. Kanal havolasini yuboring (masalan: https://t.me/kanal_nomi):")

@dp.message_handler(state=ChannelAddStates.waiting_for_channel_url)
async def add_channel_url(message: types.Message, state: FSMContext):
    channel_url = message.text.strip()
    data = await state.get_data()
    
    if not channel_url.startswith('https://t.me/'):
        await message.answer("❌ Noto'g'ri havola formati. https://t.me/ bilan boshlanishi kerak.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO channels (channel_id, channel_url)
            VALUES (?, ?)
        ''', (data['channel_id'], channel_url))
        
        conn.commit()
        
        await message.answer(
            f"✅ *Kanal muvaffaqiyatli qo'shildi!*\n\n"
            f"🆔 ID: `{data['channel_id']}`\n"
            f"🔗 Havola: {channel_url}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Kanal qo'shishda xatolik: {e}")
        await message.answer("❌ Kanal qo'shishda xatolik yuz berdi!")
    
    finally:
        conn.close()
        await state.finish()
        await channel_management(message)

@dp.message_handler(text="📋 Kanallar ro'yxati")
async def channels_list(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT channel_id, channel_url, added_date FROM channels ORDER BY added_date DESC")
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        await message.answer("ℹ️ Hozircha kanallar yo'q.")
        return
    
    text = "📢 *KANALLAR RO'YXATI*\n\n"
    
    for i, channel in enumerate(channels, 1):
        added_date = datetime.strptime(channel['added_date'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y")
        text += f"{i}. {channel['channel_url']}\n"
        text += f"   🆔: `{channel['channel_id']}`\n"
        text += f"   📅: {added_date}\n\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(text="➕ Zayafka tugma")
async def add_zayafka_start(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await ZayafkaStates.waiting_for_zayafka_url.set()
    await message.answer(
        "➕ *Zayafka kanalini qo'shish*\n\n"
        "Kanal havolasini yuboring (Telegram, Instagram yoki YouTube):",
        parse_mode="Markdown"
    )

@dp.message_handler(state=ZayafkaStates.waiting_for_zayafka_url)
async def add_zayafka_url(message: types.Message, state: FSMContext):
    channel_url = message.text.strip()
    
    # URL formatini tekshirish
    valid_domains = ['t.me', 'telegram.me', 'instagram.com', 'youtube.com', 'youtu.be']
    if not any(domain in channel_url for domain in valid_domains):
        await message.answer(
            "❌ Noto'g'ri havola formati!\n"
            "Quyidagi platformalardan havola yuboring:\n"
            "- Telegram: https://t.me/...\n"
            "- Instagram: https://instagram.com/...\n"
            "- YouTube: https://youtube.com/...\n"
        )
        return
    
    if add_zayafka_channel(channel_url):
        await message.answer(f"✅ *Zayafka kanali qo'shildi!*\n\n🔗 {channel_url}", parse_mode="Markdown")
    else:
        await message.answer("❌ Kanal qo'shishda xatolik yuz berdi!")
    
    await state.finish()
    await channel_management(message)

# ==================== XABAR YUBORISH ====================
@dp.message_handler(text="✉️ Xabar yuborish")
async def message_sending(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            ["📨 Hammaga xabar", "👤 Userga xabar"],
            ["🔗 Forward xabar", "📊 Xabar statistikasi"],
            ["🔙 Orqaga"]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "✉️ *Xabar yuborish*\n\n"
        "Kerakli amalni tanlang:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.message_handler(text="📨 Hammaga xabar")
async def broadcast_message(message: types.Message):
    if not is_user_admin(message.from_user.id):
        return
    
    await message.answer(
        "📨 *Hammaga xabar yuborish*\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm yoki video):\n\n"
        "❌ *Bekor qilish uchun:* /cancel",
        parse_mode="Markdown"
    )

@dp.message_handler(content_types=['text', 'photo', 'video'])
async def process_broadcast(message: types.Message, state: FSMContext):
    if not is_user_admin(message.from_user.id):
        return
    
    if message.text and message.text == "/cancel":
        await message.answer("❌ Xabar yuborish bekor qilindi.")
        await state.finish()
        return
    
    await message.answer("⏳ Xabar yuborilmoqda...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM userid WHERE status = 'active'")
    users = cursor.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    # Xabarni yuborish
    for user in users:
        try:
            if message.content_type == 'text':
                await bot.send_message(user['user_id'], message.text)
            elif message.content_type == 'photo':
                await bot.send_photo(user['user_id'], message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'video':
                await bot.send_video(user['user_id'], message.video.file_id, caption=message.caption)
            
            success += 1
            await asyncio.sleep(0.05)  # Anti-flood
        
        except Exception as e:
            failed += 1
    
    # Log saqlash
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO message_logs (admin_id, message_type, sent_to_count, success_count, fail_count, message_text)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (message.from_user.id, message.content_type, len(users), success, failed, 
          message.text if message.content_type == 'text' else message.caption or 'Rasm/Video'))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"✅ *Xabar yuborish yakunlandi!*\n\n"
        f"📊 Natijalar:\n"
        f"• Yuborildi: {success} ta\n"
        f"• Yuborilmadi: {failed} ta\n"
        f"• Jami: {len(users)} ta",
        parse_mode="Markdown"
    )

# ==================== INLINE HANDLER ====================
@dp.inline_handler()
async def inline_query_handler(inline_query: types.InlineQuery):
    query = inline_query.query.strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if query:
        cursor.execute('''
            SELECT name, description, movie_code, download_count 
            FROM movies 
            WHERE name LIKE ? OR movie_code LIKE ?
            ORDER BY download_count DESC
            LIMIT 50
        ''', (f'%{query}%', f'%{query}%'))
    else:
        cursor.execute('''
            SELECT name, description, movie_code, download_count 
            FROM movies 
            ORDER BY download_count DESC
            LIMIT 50
        ''')
    
    movies = cursor.fetchall()
    conn.close()
    
    results = []
    
    for movie in movies:
        results.append(
            InlineQueryResultArticle(
                id=str(movie['movie_code']),
                title=movie['name'],
                description=f"Kod: {movie['movie_code']} | Yuklangan: {movie['download_count']}",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎬 *{movie['name']}*\n\n"
                                f"{movie['description'] or 'Tavsif mavjud emas'}\n\n"
                                f"🔢 Kino kodi: `{movie['movie_code']}`\n"
                                f"👁️ {movie['download_count']} marotaba ko'rilgan\n\n"
                                f"📥 Yuklab olish uchun: /start {movie['movie_code']}",
                    parse_mode="Markdown"
                ),
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton(
                        text="📥 Yuklab olish",
                        url=f"https://t.me/kinoqishbot?start={movie['movie_code']}"
                    )
                )
            )
        )
    
    await bot.answer_inline_query(
        inline_query_id=inline_query.id,
        results=results,
        cache_time=1,
        is_personal=True
    )

# ==================== CALLBACK QUERY HANDLERLAR ====================
@dp.callback_query_handler(lambda c: c.data == "premium_info")
async def premium_info_callback(callback: CallbackQuery):
    await callback.answer()
    
    text = """
💎 *PREMIUM OBUNA*

✨ *Afzalliklari:*
• 📺 Kanallarga obunasiz foydalanish
• 🚫 Hech qanday reklama
• ⚡ Tezkor yuklab olish
• 🎬 Eng yangi filmlar
• 🔒 Maxfiylik

💰 *Narx:* 12,000 so'm / oy

💳 *To'lov usullari:*
1️⃣ Click
2️⃣ Payme
3️⃣ Bank kartasi

📞 *Bog'lanish:* @ar7_admin

👇 Premium sotib olish uchun tugmani bosing:
    """
    
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💳 Premium sotib olish", callback_data="buy_premium")
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "buy_premium")
async def buy_premium_callback(callback: CallbackQuery):
    await callback.answer()
    
    text = """
💎 *PREMIUM SOTIB OLISH*

💳 *To'lov ma'lumotlari:*
• Karta raqami: `9860 0121 2777 4144`
• Karta egasi: Asadbek Rahmonov

💰 *To'lov summasi:* 12,000 so'm

📸 *To'lov chekini* yuboring va premium obunangiz 24 soat ichida faollashtiriladi.

📞 *Aloqa:* @ar7_admin

⚠️ *Eslatma:* Faqat to'lov cheki orqali premium aktivlashtiriladi!
    """
    
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 Orqaga", callback_data="premium_info")
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

# ==================== CHEK QABUL QILISH ====================
@dp.message_handler(content_types=['photo'], state='*')
async def handle_check_photo(message: types.Message):
    """To'lov chekini qabul qilish"""
    
    # Premium haqida yuborilgan xabardan keyin chek yuborilganini tekshirish
    if not hasattr(message, 'reply_to_message') or not message.reply_to_message:
        return
    
    # Reply qilingan xabarda premium ma'lumotlari borligini tekshirish
    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if "PREMIUM SOTIB OLISH" not in reply_text:
        return
    
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Yo'q"
    photo_id = message.photo[-1].file_id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Admin kanaliga xabar yuborish
    caption = f"""
📸 *YANGI TO'LOV CHEKI*

👤 *Foydalanuvchi:*
• Ism: {user_name}
• Username: {username}
• ID: `{user_id}`

📅 *Vaqt:* {now}

💰 *Summa:* 12,000 so'm

👇 *Amallar:*
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_premium_{user_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_premium_{user_id}")
            ],
            [
                InlineKeyboardButton("💬 Javob berish", callback_data=f"reply_to_{user_id}")
            ]
        ]
    )
    
    try:
        # Admin kanaliga chekni yuborish
        await bot.send_photo(
            chat_id=CHANNEL_ID_PRM,
            photo=photo_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        # Foydalanuvchiga tasdiqlash kutilayotganligi haqida xabar
        await message.reply(
            "✅ *Chek qabul qilindi!*\n\n"
            "To'lov tekshirilmoqda. Premium obunangiz 24 soat ichida faollashtiriladi.\n\n"
            "📞 Savollar uchun: @ar7_admin",
            parse_mode="Markdown"
        )
        
        # Log saqlash
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO premium_pending 
            (user_id, user_name, username, photo_id, sent_date, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (user_id, user_name, username, photo_id, now))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Chek yuborishda xatolik: {e}")
        await message.reply("❌ Chekni yuborishda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

# ==================== PREMIUM TASDIQLASH ====================
@dp.callback_query_handler(lambda c: c.data.startswith("confirm_premium_"))
async def confirm_premium_callback(callback: CallbackQuery):
    """Premiumni tasdiqlash"""
    
    user_id = int(callback.data.split("_")[2])
    
    # Premium ma'lumotlarini bazaga qo'shish
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Foydalanuvchi ma'lumotlarini olish
        user = await bot.get_chat(user_id)
        full_name = user.full_name
        
        # Premium qo'shish
        cursor.execute('''
            INSERT OR REPLACE INTO premium_users 
            (user_id, full_name, start_date, end_date, amount, status)
            VALUES (?, ?, ?, ?, 12000, 'active')
        ''', (user_id, full_name, 
              start_date.strftime("%Y-%m-%d %H:%M:%S"),
              end_date.strftime("%Y-%m-%d %H:%M:%S")))
        
        # Foydalanuvchi ma'lumotlarini yangilash
        cursor.execute('''
            UPDATE userid SET is_premium = 1, premium_until = ?
            WHERE user_id = ?
        ''', (end_date.strftime("%Y-%m-%d"), user_id))
        
        # Pending statusini o'zgartirish
        cursor.execute('''
            UPDATE premium_pending SET status = 'confirmed', processed_date = ?
            WHERE user_id = ? AND status = 'pending'
        ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        
        # Foydalanuvchiga xabar yuborish
        try:
            success_message = await bot.send_message(
                user_id,
                f"🎉 *TABRIKLAYMIZ!*\n\n"
                f"Sizning Premium obunangiz faollashtirildi!\n\n"
                f"📅 *Boshlanish vaqti:* {start_date.strftime('%d.%m.%Y %H:%M')}\n"
                f"📅 *Tugash vaqti:* {end_date.strftime('%d.%m.%Y %H:%M')}\n"
                f"⏳ *Muddati:* 30 kun\n\n"
                f"✨ *Endi siz:*
                • Kanallarga obunasiz foydalanishingiz mumkin
                • Reklamasiz tomosha qilishingiz mumkin
                • Tezkor yuklab olishingiz mumkin\n\n"
                f"🤖 Botni qayta ishga tushiring: /start",
                parse_mode="Markdown"
            )
            
            # Javob berish tugmasi
            reply_keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("💬 Javob berish", url=f"tg://user?id={user_id}")
            )
            
        except Exception as e:
            logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")
            success_message = None
        
        # Admin xabarini yangilash
        await callback.message.edit_caption(
            caption=callback.message.caption + f"\n\n✅ *TASDIQLANDI*\nVaqt: {datetime.now().strftime('%H:%M')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton("✅ Premium faollashtirildi", callback_data="premium_confirmed"),
                        InlineKeyboardButton("💬 Javob berish", url=f"tg://user?id={user_id}")
                    ]
                ]
            ) if success_message else InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton("✅ Premium faollashtirildi", callback_data="premium_confirmed")]
                ]
            )
        )
        
        await callback.answer("✅ Premium faollashtirildi!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Premiumni tasdiqlashda xatolik: {e}")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    finally:
        conn.close()

# ==================== PREMIUM RAD ETISH ====================
@dp.callback_query_handler(lambda c: c.data.startswith("reject_premium_"))
async def reject_premium_callback(callback: CallbackQuery):
    """Premiumni rad etish"""
    
    user_id = int(callback.data.split("_")[2])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Pending statusini o'zgartirish
        cursor.execute('''
            UPDATE premium_pending SET status = 'rejected', processed_date = ?
            WHERE user_id = ? AND status = 'pending'
        ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        
        # Foydalanuvchiga xabar yuborish
        try:
            await bot.send_message(
                user_id,
                "❌ *Afsuski...*\n\n"
                "Siz yuborgan to'lov cheki tasdiqlanmadi.\n\n",
                
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Foydalanuvchiga rad etish xabarini yuborishda xatolik: {e}")
        
        # Admin xabarini yangilash
        await callback.message.edit_caption(
            caption=callback.message.caption + f"\n\n❌ *RAD ETILDI*\nVaqt: {datetime.now().strftime('%H:%M')}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton("❌ Premium rad etildi", callback_data="premium_rejected")]
                ]
            )
        )
        
        await callback.answer("❌ Premium rad etildi!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Premiumni rad etishda xatolik: {e}")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
    
    finally:
        conn.close()

# ==================== JAVOB BERISH TUGMASI ====================
@dp.callback_query_handler(lambda c: c.data.startswith("reply_to_"))
async def reply_to_user_callback(callback: CallbackQuery):
    """Foydalanuvchiga javob berish tugmasi"""
    
    user_id = int(callback.data.split("_")[2])
    
    # Admin'ga foydalanuvchi bilan suhbatlashish imkoniyatini berish
    try:
        user_info = await bot.get_chat(user_id)
        user_link = f"tg://user?id={user_id}"
        
        await callback.answer(
            f"Foydalanuvchi: {user_info.full_name}\n"
            f"ID: {user_id}\n\n"
            "Quyidagi tugma orqali foydalanuvchi bilan suhbatlashingiz mumkin:",
            show_alert=True
        )
        
        # Javob berish uchun inline tugma
        reply_keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💬 Foydalanuvchiga javob berish", url=user_link)
        )
        
        # Agar xabar edit qilish mumkin bo'lsa, tugmani qo'shamiz
        try:
            await callback.message.edit_reply_markup(reply_markup=reply_keyboard)
        except:
            await callback.message.reply(
                f"👤 *Foydalanuvchi:* {user_info.full_name}\n"
                f"🆔 *ID:* `{user_id}`\n\n"
                f"💬 Suhbatlashish uchun quyidagi tugmani bosing:",
                parse_mode="Markdown",
                reply_markup=reply_keyboard
            )
            
    except Exception as e:
        logger.error(f"Foydalanuvchi ma'lumotlarini olishda xatolik: {e}")
        await callback.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)

# ==================== PREMIUM PENDING JADVALINI YARATISH ====================
def create_premium_pending_table():
    """Premium kutayotganlar jadvalini yaratish"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_pending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            username TEXT,
            photo_id TEXT,
            sent_date TEXT,
            processed_date TEXT,
            status TEXT DEFAULT 'pending',
            admin_id INTEGER,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Premium pending jadvali yaratildi")

# ==================== PREMIUM HOLATINI TEKSHIRISH ====================
@dp.callback_query_handler(lambda c: c.data == "check_premium_status")
async def check_premium_status_callback(callback: CallbackQuery):
    """Premium holatini tekshirish"""
    
    user_id = callback.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pending statusini tekshirish
    cursor.execute('''
        SELECT status, sent_date FROM premium_pending 
        WHERE user_id = ? 
        ORDER BY sent_date DESC 
        LIMIT 1
    ''', (user_id,))
    
    pending = cursor.fetchone()
    
    # Premium statusini tekshirish
    cursor.execute('''
        SELECT end_date, status FROM premium_users 
        WHERE user_id = ?
    ''', (user_id,))
    
    premium = cursor.fetchone()
    conn.close()
    
    if premium and premium['status'] == 'active':
        end_date = datetime.strptime(premium['end_date'], "%Y-%m-%d %H:%M:%S")
        days_left = (end_date - datetime.now()).days
        
        text = f"""
✅ *SIZDA AKTIV PREMIUM OBUNA MAVJUD!*

📅 *Tugash vaqti:* {end_date.strftime('%d.%m.%Y %H:%M')}
⏳ *Qolgan muddat:* {days_left} kun

✨ Siz allaqachon kanallarga obunasiz foydalanishingiz mumkin!
        """
    
    elif pending:
        status_text = {
            'pending': "⏳ Tasdiqlash kutilmoqda",
            'confirmed': "✅ Tasdiqlangan",
            'rejected': "❌ Rad etilgan"
        }.get(pending['status'], pending['status'])
        
        sent_date = datetime.strptime(pending['sent_date'], "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        
        text = f"""
📊 *PREMIUM HOLATI:*

🔄 *Status:* {status_text}
📅 *Yuborilgan vaqt:* {sent_date}

"""
        
        if pending['status'] == 'pending':
            text += "\n⏳ Iltimos, sabr qiling. To'lov 24 soat ichida tekshiriladi."
        elif pending['status'] == 'rejected':
            text += "\n❌ To'lov tasdiqlanmadi. Yangi chek yuboring yoki @ar7_admin ga murojaat qiling."
    
    else:
        text = """
ℹ️ *PREMIUM HOLATI:*

Siz hali premium so'rov yubormagansiz.

👇 Premium sotib olish uchun:
"""
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💎 Premium sotib olish", callback_data="buy_premium")
        )
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔄 Yangilash", callback_data="check_premium_status")],
            [InlineKeyboardButton("💎 Premium haqida", callback_data="premium_info")]
        ]
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()



@dp.callback_query_handler(lambda c: c.data == "random_movie")
async def random_movie_callback(callback: CallbackQuery):
    await callback.answer("🎲 Tasodifiy film tanlanmoqda...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, description, video_file_id, movie_code, download_count 
        FROM movies 
        ORDER BY RANDOM() 
        LIMIT 1
    ''')
    
    movie = cursor.fetchone()
    conn.close()
    
    if not movie:
        await callback.answer("❌ Hozircha filmlar yo'q!", show_alert=True)
        return
    
    # Yuklanish logi
    log_download(callback.from_user.id, movie['id'])
    
    inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Do'stlarga yuborish", switch_inline_query=str(movie['movie_code'])),
                InlineKeyboardButton(text="💾 Saqlash", callback_data=f"save_{movie['id']}")
            ],
            [
                InlineKeyboardButton(text="🎲 Boshqa film", callback_data="random_movie"),
                InlineKeyboardButton(text="📋 Saqlanganlar", callback_data="saved_movies")
            ]
        ]
    )
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer_video(
        video=movie['video_file_id'],
        caption=f"🎬 *{movie['name']}*\n\n"
               f"📝 {movie['description'] or 'Tavsif mavjud emas'}\n\n"
               f"👁️ {movie['download_count'] + 1} marotaba ko'rilgan\n"
               f"🔢 Kino kodi: `{movie['movie_code']}`",
        parse_mode="Markdown",
        reply_markup=inline
    )

@dp.callback_query_handler(lambda c: c.data == "saved_movies")
async def saved_movies_callback(callback: CallbackQuery):
    await callback.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.id, m.name, m.movie_code, m.download_count, sm.saved_date
        FROM saved_movies sm
        JOIN movies m ON sm.movie_id = m.id
        WHERE sm.user_id = ?
        ORDER BY sm.saved_date DESC
        LIMIT 50
    ''', (callback.from_user.id,))
    
    saved_movies = cursor.fetchall()
    conn.close()
    
    if not saved_movies:
        await callback.message.answer("💾 *Siz hali hech qanday film saqlamagansiz!*", parse_mode="Markdown")
        return
    
    text = "💾 *SAQLANGAN FILMLAR*\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for i, movie in enumerate(saved_movies, 1):
        text += f"{i}. {movie['name']}\n"
        text += f"   🔢 Kodi: `{movie['movie_code']}`\n"
        text += f"   👁️ {movie['download_count']} marta\n\n"
        
        keyboard.insert(
            InlineKeyboardButton(
                text=str(i),
                callback_data=f"play_{movie['id']}"
            )
        )
    
    keyboard.add(InlineKeyboardButton("🗑️ Hammasini tozalash", callback_data="clear_saved"))
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu"))
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("save_"))
async def save_movie_callback(callback: CallbackQuery):
    movie_id = int(callback.data.split("_")[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Avval saqlanganligini tekshirish
    cursor.execute('''
        SELECT COUNT(*) as count FROM saved_movies 
        WHERE user_id = ? AND movie_id = ?
    ''', (callback.from_user.id, movie_id))
    
    if cursor.fetchone()['count'] > 0:
        await callback.answer("✅ Bu film allaqachon saqlangan!", show_alert=True)
        conn.close()
        return
    
    # Saqlash
    cursor.execute('''
        INSERT INTO saved_movies (user_id, movie_id) 
        VALUES (?, ?)
    ''', (callback.from_user.id, movie_id))
    
    conn.commit()
    conn.close()
    
    await callback.answer("💾 Film saqlandi!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("play_"))
async def play_saved_movie(callback: CallbackQuery):
    movie_id = int(callback.data.split("_")[1])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, description, video_file_id, movie_code, download_count 
        FROM movies WHERE id = ?
    ''', (movie_id,))
    
    movie = cursor.fetchone()
    conn.close()
    
    if not movie:
        await callback.answer("❌ Film topilmadi!", show_alert=True)
        return
    
    # Yuklanish logi
    log_download(callback.from_user.id, movie_id)
    
    inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Do'stlarga yuborish", switch_inline_query=str(movie['movie_code'])),
                InlineKeyboardButton(text="🗑️ Saqlovdan o'chirish", callback_data=f"unsave_{movie_id}")
            ],
            [
                InlineKeyboardButton(text="💾 Saqlanganlar", callback_data="saved_movies"),
                InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")
            ]
        ]
    )
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer_video(
        video=movie['video_file_id'],
        caption=f"🎬 *{movie['name']}*\n\n"
               f"📝 {movie['description'] or 'Tavsif mavjud emas'}\n\n"
               f"👁️ {movie['download_count'] + 1} marotaba ko'rilgan\n"
               f"🔢 Kino kodi: `{movie['movie_code']}`",
        parse_mode="Markdown",
        reply_markup=inline
    )

@dp.callback_query_handler(lambda c: c.data == "top_movies")
async def top_movies_callback(callback: CallbackQuery):
    await callback.answer()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT name, movie_code, download_count 
        FROM movies 
        ORDER BY download_count DESC 
        LIMIT 10
    ''')
    
    top_movies = cursor.fetchall()
    conn.close()
    
    text = "🏆 *TOP 10 FILMLAR*\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for i, movie in enumerate(top_movies, 1):
        text += f"{i}. {movie['name']}\n"
        text += f"   🔢 Kodi: `{movie['movie_code']}`\n"
        text += f"   👁️ {movie['download_count']} marta\n\n"
        
        keyboard.insert(
            InlineKeyboardButton(
                text=str(i),
                callback_data=f"play_by_code_{movie['movie_code']}"
            )
        )
    
    keyboard.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu"))
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

# ==================== ASOSIY MENYU ====================
@dp.message_handler(text="🔙 Asosiy menyu")
async def main_menu_return(message: types.Message):
    await start_command(message, None)

@dp.message_handler(text="🔙 Orqaga")
async def back_to_admin(message: types.Message):
    await admin_panel(message, None)

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery):
    await callback.answer()
    await start_command(callback.message, None)

# ==================== KINO KODI ORQALI QIDIRISH ====================
@dp.message_handler(lambda message: message.text.isdigit())
async def search_by_code(message: types.Message):
    movie_code = message.text
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, description, video_file_id, download_count, movie_code 
        FROM movies WHERE movie_code = ?
    ''', (movie_code,))
    
    movie = cursor.fetchone()
    conn.close()
    
    if not movie:
        await message.answer("❌ *Bunday kodli kino topilmadi!*\n\n🔍 Boshqa kod kiriting yoki qidiruvdan foydalaning.", parse_mode="Markdown")
        return
    
    # Yuklanish logi
    log_download(message.from_user.id, movie['id'])
    
    inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Do'stlarga yuborish", switch_inline_query=str(movie['movie_code'])),
                InlineKeyboardButton(text="💾 Saqlash", callback_data=f"save_{movie['id']}")
            ],
            [
                InlineKeyboardButton(text="📋 Saqlanganlar", callback_data="saved_movies"),
                InlineKeyboardButton(text="🎲 Tasodifiy kino", callback_data="random_movie")
            ]
        ]
    )
    
    await message.answer_video(
        video=movie['video_file_id'],
        caption=f"🎬 *{movie['name']}*\n\n"
               f"📝 {movie['description'] or 'Tavsif mavjud emas'}\n\n"
               f"👁️ {movie['download_count'] + 1} marotaba ko'rilgan\n"
               f"🔢 Kino kodi: `{movie['movie_code']}`",
        parse_mode="Markdown",
        reply_markup=inline
    )

# ==================== BOTNI ISHGA TUSHIRISH ====================
if __name__ == "__main__":
    # Ma'lumotlar bazasini yaratish
    init_db()
    
    # Dastlabki admin qo'shish
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (admin_id, admin_name) VALUES (?, ?)", 
                   (ADMIN_ID, "Asosiy Admin"))
    conn.commit()
    conn.close()
    
    logger.info("Bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True)
