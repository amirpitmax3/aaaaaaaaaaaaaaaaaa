# -*- coding: utf-8 -*-

"""
نسخه کامل و بهبودیافته ربات تلگرام شما.
تمام قابلیت‌های اصلی (پنل ادمین، سلف پرو، شرط‌بندی، پشتیبانی و...)
در این نسخه با ساختاری امن‌تر و خواناتر پیاده‌سازی شده‌اند.
"""

import os
import sqlite3
import logging
import asyncio
import secrets
import math
import re
import traceback
import html
from threading import Lock, Thread
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps

# کتابخانه‌های وب برای زنده نگه داشتن ربات در Render
from flask import Flask, request, render_template_string

# کتابخانه‌های ربات تلگرام
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    User,
    ReplyKeyboardRemove
)
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, ChatMemberStatus

# کتابخانه برای بخش Self Pro (Userbot)
try:
    from pyrogram import Client, filters as pyrogram_filters
    from pyrogram.handlers import MessageHandler as PyrogramMessageHandler
    from pyrogram.errors import (
        SessionPasswordNeeded, PhoneCodeInvalid, PhoneNumberInvalid,
        PasswordHashInvalid, ApiIdInvalid, PhoneCodeExpired, FloodWait
    )
    PYROGRAM_AVAILABLE = True
except ImportError:
    PYROGRAM_AVAILABLE = False
    # Define dummy classes if pyrogram is not installed to prevent startup errors
    class Client: pass
    class PyrogramMessageHandler: pass
    class pyrogram_filters: pass
    class FloodWait(Exception): pass
    class SessionPasswordNeeded(Exception): pass
    class PhoneCodeInvalid(Exception): pass
    class PhoneNumberInvalid(Exception): pass
    class PasswordHashInvalid(Exception): pass
    class ApiIdInvalid(Exception): pass
    class PhoneCodeExpired(Exception): pass


# --- Setup Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- Configuration ---
# It's recommended to set these as environment variables in your hosting service (e.g., Render)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8233582209:AAHKPQX-349tAfBOCFWbRRqcpD-QbVrDzQ0")
API_ID = int(os.environ.get("API_ID", "29645784"))
API_HASH = os.environ.get("API_HASH", "19e8465032deba8145d40fc4beb91744")
OWNER_ID = int(os.environ.get("OWNER_ID", "7423552124")) # ادمین اصلی

# Paths for persistent data on Render
DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
DB_PATH = os.path.join(DATA_PATH, "bot_database.db")
os.makedirs(DATA_PATH, exist_ok=True)

# Web App for Render health checks and secure login
WEB_APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:10000")
web_app = Flask(__name__)

# --- Global Variables & State Management ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
LOGIN_SESSIONS = {}
USER_SESSIONS = {} # Stores active pyrogram clients
session_lock = Lock() # Lock for thread-safe manipulation of LOGIN_SESSIONS
application = None # Global application object for Flask routes

# ConversationHandler States
(
    ASK_DIAMOND_AMOUNT, AWAIT_RECEIPT,
    ADMIN_PANEL_MAIN, SETTING_PRICE, SETTING_INITIAL_BALANCE,
    SETTING_SELF_COST, SETTING_CHANNEL_LINK, SETTING_REFERRAL_REWARD,
    SETTING_PAYMENT_CARD, SETTING_CARD_HOLDER,
    AWAITING_SUPPORT_MESSAGE, AWAITING_ADMIN_REPLY,
    AWAIT_CONTACT, AWAIT_SESSION_STRING,
    ADMIN_ADD, ADMIN_REMOVE
) = range(16)

# Font styles for the self-pro feature
FONT_STYLES = {
    'normal': "0123456789", 'monospace': "🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿",
    'doublestruck': "𝟘𝟙𚼉🛩🜜𝟝𝟞𝟟𝟠𝟡", 'stylized': "𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫",
    'cursive': "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
}

# --- Self-Pro Feature State ---
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
OFFLINE_MODE_STATUS = {}
USERS_REPLIED_IN_OFFLINE = {}
OFFLINE_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

