# -*- coding: utf-8 -*-

import os
import sqlite3
import logging
import asyncio
from threading import Thread
from datetime import datetime, timedelta
import random
import math
import re
import sys
import atexit
from functools import wraps
import time
import traceback
import html
import secrets
from zoneinfo import ZoneInfo

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
    PicklePersistence
)
from telegram.constants import ParseMode, ChatMemberStatus

# کتابخانه برای بخش Self Pro (Userbot)
from pyrogram import Client, filters as pyrogram_filters
from pyrogram.handlers import MessageHandler as PyrogramMessageHandler
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    PasswordHashInvalid,
    ApiIdInvalid,
    PhoneCodeExpired,
    FloodWait
)
from apscheduler.jobstores.base import JobLookupError


# تنظیمات لاگ‌گیری برای دیباگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error detected. Requesting application stop.")
        # This will cause the run_polling loop to stop gracefully
        await context.application.stop()
        return
    
    logger.error(f"Exception while handling an update:", exc_info=context.error)
    


# --- بخش وب سرور برای Ping و لاگین ---
web_app = Flask(__name__)
WEB_APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:10000") 
LOGIN_SESSIONS = {}
application = None # Define application globally so Flask routes can access job_queue


# --- متغیرهای ربات ---
TELEGRAM_TOKEN = "8367987651:AAE4qOeiBpJNH4fjCt1trzM7g5cKF8s8qGM"
API_ID = 29645784
API_HASH = "19e8465032deba8145d40fc4beb91744"
OWNER_ID = 7423552124 # ادمین اصلی
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")


# مسیر دیتابیس و فایل قفل در دیسک پایدار Render
DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
DB_PATH = os.path.join(DATA_PATH, "bot_database.db")
LOCK_FILE_PATH = os.path.join(DATA_PATH, "bot.lock")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- مراحل ConversationHandler ---
(
    ASK_DIAMOND_AMOUNT, AWAIT_RECEIPT,
    ADMIN_PANEL_MAIN, SETTING_PRICE, SETTING_INITIAL_BALANCE,
    SETTING_SELF_COST, SETTING_CHANNEL_LINK, SETTING_REFERRAL_REWARD,
    SETTING_PAYMENT_CARD, SETTING_CARD_HOLDER,
    AWAITING_SUPPORT_MESSAGE, AWAITING_ADMIN_REPLY,
    AWAIT_CONTACT, AWAIT_SESSION_STRING, # AWAIT_SESSION_STRING is no longer used in conversation but kept for range
    ADMIN_ADD, ADMIN_REMOVE
) = range(16)


# --- استایل‌های فونت ---
FONT_STYLES = {
    'normal': "0123456789", 'monospace': "🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿",
    'doublestruck': "𝟘𝟙𚼉🛩𝟜𝟝𝟞𝟟𝟠𝟡", 'stylized': "𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫",
    'cursive': "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
}

def stylize_time(time_str: str, style: str) -> str:
    if style not in FONT_STYLES: style = 'normal'
    return time_str.translate(str.maketrans("0123456789", FONT_STYLES[style]))

# --- متغیرهای قابلیت‌های جدید ---
ENEMY_REPLIES = [
  "کیرم تو رحم اجاره ای و خونی مالی مادرت", "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام و اب کوسشو بریزم کف خونه تا فردا صبح کارگرای افغانی برای نظافت اومدن با بوی اب کس مادرت بجقن و ابکیراشون نثار قبر مرده هات بشه", "احمق مادر کونی من کس مادرت گذاشتم تو بازم داری کسشر میگی", "هی بیناموس کیرم بره تو کس ننت واس بابات نشآخ مادر کیری کیرم بره تو کس اجدادت کسکش بیناموس کس ول نسل شوتی ابجی کسده کیرم تو کس مادرت بیناموس کیری کیرم تو کس نسلت ابجی کونی کس نسل سگ ممبر کونی ابجی سگ ممبر سگ کونی کیرم تو کس ننت کیر تو کس مادرت کیر خاندان  تو کس نسلت مادر کونی ابجی کونی کیری ناموس ابجیتو گاییدم سگ حرومی خارکسه مادر کیری با کیر بزنم تو رحم مادرت ناموستو بگام لاشی کونی ابجی کس  خیابونی مادرخونی ننت کیرمو میماله تو میای کص میگی شاخ نشو ییا ببین شاخو کردم تو کون ابجی جندت کس ابجیتو پاره کردم تو شاخ میشی اوبی",
]
OFFLINE_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
OFFLINE_MODE_STATUS = {}
USERS_REPLIED_IN_OFFLINE = {}


# --- مدیریت دیتابیس (SQLite) ---
def db_connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con, con.cursor()

def setup_database():
    con, cur = db_connect()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            self_active BOOLEAN DEFAULT FALSE, self_paused BOOLEAN DEFAULT FALSE,
            font_style TEXT DEFAULT 'normal', 
            base_first_name TEXT, base_last_name TEXT, session_string TEXT,
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
        "referral_reward": "20", "payment_card": "هنوز ثبت نشده", "payment_card_holder": "هنوز ثبت نشده",
        "mandatory_channel": "@YourChannel", "mandatory_channel_enabled": "false"
    }
    for key, value in default_settings.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (OWNER_ID,))
    cur.execute("UPDATE users SET balance = 5000000 WHERE user_id = ?", (OWNER_ID,))
    con.commit()
    con.close()
    logger.info("Database setup complete.")

# --- توابع کمکی دیتابیس ---
def get_setting(key):
    con, cur = db_connect()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cur.fetchone()
    con.close()
    return result['value'] if result else None

def update_setting(key, value):
    con, cur = db_connect()
    cur.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    con.commit()
    con.close()

def get_user(user_id, username=None):
    con, cur = db_connect()
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
    con.close()
    return user

def update_user_db(user_id, column, value):
    con, cur = db_connect()
    cur.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
    con.commit()
    con.close()

def update_user_balance(user_id, amount, add=True):
    con, cur = db_connect()
    operator = '+' if add else '-'
    cur.execute(f"UPDATE users SET balance = balance {operator} ? WHERE user_id = ?", (amount, user_id))
    con.commit()
    con.close()

def get_admins():
    con, cur = db_connect()
    cur.execute("SELECT user_id FROM admins")
    admins = [row['user_id'] for row in cur.fetchall()]
    con.close()
    return admins

def is_admin(user_id): return user_id in get_admins()
def get_user_handle(user: User): return f"@{user.username}" if user.username else user.full_name

# --- دکوریتور عضویت اجباری ---
def channel_membership_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        is_enabled = get_setting("mandatory_channel_enabled")
        if is_enabled != 'true': return await func(update, context, *args, **kwargs)
        user = update.effective_user
        if is_admin(user.id): return await func(update, context, *args, **kwargs)
        channel_id = get_setting("mandatory_channel")
        if not channel_id or not channel_id.startswith('@'): return await func(update, context, *args, **kwargs)
        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                raise ValueError("User not a member")
        except Exception:
            channel_link = f"https://t.me/{channel_id.lstrip('@')}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("عضویت در کانال", url=channel_link)]])
            await (update.effective_message or update.callback_query.message).reply_text(
                "برای استفاده از ربات، لطفا ابتدا در کانال ما عضو شوید و سپس دوباره تلاش کنید.", reply_markup=keyboard
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# --- کیبوردهای ربات ---
async def main_reply_keyboard(user_id):
    keyboard = [[KeyboardButton("💎 موجودی"), KeyboardButton("🚀 Self Pro")]]
    row_two = [KeyboardButton("🎁 کسب جم رایگان")]
    if not is_admin(user_id):
        row_two.insert(0, KeyboardButton("💰 افزایش موجودی"))
        row_two.insert(1, KeyboardButton("💬 پشتیبانی"))
    keyboard.append(row_two)
    if is_admin(user_id): keyboard.append([KeyboardButton("👑 پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def self_pro_management_keyboard(user_id):
    user = get_user(user_id)
    pause_text = "▶️ فعالسازی ساعت" if user['self_paused'] else "⏸️ توقف ساعت"
    pause_callback = "self_resume" if user['self_paused'] else "self_pause"
    keyboard = [
        [InlineKeyboardButton(pause_text, callback_data=pause_callback)],
        [InlineKeyboardButton("✏️ تغییر فونت", callback_data="change_font_menu")],
        [InlineKeyboardButton("🗑 حذف کامل سلف", callback_data="delete_self_confirm")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def font_selection_keyboard(user_id):
    user_font = get_user(user_id)['font_style']
    keyboard = []
    for style, name in [('normal', 'Normal'), ('monospace', 'Monospace'), ('doublestruck', 'Doublestruck'), ('stylized', 'Stylized'), ('cursive', 'Cursive')]:
        text = f"✅ {name}" if user_font == style else name
        keyboard.append([InlineKeyboardButton(text, callback_data=f"set_font_{style}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_self_menu")])
    return InlineKeyboardMarkup(keyboard)
    
# --- دستورات اصلی ---
@channel_membership_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    get_user(user.id, user.username) # Ensure user exists

    # --- Referral Logic ---
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                con, cur = db_connect()
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
                con.close()
        except (ValueError, IndexError):
            pass # Invalid referral code

    await update.message.reply_text(
        f"سلام {user.first_name}! به ربات Self Pro خوش آمدید.", reply_markup=await main_reply_keyboard(user.id)
    )
    return ConversationHandler.END

# --- Secure Self-Pro Activation Flow ---
user_sessions = {}

@channel_membership_required
async def self_pro_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_db = get_user(user_id)
    
    # Check if a login process is already active for this user
    for token, session in list(LOGIN_SESSIONS.items()):
        if session.get('user_id') == user_id:
            await update.message.reply_text("شما یک فرآیند ورود فعال دارید. لطفاً از لینکی که قبلاً برایتان ارسال شده استفاده کنید یا چند دقیقه صبر کرده و دوباره تلاش نمایید.")
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
        phone_number = '+' + phone_number

    await update.message.reply_text(
        f"شماره شما ({phone_number}) دریافت شد. در حال ایجاد لینک ورود امن...",
        reply_markup=ReplyKeyboardRemove()
    )

    login_token = secrets.token_urlsafe(16)
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
        client = Client(name=f"verify_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        await client.start()
        me = await client.get_me()
        await client.stop()
        update_user_db(user_id, "base_first_name", me.first_name)
        update_user_db(user_id, "base_last_name", me.last_name or "")
        update_user_db(user_id, "self_active", True)
        update_user_db(user_id, "session_string", session_string)
        permanent_client = Client(name=f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        permanent_client.add_handler(PyrogramMessageHandler(enemy_controller, pyrogram_filters.text & pyrogram_filters.reply & pyrogram_filters.me & pyrogram_filters.regex("^(دشمن فعال|دشمن خاموش)$")), group=0)
        permanent_client.add_handler(PyrogramMessageHandler(offline_mode_controller, pyrogram_filters.text & pyrogram_filters.me & pyrogram_filters.regex("^(حالت افلاین فعال|افلاین خاموش)$")), group=0)
        permanent_client.add_handler(PyrogramMessageHandler(enemy_handler, pyrogram_filters.text & (pyrogram_filters.group | pyrogram_filters.private) & ~pyrogram_filters.me), group=1)
        permanent_client.add_handler(PyrogramMessageHandler(offline_auto_reply_handler, pyrogram_filters.private & ~pyrogram_filters.me), group=1)
        user_sessions[user_id] = permanent_client
        asyncio.create_task(self_pro_background_task(user_id, permanent_client, application))
        await application.bot.send_message(
            user_id, 
            "✅ Self Pro با موفقیت فعال شد! اکنون می‌توانید آن را مدیریت کنید:", 
            reply_markup=await self_pro_management_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"Failed to complete self activation for {user_id}: {e}", exc_info=True)
        await application.bot.send_message(user_id, f"❌ خطایی در مرحله نهایی فعال‌سازی رخ داد: `{e}`. لطفاً دوباره تلاش کنید.", parse_mode=ParseMode.MARKDOWN)

async def self_pro_background_task(user_id: int, client: Client, application: Application):
    try:
        if not client.is_connected: await client.start()
        while user_id in user_sessions:
            user = get_user(user_id)
            if not user or not user['self_active']: break
            if not user['self_paused']:
                hourly_cost = int(get_setting("self_hourly_cost"))
                if user['balance'] < hourly_cost:
                    await deactivate_self_pro(user_id, client, application)
                    break
                update_user_balance(user_id, hourly_cost, add=False)
                now_str = datetime.now(TEHRAN_TIMEZONE).strftime("%H:%M")
                styled_time = stylize_time(now_str, user['font_style'])
                try: 
                    current_name = user['base_first_name']
                    cleaned_name = re.sub(r'\s[\d🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿𝟘𝟙𚼉🛩𝟜𝟝𝟞𝟟𝟠𝟡𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗]{1,2}:[\d🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿𝟘𝟙𚼉🛩𝟜𝟝𝟞𝟟𝟠𝟡𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗]{2}$', '', current_name).strip()
                    await client.update_profile(first_name=f"{cleaned_name} {styled_time}")
                except FloodWait as e:
                    logger.warning(f"FloodWait for {user_id}: sleeping for {e.value} seconds.")
                    await asyncio.sleep(e.value)
                except Exception as e: logger.error(f"Failed to update profile for {user_id}: {e}")
            await asyncio.sleep(60)
    except Exception as e: logger.error(f"Critical error in self_pro_background_task for {user_id}: {e}", exc_info=True)
    finally:
        await clean_up_user_session(user_id)
        
async def deactivate_self_pro(user_id: int, client: Client, application: Application):
    logger.info(f"Deactivating self pro for user {user_id} due to insufficient balance.")
    await clean_up_user_session(user_id)
    update_user_db(user_id, "self_active", False)
    update_user_db(user_id, "self_paused", False)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ادامه فعالسازی", callback_data="reactivate_self")]])
    await application.bot.send_message(user_id, "موجودی الماس شما تمام شد و سلف غیرفعال گردید. لطفاً حساب خود را شارژ کرده و دوباره فعال کنید.", reply_markup=keyboard)


async def clean_up_user_session(user_id: int):
    client = user_sessions.pop(user_id, None)
    if client and client.is_connected:
        try:
            user_data = get_user(user_id)
            if user_data and user_data['base_first_name']:
                 await client.update_profile(first_name=user_data['base_first_name'], last_name=user_data['base_last_name'] or "")
        except Exception as e:
            logger.error(f"Could not restore name for user {user_id} on cleanup: {e}")
        finally:
             await client.stop()

    ACTIVE_ENEMIES.pop(user_id, None)
    ENEMY_REPLY_QUEUES.pop(user_id, None)
    OFFLINE_MODE_STATUS.pop(user_id, None)
    USERS_REPLIED_IN_OFFLINE.pop(user_id, None)
    logger.info(f"Cleaned up session and features for user {user_id}.")


async def reactivate_self_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    update.effective_message.text = "🚀 Self Pro"
    await self_pro_start(update.effective_message, context)


# --- هندلرهای قابلیت‌های جدید ---
async def enemy_handler(client, message):
    user_id = client.me.id
    if not ACTIVE_ENEMIES.get(user_id): return
    enemy_list = ACTIVE_ENEMIES.get(user_id, set())
    if message.from_user and (message.from_user.id, message.chat.id) in enemy_list:
        if not ENEMY_REPLY_QUEUES.get(user_id):
            ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
        reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
        try: await message.reply_text(reply_text)
        except Exception as e: logger.warning(f"Could not reply to enemy for user {user_id}: {e}")

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
        await message.edit_text(f"❌ **حalt دشمن برای {target_user.first_name} در این چت خاموش شد.**")

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
        except Exception as e: logger.warning(f"Could not auto-reply for user {owner_user_id}: {e}")

@channel_membership_required
async def delete_self_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(" بله، حذف کن", callback_data="delete_self_final"), InlineKeyboardButton(" خیر", callback_data="back_to_self_menu")]]
    await query.edit_message_text("آیا از حذف کامل سلف خود مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))

@channel_membership_required
async def delete_self_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await clean_up_user_session(user_id)
    update_user_db(user_id, 'self_active', False)
    update_user_db(user_id, 'self_paused', False)
    update_user_db(user_id, 'base_first_name', None)
    update_user_db(user_id, 'base_last_name', None)
    update_user_db(user_id, 'session_string', None)
    await query.answer("سلف شما با موفقیت حذف شد.")
    await query.edit_message_text("سلف شما حذف شد. نام اصلی شما بازیابی شد.")

@channel_membership_required
async def toggle_self_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user = get_user(query.from_user.id)
    new_state = not user['self_paused']
    update_user_db(query.from_user.id, 'self_paused', new_state)
    await query.answer(f"ساعت با موفقیت {'متوقف' if new_state else 'فعال'} شد.")
    await query.edit_message_reply_markup(reply_markup=await self_pro_management_keyboard(query.from_user.id))

@channel_membership_required
async def change_font_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
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
    query = update.callback_query; await query.answer()
    await query.edit_message_text("⚙️ منوی مدیریت Self Pro:", reply_markup=await self_pro_management_keyboard(query.from_user.id))

# --- Group Features ---
@channel_membership_required
async def group_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or update.effective_chat.type not in ['group', 'supergroup']: return
    text = update.message.text.strip()
    if text == 'موجودی': await check_balance_text_handler(update, context)
    elif text.startswith('شرطبندی '):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            context.args = [parts[1]]
            await start_bet(update, context)
        else: await update.message.reply_text("فرمت صحیح: شرطبندی <مبلغ>")

async def handle_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message: return
    match = re.search(r'(\d+)', update.message.text)
    if not match: return
    try: amount = int(match.group(1))
    except (ValueError, TypeError): return
    if amount <= 0: return
    sender, receiver = update.effective_user, update.message.reply_to_message.from_user
    if sender.id == receiver.id: await update.message.reply_text("انتقال به خود امکان‌پذیر نیست."); return
    if get_user(sender.id)['balance'] < amount: await update.message.reply_text("موجودی شما کافی نیست."); return
    get_user(receiver.id, receiver.username)
    update_user_balance(sender.id, amount, add=False)
    update_user_balance(receiver.id, amount, add=True)
    text = (f"✅ <b>انتقال موفق</b> ✅\n\n"
            f"👤 <b>از:</b> {get_user_handle(sender)}\n"
            f"👥 <b>به:</b> {get_user_handle(receiver)}\n"
            f"💎 <b>مبلغ:</b> {amount} الماس")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def resolve_bet_logic(chat_id: int, message_id: int, bet_info: dict, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🎲 تاس‌ها در حال چرخش...", reply_markup=None)
    await asyncio.sleep(3)
    winner_id = secrets.choice(list(bet_info['participants']))
    losers_list = [p_id for p_id in bet_info['participants'] if p_id != winner_id]
    bet_amount, total_pot = bet_info['amount'], bet_info['amount'] * len(bet_info['participants'])
    tax = math.ceil(total_pot * 0.02)
    prize = total_pot - tax
    update_user_balance(winner_id, prize, add=True)
    for p_id in bet_info['participants']:
        if 'users_in_bet' in context.chat_data: context.chat_data['users_in_bet'].discard(p_id)
    winner_handle = get_user_handle(await context.bot.get_chat(winner_id))
    losers_handles = ", ".join([get_user_handle(await context.bot.get_chat(loser_id)) for loser_id in losers_list])
    result_text = (f"<b>🎲 نتیجه شرط‌بندی 🎲</b>\nمبلغ: {bet_amount} الماس\n\n"
                   f"🏆 <b>برنده:</b> {winner_handle}\n"
                   f"💔 <b>بازنده‌ها:</b> {losers_handles or 'هیچ‌کس'}\n\n"
                   f"💰 <b>جایزه:</b> {prize} الماس (کسر {tax} الماس مالیات)")
    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=result_text, parse_mode=ParseMode.HTML)

async def end_bet_on_timeout(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_data = context.application.chat_data.get(job_data['chat_id'], {})
    bet_info = job_data['bet_info']
    for p_id in bet_info['participants']:
        update_user_balance(p_id, bet_info['amount'], add=True)
        if 'users_in_bet' in chat_data: chat_data['users_in_bet'].discard(p_id)
    if 'bets' in chat_data: chat_data['bets'].pop(job_data['message_id'], None)
    await context.bot.edit_message_text(chat_id=job_data['chat_id'], message_id=job_data['message_id'], text="⌛️ زمان شرط‌بندی تمام شد و مبلغ بازگردانده شد.")

@channel_membership_required
async def start_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data.setdefault('users_in_bet', set())
    creator = update.effective_user
    if creator.id in context.chat_data['users_in_bet']:
        await update.message.reply_text("شما در یک شرط‌بندی دیگر فعال هستید."); return
    try:
        amount = int(context.args[0])
        if amount <= 0: await update.message.reply_text("مبلغ شرط باید مثبت باشد."); return
    except (IndexError, ValueError):
        await update.message.reply_text("مثال: /bet 100"); return
    if get_user(creator.id, creator.username)['balance'] < amount:
        await update.message.reply_text("موجودی شما کافی نیست."); return
    update_user_balance(creator.id, amount, add=False)
    bet_message = await update.message.reply_text("در حال ایجاد شرط...")
    bet_info = {'amount': amount, 'creator_id': creator.id, 'participants': {creator.id}}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ پیوستن", callback_data=f"join_bet_{bet_message.message_id}"), InlineKeyboardButton("❌ لغو", callback_data=f"cancel_bet_{bet_message.message_id}")]])
    text = (f"🎲 شرط‌بندی جدید به مبلغ <b>{amount}</b> الماس توسط {get_user_handle(creator)}!\n\n"
            f"نفر دوم که بپیوندد، برنده مشخص خواهد شد.\n\n"
            f"<b>شرکت کنندگان:</b>\n- {get_user_handle(creator)}")
    await bet_message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    job_data = {'message_id': bet_message.message_id, 'bet_info': bet_info, 'chat_id': update.effective_chat.id}
    job = context.job_queue.run_once(end_bet_on_timeout, 60, data=job_data, name=f"bet_{bet_message.message_id}")
    bet_info['job'] = job
    context.chat_data.setdefault('bets', {})[bet_message.message_id] = bet_info
    context.chat_data['users_in_bet'].add(creator.id)

@channel_membership_required
async def join_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query, user = update.callback_query, update.callback_query.from_user
    message_id = int(query.data.split("_")[-1])
    bets = context.chat_data.get('bets', {})
    if message_id not in bets: await query.answer("این شرط‌بندی فعال نیست.", show_alert=True); return
    bet_info = bets[message_id]
    if user.id in bet_info['participants']: await query.answer("شما قبلاً پیوسته‌اید.", show_alert=True); return
    if user.id in context.chat_data.get('users_in_bet', set()): await query.answer("شما در شرط‌بندی دیگری فعال هستید.", show_alert=True); return
    if get_user(user.id, user.username)['balance'] < bet_info['amount']:
        await query.answer("موجودی شما کافی نیست.", show_alert=True); return
    update_user_balance(user.id, bet_info['amount'], add=False)
    bet_info['participants'].add(user.id)
    context.chat_data['users_in_bet'].add(user.id)
    await query.answer("شما به شرط پیوستید!")
    bet_info['job'].schedule_removal()
    context.chat_data['bets'].pop(message_id, None)
    await resolve_bet_logic(update.effective_chat.id, message_id, bet_info, context)

async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    message_id = int(query.data.split("_")[-1])
    bets = context.chat_data.get('bets', {})
    if message_id not in bets: await query.answer("این شرط‌بندی فعال نیست.", show_alert=True); return
    bet_info = bets[message_id]
    if query.from_user.id != bet_info['creator_id']:
        await query.answer("فقط شروع‌کننده می‌تواند شرط را لغو کند.", show_alert=True); return
    bet_info['job'].schedule_removal()
    for p_id in bet_info['participants']:
        update_user_balance(p_id, bet_info['amount'], add=True)
        if 'users_in_bet' in context.chat_data: context.chat_data['users_in_bet'].discard(p_id)
    context.chat_data['bets'].pop(message_id, None)
    await query.message.edit_text(f"🎲 شرط‌بندی توسط {get_user_handle(query.from_user)} لغو شد.")
    await query.answer("شرط لغو شد.")

# --- Other Bot Functions ---
@channel_membership_required
async def buy_diamond_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تعداد الماسی که قصد خرید دارید را وارد کنید:")
    return ASK_DIAMOND_AMOUNT

async def ask_diamond_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفا یک عدد صحیح وارد کنید."); return ASK_DIAMOND_AMOUNT
    if not 0 < amount <= 10000:
        await update.message.reply_text("لطفا یک عدد بین ۱ تا ۱۰,۰۰۰ وارد کنید."); return ASK_DIAMOND_AMOUNT
    
    diamond_price = int(get_setting("diamond_price"))
    total_cost = amount * diamond_price
    payment_card, card_holder = get_setting("payment_card"), get_setting("payment_card_holder")
    context.user_data.update({'purchase_amount': amount, 'purchase_cost': total_cost})
    text = (f"🧾 **پیش‌فاکتور خرید**\n\n💎 تعداد: {amount}\n💳 مبلغ: {total_cost:,} تومان\n\n"
            f"لطفاً مبلغ را به کارت زیر واریز و سپس **عکس رسید** را ارسال کنید:\n"
            f"`{payment_card}`\n"
            f"**به نام:** {card_holder}")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    return AWAIT_RECEIPT

async def await_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("لطفا فقط عکس رسید را ارسال کنید."); return AWAIT_RECEIPT
    user = update.effective_user
    amount, cost = context.user_data.pop('purchase_amount', 0), context.user_data.pop('purchase_cost', 0)
    if amount == 0: return ConversationHandler.END
    con, cur = db_connect()
    cur.execute("INSERT INTO transactions (user_id, amount_diamonds, amount_toman, receipt_file_id) VALUES (?, ?, ?, ?)",
                (user.id, amount, cost, update.message.photo[-1].file_id))
    transaction_id = cur.lastrowid
    con.commit(); con.close()
    await update.message.reply_text("✅ رسید شما دریافت شد. منتظر تایید ادمین باشید.", reply_markup=await main_reply_keyboard(user.id))
    caption = (f" رسید جدید برای تایید\nکاربر: {get_user_handle(user)} (ID: `{user.id}`)\n"
               f"تعداد الماس: {amount}\nمبلغ: {cost:,} تومان")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید", callback_data=f"approve_{transaction_id}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{transaction_id}")]])
    for admin_id in get_admins():
        try: await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e: logger.error(f"Failed to send receipt to admin {admin_id}: {e}")
    return ConversationHandler.END

async def handle_transaction_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    action, transaction_id = query.data.split("_")
    con, cur = db_connect(); cur.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)); tx = cur.fetchone(); con.close()
    if not tx or tx['status'] != 'pending':
        await query.edit_message_caption(caption="این تراکنش قبلاً پردازش شده است."); return
    user_id, amount = tx['user_id'], tx['amount_diamonds']
    if action == "approve":
        update_user_balance(user_id, amount, add=True)
        new_status, user_msg, admin_caption = 'approved', f"✅ درخواست شما تایید شد و {amount} الماس به حسابتان اضافه گردید.", f"✅ تراکنش تایید شد."
    else: new_status, user_msg, admin_caption = 'rejected', "❌ درخواست شما توسط ادمین رد شد.", "❌ تراکنش رد شد."
    con, cur = db_connect(); cur.execute("UPDATE transactions SET status = ?, approved_by = ? WHERE id = ?", (new_status, query.from_user.id, transaction_id)); con.commit(); con.close()
    await query.edit_message_caption(caption=admin_caption)
    try: await context.bot.send_message(user_id, user_msg)
    except Exception as e: logger.warning(f"Could not notify user {user_id}: {e}")

async def admin_panel_entry_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("شما دسترسی به این بخش را ندارید."); return ConversationHandler.END
    
    is_channel_lock_enabled = get_setting("mandatory_channel_enabled") == 'true'
    channel_lock_text = "✅ قفل کانال: فعال" if is_channel_lock_enabled else "❌ قفل کانال: غیرفعال"
    keyboard = [
        [InlineKeyboardButton("💎 تنظیم قیمت الماس", callback_data="admin_set_price")],
        [InlineKeyboardButton("💰 تنظیم موجودی اولیه", callback_data="admin_set_initial_balance")],
        [InlineKeyboardButton("🚀 تنظیم هزینه سلف", callback_data="admin_set_self_cost")],
        [InlineKeyboardButton("🎁 تنظیم پاداش دعوت", callback_data="admin_set_referral_reward")],
        [InlineKeyboardButton("💳 تنظیم شماره کارت", callback_data="admin_set_payment_card")],
        [InlineKeyboardButton("📢 تنظیم کانال اجباری", callback_data="admin_set_channel")],
        [InlineKeyboardButton(channel_lock_text, callback_data="admin_toggle_channel_lock")],
    ]
    if user_id == OWNER_ID:
        keyboard.extend([
            [InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin_add")],
            [InlineKeyboardButton("➖ حذف ادمین", callback_data="admin_remove")]
        ])
    await update.message.reply_text("👑 به پنل ادمین خوش آمدید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_PANEL_MAIN

async def ask_for_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    setting_map = {
        "admin_set_price": ("diamond_price", "💎 قیمت جدید هر الماس را وارد کنید:", SETTING_PRICE),
        "admin_set_initial_balance": ("initial_balance", "💰 موجودی اولیه کاربران جدید را وارد کنید:", SETTING_INITIAL_BALANCE),
        "admin_set_self_cost": ("self_hourly_cost", "🚀 هزینه ساعتی سلف را وارد کنید:", SETTING_SELF_COST),
        "admin_set_referral_reward": ("referral_reward", "🎁 پاداش دعوت را وارد کنید:", SETTING_REFERRAL_REWARD),
        "admin_set_payment_card": (None, "💳 شماره کارت جدید را وارد کنید:", SETTING_PAYMENT_CARD),
        "admin_set_channel": ("mandatory_channel", "📢 آیدی کانال (با @) را وارد کنید:", SETTING_CHANNEL_LINK),
        "admin_add": (None, "➕ آیدی عددی ادمین جدید را وارد کنید:", ADMIN_ADD),
        "admin_remove": (None, f"➖ آیدی عددی ادمینی که می‌خواهید حذف کنید را وارد کنید.\n\nلیست ادمین‌ها:\n`{get_admins()}`", ADMIN_REMOVE)
    }
    data = query.data
    if data not in setting_map: return ADMIN_PANEL_MAIN
    setting_key, prompt, next_state = setting_map[data]
    if setting_key: context.user_data["setting_key"] = setting_key
    await query.edit_message_text(prompt, parse_mode=ParseMode.MARKDOWN); return next_state

async def receive_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    setting_key = context.user_data.pop("setting_key", None)
    if not setting_key: return ConversationHandler.END
    update_setting(setting_key, new_value)
    await update.message.reply_text("✅ تنظیمات ذخیره شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def receive_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment_card'] = update.message.text
    await update.message.reply_text("نام صاحب کارت را وارد کنید:")
    return SETTING_CARD_HOLDER

async def receive_card_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    card_number = context.user_data.pop('payment_card')
    card_holder = update.message.text
    update_setting('payment_card', card_number)
    update_setting('payment_card_holder', card_holder)
    await update.message.reply_text("✅ اطلاعات کارت با موفقیت ذخیره شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: admin_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید."); return ADMIN_ADD
    if admin_id == OWNER_ID:
        await update.message.reply_text("نمی‌توانید ادمین اصلی را اضافه کنید."); return ConversationHandler.END
    con, cur = db_connect()
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    con.commit(); con.close()
    await update.message.reply_text(f"✅ کاربر {admin_id} با موفقیت به لیست ادمین‌ها اضافه شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try: admin_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید."); return ADMIN_REMOVE
    if admin_id == OWNER_ID:
        await update.message.reply_text("نمی‌توانید ادمین اصلی را حذف کنید."); return ConversationHandler.END
    con, cur = db_connect()
    cur.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
    con.commit(); con.close()
    await update.message.reply_text(f"✅ کاربر {admin_id} با موفقیت از لیست ادمین‌ها حذف شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def toggle_channel_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    new_state = "false" if get_setting("mandatory_channel_enabled") == "true" else "true"
    update_setting("mandatory_channel_enabled", new_state)
    await query.answer(f"قفل کانال {'فعال' if new_state == 'true' else 'غیرفعال'} شد.")
    await query.message.delete()
    mock_update = Update(update.update_id, message=query.message)
    mock_update.effective_user = query.from_user
    
    await admin_panel_entry_text(mock_update, context)
    return ADMIN_PANEL_MAIN
    
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا پیام خود را برای ارسال به پشتیبانی بنویسید.", reply_markup=ReplyKeyboardRemove())
    return AWAITING_SUPPORT_MESSAGE

async def forward_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.", reply_markup=await main_reply_keyboard(user.id))
    forward_text = (f"📩 **پیام جدید**\nاز: {get_user_handle(user)} (`{user.id}`)\n\n{update.message.text}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ پاسخ", callback_data=f"reply_to_{user.id}")]])
    for admin_id in get_admins():
        try: await context.bot.send_message(admin_id, forward_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e: logger.error(f"Failed to forward support msg to admin {admin_id}: {e}")
    return ConversationHandler.END

async def ask_for_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    user_id_to_reply = int(query.data.split("_")[-1])
    context.user_data['reply_to_user_id'] = user_id_to_reply
    await query.edit_message_text(f"{query.message.text}\n\n---\nلطفا پاسخ خود را بنویسید.", reply_markup=None)
    return AWAITING_ADMIN_REPLY

async def send_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data.pop('reply_to_user_id', None)
    if not user_id: return ConversationHandler.END
    try:
        await context.bot.send_message(user_id, f"📨 **پاسخ پشتیبانی:**\n\n{update.message.text}")
        await update.message.reply_text("✅ پاسخ شما با موفقیت ارسال شد.")
    except Exception as e: await update.message.reply_text(f"خطا در ارسال پیام: {e}")
    return ConversationHandler.END

@channel_membership_required
async def check_balance_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    toman_equivalent = user_data['balance'] * int(get_setting("diamond_price"))
    text = (f"👤 کاربر: <b>{get_user_handle(update.effective_user)}</b>\n"
            f"💎 موجودی الماس: <b>{user_data['balance']}</b>\n"
            f"💳 معادل تخمینی: <b>{toman_equivalent:,} تومان</b>")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

@channel_membership_required
async def referral_menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={update.effective_user.id}"
    reward = get_setting("referral_reward")
    text = (f"🔗 لینک دعوت شما:\n`{referral_link}`\n\nبا هر دعوت موفق {reward} الماس هدیه بگیرید.")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# --- Flask Web App for Login ---
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ورود به حساب تلگرام</title><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background-color:#f4f4f9;color:#333;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.container{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1);text-align:center;max-width:400px;width:90%}h1{color:#007bff}p{color:#555;line-height:1.6}label{color:#555}input{width:100%;padding:12px;margin:10px 0 20px;border:1px solid #ddd;border-radius:8px;box-sizing:border-box}button{background-color:#007bff;color:#fff;padding:12px 20px;border:none;border-radius:8px;cursor:pointer;font-size:16px;transition:background-color .3s}button:hover{background-color:#0056b3}.error-box{background-color:#f8d7da;color:#721c24;border:1px solid #f5c6cb;padding:1rem;margin-top:1.5rem;border-radius:8px;text-align:center}</style></head><body><div class="container"><h1>{{ title }}</h1><p>{{ message }}</p>{% if form_html %}{{ form_html|safe }}{% endif %}{% if error %}<div class="error-box"><p>{{ error }}</p></div>{% endif %}</div></body></html>
"""
@web_app.route('/')
def index(): return "Bot is running!"

@web_app.route('/login/<token>')
def login_page(token):
    async def worker():
        logger.info(f"Login attempt started for token: {token}")
        if token not in LOGIN_SESSIONS or LOGIN_SESSIONS[token].get('step') != 'start':
            logger.warning(f"Invalid, used, or expired token received: {token}")
            return render_template_string(HTML_TEMPLATE, title="لینک منقضی شده", message="این لینک ورود نامعتبر یا منقضی شده است.", error="لطفاً به ربات بازگشته و فرآیند را از ابتدا شروع کنید تا یک لینک جدید دریافت نمایید.")

        # Lock the session to prevent re-entry
        LOGIN_SESSIONS[token]['step'] = 'processing_send_code'

        phone = LOGIN_SESSIONS[token]['phone']
        user_id = LOGIN_SESSIONS[token]['user_id']
        client_name = f"login_{user_id}_{token[:8]}"
        client = Client(name=client_name, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        LOGIN_SESSIONS[token]['client'] = client
        
        error_message = None
        try:
            logger.info(f"Connecting client for user {user_id}...")
            await asyncio.wait_for(client.connect(), timeout=20.0)
            
            logger.info(f"Client connected. Sending code to {phone} for user {user_id}.")
            sent_code = await asyncio.wait_for(client.send_code(phone), timeout=20.0)
            
            logger.info(f"Code sent successfully to {phone} for user {user_id}.")
            LOGIN_SESSIONS[token]['phone_code_hash'] = sent_code.phone_code_hash
            LOGIN_SESSIONS[token]['step'] = 'awaiting_code'
            form = f'<form method="post" action="/submit_code/{token}"><label for="code">کد تایید:</label><input type="text" id="code" name="code" required><button type="submit">تایید کد</button></form>'
            return render_template_string(HTML_TEMPLATE, title="مرحله ۱: کد تایید", message=f"کدی که به تلگرام شما برای شماره {phone} ارسال شد را وارد کنید.", form_html=form)
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout occurred during login process for user {user_id} with token {token}.")
            error_message = "اتصال به سرورهای تلگرام بیش از حد طول کشید. این لینک منقضی شد. لطفاً به ربات برگردید و دوباره تلاش کنید."
        except Exception as e:
            logger.error(f"Web login error (send_code) for user {user_id} with token {token}: {e}", exc_info=True)
            error_message = f"در فرآیند ارسال کد خطایی رخ داد: ({type(e).__name__}). این لینک منقضی شد. لطفاً به ربات برگردید و دوباره تلاش کنید."

        # This part runs ONLY if an exception was caught
        if client.is_connected:
            await client.disconnect()
        LOGIN_SESSIONS.pop(token, None) # Invalidate the token
        return render_template_string(HTML_TEMPLATE, title="خطا در ارتباط", message="عملیات با مشکل مواجه شد.", error=error_message)

    if hasattr(web_app, 'loop') and web_app.loop.is_running():
        future = asyncio.run_coroutine_threadsafe(worker(), web_app.loop)
        try:
            return future.result(timeout=45) # Add a generous timeout
        except Exception as e:
            logger.error(f"Error getting result from Flask worker future: {e}")
            return "خطای داخلی سرور هنگام پردازش درخواست.", 500
    
    logger.error("Main event loop is not available or not running for Flask handler.")
    return "خطای داخلی سرور: حلقه رویداد در دسترس نیست.", 500


async def activation_callback(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data['user_id']
    session_string = context.job.data['session_string']
    await complete_self_pro_activation(user_id, session_string)

@web_app.route('/submit_code/<token>', methods=['POST'])
def submit_code(token):
    async def worker():
        if token not in LOGIN_SESSIONS or LOGIN_SESSIONS[token].get('step') != 'awaiting_code': 
            return render_template_string(HTML_TEMPLATE, title="خطا", message="جلسه نامعتبر یا منقضی شده است.", error="لطفاً به ربات برگردید و دوباره تلاش کنید.")

        code = request.form['code']
        session_data = LOGIN_SESSIONS[token]
        client = session_data['client']
        
        try:
            await asyncio.wait_for(client.sign_in(session_data['phone'], session_data['phone_code_hash'], code), timeout=20.0)
            
            session_string = await client.export_session_string()
            user_id = session_data['user_id']
            
            application.job_queue.run_once(
                activation_callback, when=0, 
                data={'user_id': user_id, 'session_string': session_string}
            )
            
            return render_template_string(HTML_TEMPLATE, title="موفقیت!", message="عملیات با موفقیت انجام شد. لطفاً به ربات در تلگرام برگردید. نتیجه نهایی آنجا به شما اعلام خواهد شد.")
        
        except SessionPasswordNeeded:
            LOGIN_SESSIONS[token]['step'] = 'awaiting_password'
            form = f'<form method="post" action="/submit_password/{token}"><label for="password">رمز تایید دو مرحله‌ای:</label><input type="password" id="password" name="password" required><button type="submit">تایید رمز</button></form>'
            return render_template_string(HTML_TEMPLATE, title="مرحله ۲: تایید دو مرحله‌ای", message="حساب شما دارای رمز عبور است. آن را وارد کنید.", form_html=form)
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout occurred during sign_in for token {token}.")
            error_message = "تایید کد بیش از حد طول کشید. این لینک منقضی شد."
        except Exception as e:
            logger.error(f"Web login error (sign_in) for token {token}: {e}", exc_info=True)
            error_message = "کد وارد شده اشتباه است یا خطای دیگری رخ داد. این لینک منقضی شد."

        # Cleanup on error
        if client.is_connected: await client.disconnect()
        del LOGIN_SESSIONS[token]
        return render_template_string(HTML_TEMPLATE, title="خطا", message="عملیات ناموفق بود.", error=error_message + " لطفاً به ربات برگردید و دوباره تلاش کنید.")
        
    if hasattr(web_app, 'loop') and web_app.loop.is_running():
        future = asyncio.run_coroutine_threadsafe(worker(), web_app.loop)
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error getting result from Flask worker future: {e}")
            return "خطای داخلی سرور هنگام پردازش درخواست.", 500
    
    logger.error("Main event loop is not available or not running for Flask handler.")
    return "خطای داخلی سرور: حلقه رویداد در دسترس نیست.", 500


@web_app.route('/submit_password/<token>', methods=['POST'])
def submit_password(token):
    async def worker():
        if token not in LOGIN_SESSIONS or LOGIN_SESSIONS[token].get('step') != 'awaiting_password': 
            return render_template_string(HTML_TEMPLATE, title="خطا", message="جلسه نامعتبر یا منقضی شده است.", error="لطفاً به ربات برگردید و دوباره تلاش کنید.")
            
        password = request.form['password']
        client = LOGIN_SESSIONS[token]['client']

        try:
            await asyncio.wait_for(client.check_password(password), timeout=20.0)

            session_string = await client.export_session_string()
            user_id = LOGIN_SESSIONS[token]['user_id']

            application.job_queue.run_once(
                activation_callback, when=0,
                data={'user_id': user_id, 'session_string': session_string}
            )
            
            return render_template_string(HTML_TEMPLATE, title="موفقیت!", message="عملیات با موفقیت انجام شد. لطفاً به ربات در تلگرام برگردید. نتیجه نهایی آنجا به شما اعلام خواهد شد.")
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout occurred during check_password for token {token}.")
            error_message = "تایید رمز بیش از حد طول کشید. این لینک منقضی شد."
        except Exception as e:
            logger.error(f"Web login error (check_password) for token {token}: {e}", exc_info=True)
            error_message = "رمز عبور وارد شده اشتباه بود. این لینک منقضی شد."

        # Cleanup on error
        if client.is_connected: await client.disconnect()
        del LOGIN_SESSIONS[token]
        return render_template_string(HTML_TEMPLATE, title="خطا", message="عملیات ناموفق بود.", error=error_message + " لطفاً به ربات برگردید و دوباره تلاش کنید.")

    if hasattr(web_app, 'loop') and web_app.loop.is_running():
        future = asyncio.run_coroutine_threadsafe(worker(), web_app.loop)
        try:
            return future.result(timeout=30)
        except Exception as e:
            logger.error(f"Error getting result from Flask worker future: {e}")
            return "خطای داخلی سرور هنگام پردازش درخواست.", 500
    
    logger.error("Main event loop is not available or not running for Flask handler.")
    return "خطای داخلی سرور: حلقه رویداد در دسترس نیست.", 500


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

def main_sync() -> None:
    global application
    setup_database()
    persistence = PicklePersistence(filepath=os.path.join(DATA_PATH, "bot_persistence.pickle"))
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    application.add_error_handler(error_handler)

    self_pro_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🚀 Self Pro$'), self_pro_start)],
        states={
            AWAIT_CONTACT: [MessageHandler(filters.CONTACT, self_pro_receive_contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)], persistent=False, name="self_pro_login_conversation"
    )
    main_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^💰 افزایش موجودی$'), buy_diamond_start_text),
            MessageHandler(filters.Regex('^👑 پنل ادمین$'), admin_panel_entry_text),
            MessageHandler(filters.Regex('^💬 پشتیبانی$'), support_start),
            CallbackQueryHandler(ask_for_reply, pattern=r"^reply_to_")
        ],
        states={
            ASK_DIAMOND_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_diamond_amount)],
            AWAIT_RECEIPT: [MessageHandler(filters.PHOTO, await_receipt)],
            ADMIN_PANEL_MAIN: [
                CallbackQueryHandler(ask_for_setting, pattern=r"admin_set_|admin_add|admin_remove"),
                CallbackQueryHandler(toggle_channel_lock, pattern=r"^admin_toggle_channel_lock$")
            ],
            SETTING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_INITIAL_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_SELF_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_REFERRAL_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_PAYMENT_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_payment_card)],
            SETTING_CARD_HOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_card_holder)],
            SETTING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            ADMIN_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin)],
            ADMIN_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin)],
            AWAITING_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message_to_admin)],
            AWAITING_ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_reply_to_user)]
        },
        fallbacks=[CommandHandler("cancel", cancel)], persistent=True, name="main_conversation"
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(self_pro_conv); application.add_handler(main_conv)
    application.add_handler(CallbackQueryHandler(handle_transaction_approval, pattern=r"^(approve|reject)_\d+$"))
    application.add_handler(CallbackQueryHandler(toggle_self_pause, pattern=r"^self_(pause|resume)$"))
    application.add_handler(CallbackQueryHandler(change_font_menu, pattern=r"^change_font_menu$"))
    application.add_handler(CallbackQueryHandler(set_font, pattern=r"^set_font_"))
    application.add_handler(CallbackQueryHandler(back_to_self_menu, pattern=r"^back_to_self_menu$"))
    application.add_handler(CallbackQueryHandler(delete_self_confirm, pattern=r"^delete_self_confirm$"))
    application.add_handler(CallbackQueryHandler(delete_self_final, pattern=r"^delete_self_final$"))
    application.add_handler(CallbackQueryHandler(reactivate_self_pro, pattern=r"^reactivate_self$"))
    application.add_handler(MessageHandler(filters.Regex('^💎 موجودی$'), check_balance_text_handler))
    application.add_handler(MessageHandler(filters.Regex('^🎁 کسب جم رایگان$'), referral_menu_text_handler))
    
    # --- Add Group Handlers ---
    application.add_handler(CommandHandler("bet", start_bet, filters=filters.ChatType.GROUPS))
    application.add_handler(CallbackQueryHandler(join_bet, pattern=r"^join_bet_"))
    application.add_handler(CallbackQueryHandler(cancel_bet, pattern=r"^cancel_bet_"))
    application.add_handler(MessageHandler(filters.REPLY & filters.ChatType.GROUPS & filters.Regex(r'^(انتقال الماس\s*\d+|\d+)$'), handle_transfer))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, group_text_handler))
    
    logger.info("Bot is initializing...")
    # The application is returned to be run by the main async context
    return application


if __name__ == "__main__":
    if os.path.exists(LOCK_FILE_PATH): 
        logger.critical(f"Lock file exists. Exiting.")
        sys.exit(0)
    
    try:
        with open(LOCK_FILE_PATH, "w") as f: f.write(str(os.getpid()))
        atexit.register(lambda: os.path.exists(LOCK_FILE_PATH) and os.remove(LOCK_FILE_PATH))
        
        # Build the application
        app = main_sync()
        
        # Get the event loop that PTB will use
        loop = asyncio.get_event_loop()
        web_app.loop = loop # Make it accessible to the Flask thread
        
        flask_thread = Thread(target=lambda: web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))))
        flask_thread.daemon = True
        flask_thread.start()
        
        # Run the bot on the event loop
        logger.info("Bot is starting polling...")
        loop.run_until_complete(app.run_polling(drop_pending_updates=True))

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually or due to conflict.")
    finally:
        # Gracefully stop all running user sessions before closing the loop
        if user_sessions:
            logger.info("Cleaning up active user sessions...")
            cleanup_tasks = [clean_up_user_session(user_id) for user_id in list(user_sessions.keys())]
            loop.run_until_complete(asyncio.gather(*cleanup_tasks))
            logger.info("All user sessions cleaned up.")

        if os.path.exists(LOCK_FILE_PATH): 
            os.remove(LOCK_FILE_PATH)
        
        logger.info("Closing the event loop.")
        loop.close()