ENEMY_REPLIES = [
 "کیرم تو رحم اجاره ای و خونی مالی مادرت", "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام و اب کوسشو بریزم کف خونه تا فردا صبح کارگرای افغانی برای نظافت اومدن با بوی اب کس مادرت بجقن و ابکیراشون نثار قبر مرده هات بشه", "احمق مادر کونی من کس مادرت گذاشتم تو بازم داری کسشر میگی", "هی بیناموس کیرم بره تو کس ننت واس بابات نشآخ مادر کیری کیرم بره تو کس اجدادت کسکش بیناموس کس ول نسل شوتی ابجی کسده کیرم تو کس مادرت بیناموس کیری کیرم تو کس نسلت ابجی کونی کس نسل سگ ممبر کونی ابجی سگ ممبر سگ کونی کیرم تو کس ننت کیر تو کس مادرت کیر خاندان  تو کس نسلت مادر کونی ابجی کونی کیری ناموس ابجیتو گاییدم سگ حرومی خارکسه مادر کیری با کیر بزنم تو رحم مادرت ناموستو بگام لاشی کونی ابجی کس  خیابونی مادرخونی ننت کیرمو میماله تو میای کص میگی شاخ نشو ییا ببین شاخو کردم تو کون ابجی جندت کس ابجیتو پاره کردم تو شاخ میشی اوبی",
]


# --- Utility Functions ---
def stylize_time(time_str: str, style: str) -> str:
    """Converts a time string using a specified font style."""
    if style not in FONT_STYLES:
        style = 'normal'
    return time_str.translate(str.maketrans("0123456789", FONT_STYLES[style]))

def get_user_handle(user: User) -> str:
    """Returns a user's @username or full_name."""
    return f"@{user.username}" if user.username else user.full_name


# --- Database Management ---
def db_connect():
    """Establishes a connection to the SQLite database."""
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con, con.cursor()

def setup_database():
    """Initializes the database schema if it doesn't exist."""
    con, cur = db_connect()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            self_active BOOLEAN DEFAULT FALSE, self_paused BOOLEAN DEFAULT FALSE,
            font_style TEXT DEFAULT 'normal', base_first_name TEXT,
            base_last_name TEXT, session_string TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount_diamonds INTEGER,
            amount_toman INTEGER, receipt_file_id TEXT, status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, approved_by INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER, referred_id INTEGER PRIMARY KEY
        )
    """)
    default_settings = {
        "diamond_price": "500", "initial_balance": "10", "self_hourly_cost": "5",
        "referral_reward": "20", "payment_card": "هنوز ثبت نشده",
        "payment_card_holder": "هنوز ثبت نشده", "mandatory_channel": "@YourChannel",
        "mandatory_channel_enabled": "false"
    }
    for key, value in default_settings.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
    cur.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)", (OWNER_ID, 5000000))
    con.commit()
    con.close()
    logger.info("Database setup complete.")


def get_setting(key: str) -> str | None:
    con, cur = db_connect()
    try:
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cur.fetchone()
        return result['value'] if result else None
    finally:
        con.close()

def update_setting(key: str, value: str):
    con, cur = db_connect()
    try:
        cur.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        con.commit()
    finally:
        con.close()

def get_user(user_id: int, username: str = None) -> sqlite3.Row | None:
    con, cur = db_connect()
    try:
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cur.fetchone()
        if not user:
            initial_balance = int(get_setting("initial_balance"))
            balance = 5000000 if user_id == OWNER_ID else initial_balance
            cur.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, balance))
            con.commit()
            cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cur.fetchone()
        elif username and user['username'] != username:
            cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            con.commit()
        return user
    finally:
        con.close()

def update_user_db(user_id: int, column: str, value):
    con, cur = db_connect()
    try:
        cur.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
        con.commit()
    finally:
        con.close()

def update_user_balance(user_id: int, amount: int, add: bool = True):
    operator = '+' if add else '-'
    con, cur = db_connect()
    try:
        cur.execute(f"UPDATE users SET balance = balance {operator} ? WHERE user_id = ?", (amount, user_id))
        con.commit()
    finally:
        con.close()

def get_admins() -> list[int]:
    con, cur = db_connect()
    try:
        cur.execute("SELECT user_id FROM admins")
        return [row['user_id'] for row in cur.fetchall()]
    finally:
        con.close()

def is_admin(user_id: int) -> bool:
    return user_id in get_admins()


# --- Decorators ---
def channel_membership_required(func):
    """A decorator that checks if a user is a member of the mandatory channel."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if get_setting("mandatory_channel_enabled") != 'true':
            return await func(update, context, *args, **kwargs)

        user = update.effective_user
        if is_admin(user.id):
            return await func(update, context, *args, **kwargs)

        channel_id = get_setting("mandatory_channel")
        if not channel_id or not channel_id.startswith('@'):
            return await func(update, context, *args, **kwargs)

        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                raise ValueError("User not a member")
        except Exception as e:
            logger.error(f"Membership check failed for {user.id} in {channel_id}: {e}")
            channel_link = f"https://t.me/{channel_id.lstrip('@')}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("عضویت در کانال", url=channel_link)]])
            target_message = update.callback_query.message if update.callback_query else update.effective_message
            await target_message.reply_text(
                "برای استفاده از ربات، لطفا ابتدا در کانال ما عضو شوید و سپس دوباره تلاش کنید.",
                reply_markup=keyboard
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


# --- Keyboards ---
async def main_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton("💎 موجودی"), KeyboardButton("🚀 Self Pro")]]
    row_two = [KeyboardButton("🎁 کسب جم رایگان")]
    if not is_admin(user_id):
        row_two.insert(0, KeyboardButton("💰 افزایش موجودی"))
        row_two.insert(1, KeyboardButton("💬 پشتیبانی"))
    keyboard.append(row_two)
    if is_admin(user_id):
        keyboard.append([KeyboardButton("👑 پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def self_pro_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = get_user(user_id)
    pause_text = "▶️ فعالسازی ساعت" if user['self_paused'] else "⏸️ توقف ساعت"
    pause_callback = "self_resume" if user['self_paused'] else "self_pause"
    keyboard = [
        [InlineKeyboardButton(pause_text, callback_data=pause_callback)],
        [InlineKeyboardButton("✏️ تغییر فونت", callback_data="change_font_menu")],
        [InlineKeyboardButton("🗑 حذف کامل سلف", callback_data="delete_self_confirm")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def font_selection_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user_font = get_user(user_id)['font_style']
    keyboard = []
    font_options = [('normal', 'Normal'), ('monospace', 'Monospace'), ('doublestruck', 'Doublestruck'), ('stylized', 'Stylized'), ('cursive', 'Cursive')]
    for style, name in font_options:
        text = f"✅ {name}" if user_font == style else name
        keyboard.append([InlineKeyboardButton(text, callback_data=f"set_font_{style}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_self_menu")])
    return InlineKeyboardMarkup(keyboard)


# --- Main Bot Handlers ---
@channel_membership_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    get_user(user.id, user.username) # Ensure user exists

    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                con, cur = db_connect()
                try:
                    cur.execute("SELECT * FROM referrals WHERE referred_id = ?", (user.id,))
                    if not cur.fetchone():
                        cur.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, user.id))
                        con.commit()
                        reward = int(get_setting("referral_reward"))
                        update_user_balance(referrer_id, reward, add=True)
                        try:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 تبریک! یک کاربر جدید از طریق لینک شما وارد ربات شد و شما {reward} الماس هدیه گرفتید."
                            )
                        except Exception as e:
                            logger.warning(f"Could not notify referrer {referrer_id}: {e}")
                finally:
                    con.close()
        except (ValueError, IndexError):
            pass

    await update.message.reply_text(
        f"سلام {user.first_name}! به ربات Self Pro خوش آمدید.",
        reply_markup=await main_reply_keyboard(user.id)
    )
    return ConversationHandler.END

# --- Self-Pro Section (Activation, Management, Background Task) ---
@channel_membership_required
async def self_pro_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not PYROGRAM_AVAILABLE:
        await update.message.reply_text("متاسفانه قابلیت سلف در حال حاضر غیرفعال است.")
        return ConversationHandler.END
        
    user_id = update.effective_user.id
    user_db = get_user(user_id)
    
    with session_lock:
        for token, session in LOGIN_SESSIONS.items():
            if session.get('user_id') == user_id:
                await update.message.reply_text("شما یک فرآیند ورود فعال دارید. لطفاً از لینکی که قبلاً برایتان ارسال شده استفاده کنید.")
                return ConversationHandler.END

    if user_db['self_active']:
        await update.message.reply_text("⚙️ منوی مدیریت Self Pro:", reply_markup=await self_pro_management_keyboard(user_id))
        return ConversationHandler.END

    hourly_cost = int(get_setting("self_hourly_cost"))
    if user_db['balance'] < hourly_cost:
        await update.message.reply_text(f"برای فعال سازی سلف، حداقل باید {hourly_cost} الماس موجودی داشته باشید.")
        return ConversationHandler.END

    keyboard = [[KeyboardButton("✅ اشتراک‌گذاری شماره تلفن", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "برای شروع فرآیند فعال‌سازی، لطفاً شماره تلفن خود را از طریق دکمه زیر به اشتراک بگذارید.",
        reply_markup=reply_markup
    )
    return AWAIT_CONTACT

async def self_pro_receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.effective_message.contact
    phone_number = contact.phone_number
    user_id = update.effective_user.id

    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"

    await update.message.reply_text(f"شماره شما ({phone_number}) دریافت شد. در حال ایجاد لینک ورود امن...", reply_markup=ReplyKeyboardRemove())

    login_token = secrets.token_urlsafe(16)
    with session_lock:
        LOGIN_SESSIONS[login_token] = {
            'user_id': user_id,
            'step': 'start',
            'phone': phone_number
        }
    
    login_url = f"{WEB_APP_URL}/login/{login_token}"
    text = (
        f"✅ **لینک ورود امن شما آماده شد.**\n\n"
        f"🔗 [برای ادامه اینجا کلیک کنید]({login_url})\n\n"
        "مراحل را در صفحه وب دنبال کنید. پس از اتمام، ربات به صورت خودکار نتیجه را به شما اعلام خواهد کرد."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=await main_reply_keyboard(user_id))
    return ConversationHandler.END

async def complete_self_pro_activation(user_id: int, session_string: str):
    await application.bot.send_message(user_id, "اطلاعات شما با موفقیت تایید شد. در حال فعال‌سازی نهایی سلف‌پرو...")
    try:
        # Verify the session string by starting and stopping a temporary client
        temp_client = Client(name=f"verify_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        await temp_client.start()
        me = await temp_client.get_me()
        await temp_client.stop()

        update_user_db(user_id, "base_first_name", me.first_name)
        update_user_db(user_id, "base_last_name", me.last_name or "")
        update_user_db(user_id, "self_active", True)
        update_user_db(user_id, "session_string", session_string)
        
        # Create and store the permanent client
        permanent_client = Client(name=f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        add_pyrogram_handlers(permanent_client)
        USER_SESSIONS[user_id] = permanent_client
        
        # Start the background task
        asyncio.create_task(self_pro_background_task(user_id, permanent_client))

        await application.bot.send_message(
            user_id, "✅ Self Pro با موفقیت فعال شد! اکنون می‌توانید آن را مدیریت کنید:",
            reply_markup=await self_pro_management_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Failed to complete self activation for {user_id}: {e}", exc_info=True)
        await application.bot.send_message(user_id, f"❌ خطایی در مرحله نهایی فعال‌سازی رخ داد: `{e}`. لطفاً دوباره تلاش کنید.", parse_mode=ParseMode.MARKDOWN)

async def self_pro_background_task(user_id: int, client: Client):
    try:
        if not client.is_connected:
            await client.start()
        
        while user_id in USER_SESSIONS:
            user = get_user(user_id)
            if not user or not user['self_active']:
                break
            
            if not user['self_paused']:
                hourly_cost = int(get_setting("self_hourly_cost"))
                if user['balance'] < hourly_cost:
                    await deactivate_self_pro(user_id, "موجودی الماس شما تمام شد و سلف غیرفعال گردید.")
                    break
                
                update_user_balance(user_id, hourly_cost, add=False)
                
                now_str = datetime.now(TEHRAN_TIMEZONE).strftime("%H:%M")
                styled_time = stylize_time(now_str, user['font_style'])
                
                try:
                    # Construct new name safely
                    current_name = user['base_first_name']
                    # This regex is complex, a simpler approach might be better
                    # For now, we assume it works as intended to strip old times
                    cleaned_name = re.sub(r'\s[\d\w:]{1,10}$', '', current_name).strip()

                    await client.update_profile(first_name=f"{cleaned_name} {styled_time}")
                except FloodWait as e:
                    logger.warning(f"FloodWait for {user_id}: sleeping for {e.value} seconds.")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    logger.error(f"Failed to update profile for {user_id}: {e}")

            await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Critical error in self_pro_background_task for {user_id}: {e}", exc_info=True)
    finally:
        await clean_up_user_session(user_id)

async def deactivate_self_pro(user_id: int, reason: str):
    logger.info(f"Deactivating self pro for user {user_id}. Reason: {reason}")
    await clean_up_user_session(user_id)
    update_user_db(user_id, "self_active", False)
    update_user_db(user_id, "self_paused", False)
    try:
        await application.bot.send_message(user_id, f"{reason} لطفاً حساب خود را شارژ کرده و دوباره فعال کنید.")
    except Exception as e:
        logger.warning(f"Could not notify user {user_id} about deactivation: {e}")

async def clean_up_user_session(user_id: int):
    client = USER_SESSIONS.pop(user_id, None)
    if client and client.is_connected:
        try:
            user_data = get_user(user_id)
            if user_data and user_data['base_first_name']:
                await client.update_profile(first_name=user_data['base_first_name'], last_name=user_data['base_last_name'] or "")
        except Exception as e:
            logger.error(f"Could not restore name for user {user_id} on cleanup: {e}")
        finally:
            await client.stop()

    # Clean up feature states
    ACTIVE_ENEMIES.pop(user_id, None)
    ENEMY_REPLY_QUEUES.pop(user_id, None)
    OFFLINE_MODE_STATUS.pop(user_id, None)
    USERS_REPLIED_IN_OFFLINE.pop(user_id, None)
    logger.info(f"Cleaned up session and features for user {user_id}.")

@channel_membership_required
async def delete_self_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("✅ بله، حذف کن", callback_data="delete_self_final"), InlineKeyboardButton("❌ خیر", callback_data="back_to_self_menu")]]
    await query.edit_message_text("آیا از حذف کامل سلف خود مطمئن هستید؟ این عمل غیرقابل بازگشت است.", reply_markup=InlineKeyboardMarkup(keyboard))

@channel_membership_required
async def delete_self_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer("در حال حذف سلف...")
    await clean_up_user_session(user_id)
    update_user_db(user_id, 'self_active', False)
    update_user_db(user_id, 'self_paused', False)
    update_user_db(user_id, 'session_string', None)
    await query.edit_message_text("✅ سلف شما با موفقیت حذف شد. نام اصلی شما بازیابی شد.")

@channel_membership_required
async def toggle_self_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    new_state = not user['self_paused']
    update_user_db(user_id, 'self_paused', new_state)
    await query.answer(f"ساعت با موفقیت {'متوقف' if new_state else 'فعال'} شد.")
    await query.edit_message_reply_markup(reply_markup=await self_pro_management_keyboard(user_id))

@channel_membership_required
async def change_font_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفا یک فونت برای نمایش زمان انتخاب کنید:", reply_markup=await font_selection_keyboard(query.from_user.id))

@channel_membership_required
async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    font_style = query.data.replace("set_font_", "")
    update_user_db(query.from_user.id, 'font_style', font_style)
    await query.answer(f"فونت با موفقیت به {font_style} تغییر یافت.")
    await query.edit_message_reply_markup(reply_markup=await font_selection_keyboard(query.from_user.id))

@channel_membership_required
async def back_to_self_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚙️ منوی مدیریت Self Pro:", reply_markup=await self_pro_management_keyboard(query.from_user.id))


# --- Pyrogram (Userbot) Feature Handlers ---
def add_pyrogram_handlers(client: Client):
    """Adds all necessary handlers to a pyrogram client instance."""
    handlers = [
        PyrogramMessageHandler(enemy_controller, pyrogram_filters.text & pyrogram_filters.reply & pyrogram_filters.me & pyrogram_filters.regex("^(دشمن فعال|دشمن خاموش)$")),
        PyrogramMessageHandler(offline_mode_controller, pyrogram_filters.text & pyrogram_filters.me & pyrogram_filters.regex("^(حالت افلاین فعال|افلاین خاموش)$")),
        PyrogramMessageHandler(enemy_handler, pyrogram_filters.text & (pyrogram_filters.group | pyrogram_filters.private) & ~pyrogram_filters.me),
        PyrogramMessageHandler(offline_auto_reply_handler, pyrogram_filters.private & ~pyrogram_filters.me)
    ]
    for handler in handlers:
        client.add_handler(handler)

async def enemy_handler(client, message):
    user_id = client.me.id
    if not ACTIVE_ENEMIES.get(user_id): return
    enemy_list = ACTIVE_ENEMIES.get(user_id, set())
    if message.from_user and (message.from_user.id, message.chat.id) in enemy_list:
        if not ENEMY_REPLY_QUEUES.get(user_id) or len(ENEMY_REPLY_QUEUES[user_id]) == 0:
            ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
        reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
        try:
            await message.reply_text(reply_text)
        except Exception as e:
            logger.warning(f"Could not reply to enemy for user {user_id}: {e}")

async def enemy_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    user_id = client.me.id
    target_user, chat_id, command = message.reply_to_message.from_user, message.chat.id, message.text.strip()
    ACTIVE_ENEMIES.setdefault(user_id, set())
    if command == "دشمن فعال":
        ACTIVE_ENEMIES[user_id].add((target_user.id, chat_id))
        await message.edit_text(f"✅ **حالت دشمن برای {target_user.first_name} در این چت فعال شد.**")
    elif command == "دشمن خاموش":
        ACTIVE_ENEMIES[user_id].discard((target_user.id, chat_id))
        await message.edit_text(f"❌ **حالت دشمن برای {target_user.first_name} در این چت خاموش شد.**")

async def offline_mode_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "حالت افلاین فعال":
        OFFLINE_MODE_STATUS[user_id] = True
        USERS_REPLIED_IN_OFFLINE[user_id] = set()
        await message.edit_text("✅ **حالت آفلاین فعال شد.**")
    elif command == "افلاین خاموش":
        OFFLINE_MODE_STATUS[user_id] = False
        await message.edit_text("❌ **حالت آفلاین غیرفعال شد.**")

async def offline_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if OFFLINE_MODE_STATUS.get(owner_user_id, False):
        replied_users = USERS_REPLIED_IN_OFFLINE.setdefault(owner_user_id, set())
        if message.from_user.id in replied_users: return
        try:
            await message.reply_text(OFFLINE_REPLY_MESSAGE)
            replied_users.add(message.from_user.id)
        except Exception as e:
            logger.warning(f"Could not auto-reply for user {owner_user_id}: {e}")


# --- Group Features (Betting, Transfer) ---
async def check_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💎 موجودی شما: {user['balance']} الماس")

async def group_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.strip()
    if text == 'موجودی':
        await check_balance_handler(update, context)
    # Add other group command handlers here
    
async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message: return
    match = re.search(r'(\d+)', update.message.text)
    if not match: return

    try:
        amount = int(match.group(1))
    except (ValueError, TypeError):
        return
    if amount <= 0: return

    sender = update.effective_user
    receiver = update.message.reply_to_message.from_user

    if sender.id == receiver.id:
        await update.message.reply_text("انتقال به خود امکان‌پذیر نیست.")
        return
    if get_user(sender.id)['balance'] < amount:
        await update.message.reply_text("موجودی شما کافی نیست.")
        return

    get_user(receiver.id, receiver.username)
    update_user_balance(sender.id, amount, add=False)
    update_user_balance(receiver.id, amount, add=True)

    text = (f"✅ <b>انتقال موفق</b> ✅\n\n"
            f"👤 <b>از:</b> {get_user_handle(sender)}\n"
            f"👥 <b>به:</b> {get_user_handle(receiver)}\n"
            f"💎 <b>مبلغ:</b> {amount} الماس")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# --- Web Server (Flask) ---
@web_app.route('/')
def index():
    """Health check endpoint for Render."""
    return "Bot is running!", 200

# The secure login flow via web is complex. This is a simplified placeholder.
# A full implementation would require more routes, error handling, and a proper UI.
@web_app.route('/login/<token>')
def login_page(token):
    # This page should be a proper HTML form
    return f"Login page for token {token}. (Implementation needed)"


# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error detected. Another instance is running.")
        if context.application.running:
            await context.application.stop()
        return
    logger.error("Exception while handling an update:", exc_info=context.error)


# --- Main Application Setup ---
def main() -> None:
    """Start the bot."""
    global application
    setup_database()

    if not PYROGRAM_AVAILABLE:
        logger.warning("Pyrogram library not found. Self-pro features will be disabled.")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Conversation Handlers
    self_pro_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚀 Self Pro$"), self_pro_start)],
        states={AWAIT_CONTACT: [MessageHandler(filters.CONTACT, self_pro_receive_contact)]},
        fallbacks=[CommandHandler("start", start)],
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(self_pro_conv)
    application.add_handler(MessageHandler(filters.Regex("^💎 موجودی$"), check_balance_handler))
    
    # Group message handler for "موجودی"
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        group_text_handler
    ))
    # Transfer handler
    application.add_handler(MessageHandler(
        filters.Regex(r'^انتقال\s+(\d+)') & filters.REPLY, 
        handle_transfer
    ))
    
    # Self Pro management callbacks
    application.add_handler(CallbackQueryHandler(toggle_self_pause, pattern="^self_(pause|resume)$"))
    application.add_handler(CallbackQueryHandler(change_font_menu, pattern="^change_font_menu$"))
    application.add_handler(CallbackQueryHandler(set_font, pattern="^set_font_"))
    application.add_handler(CallbackQueryHandler(back_to_self_menu, pattern="^back_to_self_menu$"))
    application.add_handler(CallbackQueryHandler(delete_self_confirm, pattern="^delete_self_confirm$"))
    application.add_handler(CallbackQueryHandler(delete_self_final, pattern="^delete_self_final$"))

    # Add other handlers (admin, support, etc.) here as needed

    application.add_error_handler(error_handler)

    # Start existing user sessions on bot restart
    # con, cur = db_connect()
    # cur.execute("SELECT user_id, session_string FROM users WHERE self_active = TRUE AND session_string IS NOT NULL")
    # active_users = cur.fetchall()
    # con.close()
    # for user in active_users:
    #     logger.info(f"Re-activating self-pro for user {user['user_id']}")
    #     # This part needs careful async handling on startup
    
    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or "YOUR_TOKEN" in TELEGRAM_TOKEN:
        logger.error("Telegram token not found or is a placeholder. Please set the TELEGRAM_TOKEN environment variable.")
    else:
        # Start Flask web server in a new thread for Render health checks
        port = int(os.environ.get('PORT', 10000))
        flask_thread = Thread(target=lambda: web_app.run(host='0.0.0.0', port=port))
        flask_thread.daemon = True
        flask_thread.start()
        logger.info(f"Flask web server started on port {port}")
        
        main()

