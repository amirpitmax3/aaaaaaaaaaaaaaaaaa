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

# کتابخانه برای بخش dark self (Userbot)
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
from pyrogram.enums import ChatType
from apscheduler.jobstores.base import JobLookupError


# تنظیمات لاگ‌گیری برای دیباگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error detected. This instance will stop polling gracefully.")
        await context.application.stop()
        return
    logger.error(f"Exception while handling an update:", exc_info=context.error)
    


# --- بخش وب سرور برای Ping و لاگین ---
web_app = Flask(__name__)
WEB_APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:10000") 
LOGIN_SESSIONS = {}

# --- متغیرهای ربات ---
TELEGRAM_TOKEN = "8233582209:AAHKPQX-349tAfBOCFWbRRqcpD-QbVrDzQ0"
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
    AWAIT_PHONE_CONTACT, AWAIT_SESSION_STRING,
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
AUTO_SEEN_STATUS = {}
AUTO_BOLD_STATUS = {}
AUTO_REACTION_STATUS = {}


# --- مدیریت دیتابیس (SQLite) ---
def db_connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_deduction_at TIMESTAMP
        )
    """)
    try: cur.execute("ALTER TABLE users ADD COLUMN last_deduction_at TIMESTAMP")
    except sqlite3.OperationalError: pass
    
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
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    old_balance = row['balance'] if row else 'NOT FOUND'
    
    operator = '+' if add else '-'
    cur.execute(f"UPDATE users SET balance = balance {operator} ? WHERE user_id = ?", (amount, user_id))
    con.commit()
    
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    new_balance = row['balance'] if row else 'NOT FOUND'
    con.close()
    logger.info(f"Balance update for user {user_id}: Old={old_balance}, Amount={' + ' if add else ' - '}{amount}, New={new_balance}")


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
    keyboard = [[KeyboardButton("💎 موجودی"), KeyboardButton("🚀 dark self")]]
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
    sample_time = "12:30" # Example time for font preview
    for style, name in [('normal', 'Normal'), ('monospace', 'Monospace'), ('doublestruck', 'Doublestruck'), ('stylized', 'Stylized'), ('cursive', 'Cursive')]:
        check_mark = "✅ " if user_font == style else ""
        example_time = stylize_time(sample_time, style)
        text = f"{check_mark}{name}  ({example_time})"
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
                    logger.info(f"Referral success: User {user.id} was referred by {referrer_id}. Granting {reward} gems.")
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
        f"سلام {user.first_name}! به ربات dark self خوش آمدید.", reply_markup=await main_reply_keyboard(user.id)
    )
    return ConversationHandler.END

# --- dark self Activation Flow ---
user_sessions = {}

@channel_membership_required
async def self_pro_menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_db = get_user(user_id)
    if user_db['self_active']:
        await update.message.reply_text("⚙️ منوی مدیریت dark self:", reply_markup=await self_pro_management_keyboard(user_id))
        return ConversationHandler.END
    hourly_cost = int(get_setting("self_hourly_cost"))
    if user_db['balance'] < hourly_cost:
        await update.message.reply_text(f"برای فعال سازی سلف، حداقل باید {hourly_cost} الماس موجودی داشته باشید.")
        return ConversationHandler.END

    keyboard = [[KeyboardButton("📱 اشتراک گذاری شماره تلفن", request_contact=True)]]
    await update.message.reply_text(
        "برای شروع فرآیند ورود، لطفاً شماره تلفن خود را از طریق دکمه زیر به اشتراک بگذارید.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return AWAIT_PHONE_CONTACT

async def receive_phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    phone_number = f"+{update.message.contact.phone_number.lstrip('+')}"
    
    login_token = secrets.token_urlsafe(16)
    # Store user_id and the received phone number
    LOGIN_SESSIONS[login_token] = {'user_id': user_id, 'step': 'start', 'phone': phone_number}
    login_url = f"{WEB_APP_URL}/login/{login_token}"

    text = (f"✅ شماره شما دریافت شد.\n\n"
            f"**برای ادامه، روی لینک ورود امن زیر کلیک کنید:**\n\n🔗 [لینک ورود امن]({login_url})\n\n"
            "پس از اتمام مراحل، Session String خود را کپی کرده و در همین چت ارسال کنید.")
            
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    return AWAIT_SESSION_STRING


async def process_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session_string = update.message.text.strip()
    await update.message.reply_text("در حال بررسی Session String... لطفاً صبر کنید.")
    try:
        client = Client(name=f"verify_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        await client.start()
        me = await client.get_me()
        await client.stop()
        
        # Set last_deduction_at to current time on first activation
        update_user_db(user_id, "last_deduction_at", datetime.now(TEHRAN_TIMEZONE))
        update_user_db(user_id, "base_first_name", me.first_name)
        update_user_db(user_id, "base_last_name", me.last_name or "")
        update_user_db(user_id, "self_active", True)
        update_user_db(user_id, "session_string", session_string)
        
        permanent_client = Client(name=f"user_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        
        # --- Add all feature handlers ---
        add_all_handlers(permanent_client)
        
        user_sessions[user_id] = permanent_client
        asyncio.create_task(self_pro_background_task(user_id, permanent_client, application))
        await update.message.reply_text("✅ dark self با موفقیت فعال شد! اکنون می‌توانید آن را مدیریت کنید:", reply_markup=await self_pro_management_keyboard(user_id))
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Failed to activate self with session string for {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Session String نامعتبر است یا خطایی رخ داد: `{e}`", parse_mode=ParseMode.MARKDOWN)
        return AWAIT_SESSION_STRING

async def self_pro_background_task(user_id: int, client: Client, application: Application):
    try:
        if not client.is_connected: await client.start()
        while user_id in user_sessions:
            user = get_user(user_id)
            if not user or not user['self_active']: break
            
            if not user['self_paused']:
                now = datetime.now(TEHRAN_TIMEZONE)
                last_deduction = user['last_deduction_at']
                
                if isinstance(last_deduction, str):
                    last_deduction = datetime.fromisoformat(last_deduction)
                if not last_deduction or not last_deduction.tzinfo:
                     last_deduction = now.replace(tzinfo=TEHRAN_TIMEZONE)

                if now - last_deduction >= timedelta(hours=1):
                    hourly_cost = int(get_setting("self_hourly_cost"))
                    if user['balance'] < hourly_cost:
                        await deactivate_self_pro(user_id, client, application, reason="موجودی جم شما برای تمدید ساعت کافی نیست.")
                        break 
                    update_user_balance(user_id, hourly_cost, add=False)
                    update_user_db(user_id, "last_deduction_at", now)
                    logger.info(f"Deducted {hourly_cost} gems from user {user_id}. Next deduction in 1 hour.")

                now_str = now.strftime("%H:%M")
                styled_time = stylize_time(now_str, user['font_style'])
                try: 
                    current_name = user['base_first_name']
                    cleaned_name = re.sub(r'\s[\d🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿𝟘𝟙𚼉🛩𝟜𝟝𝟞𝟟𝟠𝟡𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗]{1,2}:[\d🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿𝟘𝟙𚼉🛩𝟜𝟝𝟞𝟟𝟠𝟡𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗]{2}$', '', current_name).strip()
                    await client.update_profile(first_name=f"{cleaned_name} {styled_time}")
                except FloodWait as e:
                    logger.warning(f"FloodWait for {user_id}: sleeping for {e.value} seconds.")
                    await asyncio.sleep(e.value)
                except Exception as e: logger.error(f"Failed to update profile for {user_id}: {e}")
            
            # --- PRECISE SLEEP CALCULATION ---
            now_for_sleep = datetime.now(TEHRAN_TIMEZONE)
            seconds_until_next_minute = 60 - now_for_sleep.second
            await asyncio.sleep(seconds_until_next_minute + 0.1) # Add a small buffer

    except Exception as e: logger.error(f"Critical error in self_pro_background_task for {user_id}: {e}", exc_info=True)
    finally:
        await clean_up_user_session(user_id)
        
async def deactivate_self_pro(user_id: int, client: Client, application: Application, reason: str):
    """Function to deactivate self pro for any reason."""
    logger.info(f"Deactivating self pro for user {user_id}. Reason: {reason}")
    await clean_up_user_session(user_id)
    update_user_db(user_id, "self_active", False)
    update_user_db(user_id, "self_paused", False)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("فعالسازی مجدد", callback_data="reactivate_self")]])
    await application.bot.send_message(user_id, f"{reason} سلف شما غیرفعال گردید.", reply_markup=keyboard)


async def clean_up_user_session(user_id: int):
    """Safely stop client and clean up all related data."""
    client = user_sessions.pop(user_id, None)
    if client and client.is_connected:
        try:
            # Restore original name before stopping
            user_data = get_user(user_id)
            if user_data and user_data['base_first_name']:
                 await client.update_profile(first_name=user_data['base_first_name'], last_name=user_data['base_last_name'] or "")
        except Exception as e:
            logger.error(f"Could not restore name for user {user_id} on cleanup: {e}")
        finally:
             await client.stop()

    # Clean up all feature states
    for status_dict in [ACTIVE_ENEMIES, ENEMY_REPLY_QUEUES, OFFLINE_MODE_STATUS, USERS_REPLIED_IN_OFFLINE, AUTO_SEEN_STATUS, AUTO_BOLD_STATUS, AUTO_REACTION_STATUS]:
        status_dict.pop(user_id, None)
    logger.info(f"Cleaned up session and features for user {user_id}.")


async def reactivate_self_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await self_pro_menu_text_handler(query.message, context)


# --- Feature Handlers ---

def add_all_handlers(client: Client):
    # Group 0: User's own immediate commands
    command_handlers = {
        r"^(دشمن فعال|دشمن خاموش)$": enemy_controller,
        r"^(افلاین روشن|افلاین خاموش)$": offline_mode_controller,
        r"^(بلاک روشن|بلاک خاموش)$": block_controller,
        r"^(سکوت روشن|سکوت خاموش)$": mute_controller,
        r"^ذخیره$": save_message_handler,
        r"^تکرار\s\d+$": repeat_message_handler,
        r"^ریاکشن\s.+$": reaction_controller,
        r"^ریاکشن خاموش$": reaction_controller,
        r"^(سین روشن|سین خاموش)$": auto_seen_controller,
        r"^(بولد روشن|بولد خاموش)$": auto_bold_controller,
        r"^(ساعت روشن|ساعت خاموش)$": clock_controller,
        r"^فونت.*$": font_controller,
    }
    for regex, handler in command_handlers.items():
        client.add_handler(PyrogramMessageHandler(handler, pyrogram_filters.text & pyrogram_filters.reply & pyrogram_filters.me & pyrogram_filters.regex(regex)), group=0)
    
    # Handlers that don't need a reply
    no_reply_handlers = {
        r"^(افلاین روشن|افلاین خاموش)$": offline_mode_controller,
        r"^(سین روشن|سین خاموش)$": auto_seen_controller,
        r"^(بولد روشن|بولد خاموش)$": auto_bold_controller,
        r"^(ساعت روشن|ساعت خاموش)$": clock_controller,
        r"^فونت.*$": font_controller,
    }
    for regex, handler in no_reply_handlers.items():
        client.add_handler(PyrogramMessageHandler(handler, pyrogram_filters.text & pyrogram_filters.me & pyrogram_filters.regex(regex)), group=0)

    # Group 1: Media handlers on incoming messages
    client.add_handler(PyrogramMessageHandler(auto_save_timed_photo_handler, pyrogram_filters.photo & pyrogram_filters.private & ~pyrogram_filters.me), group=1)
    
    # Group 2 for incoming text messages
    client.add_handler(PyrogramMessageHandler(enemy_handler, pyrogram_filters.text & (pyrogram_filters.group | pyrogram_filters.private) & ~pyrogram_filters.me), group=2)
    client.add_handler(PyrogramMessageHandler(offline_auto_reply_handler, pyrogram_filters.text & pyrogram_filters.private & ~pyrogram_filters.me), group=2)

    # Group 5: Post-processing handlers for incoming messages
    client.add_handler(PyrogramMessageHandler(auto_seen_processor, pyrogram_filters.incoming & pyrogram_filters.private & ~pyrogram_filters.me), group=5)
    client.add_handler(PyrogramMessageHandler(auto_reaction_processor, pyrogram_filters.incoming & ~pyrogram_filters.me), group=5)
    
    # Group 6: Outgoing message handlers
    client.add_handler(PyrogramMessageHandler(auto_bold_processor, pyrogram_filters.outgoing & pyrogram_filters.text), group=6)


async def auto_seen_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "سین روشن":
        AUTO_SEEN_STATUS[user_id] = True
        await message.edit_text("👁 **سین خودکار فعال شد.**")
    elif command == "سین خاموش":
        AUTO_SEEN_STATUS[user_id] = False
        await message.edit_text("👁 **سین خودکار خاموش شد.**")

async def auto_seen_processor(client, message):
    owner_user_id = client.me.id
    if AUTO_SEEN_STATUS.get(owner_user_id, False) and message.chat.type == ChatType.PRIVATE:
        try:
            await client.read_chat_history(message.chat.id)
        except Exception: pass

async def auto_bold_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "بولد روشن":
        AUTO_BOLD_STATUS[user_id] = True
        await message.edit_text("**حالت بولد خودکار فعال شد.**")
    elif command == "بولد خاموش":
        AUTO_BOLD_STATUS[user_id] = False
        await message.edit_text("**حالت بولد خودکار خاموش شد.**")

async def auto_bold_processor(client, message):
    owner_user_id = client.me.id
    if AUTO_BOLD_STATUS.get(owner_user_id, False) and message.text and not message.text.startswith("**"):
        try:
            await message.edit_text(f"**{message.text}**", parse_mode=None)
        except Exception: pass

async def clock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "ساعت روشن":
        update_user_db(user_id, 'self_paused', False)
        update_user_db(user_id, "last_deduction_at", datetime.now(TEHRAN_TIMEZONE))
        await message.edit_text("⏰ **ساعت پروفایل فعال شد.**")
    elif command == "ساعت خاموش":
        update_user_db(user_id, 'self_paused', True)
        user_data = get_user(user_id)
        if user_data and user_data['base_first_name']:
             await client.update_profile(first_name=user_data['base_first_name'], last_name=user_data['base_last_name'] or "")
        await message.edit_text("⏰ **ساعت پروفایل خاموش شد.**")

async def font_controller(client, message):
    user_id = client.me.id
    parts = message.text.strip().split()
    font_map = [('cursive', 'Cursive'), ('stylized', 'Stylized'), ('doublestruck', 'Doublestruck'), ('monospace', 'Monospace'), ('normal', 'Normal')]
    if len(parts) == 1 and parts[0] == "فونت":
        reply_text = "لیست فونت‌های موجود:\n\n"
        for i, (style, name) in enumerate(font_map, 1):
            example = stylize_time("12:34", style)
            reply_text += f"`{i}`: {name} ({example})\n"
        reply_text += "\nبرای انتخاب، `فونت [عدد]` را ارسال کنید."
        await message.edit_text(reply_text)
    elif len(parts) == 2 and parts[0] == "فونت" and parts[1].isdigit():
        try:
            choice = int(parts[1])
            if 1 <= choice <= len(font_map):
                selected_style = font_map[choice - 1][0]
                update_user_db(user_id, 'font_style', selected_style)
                await message.edit_text(f"✅ فونت با موفقیت به **{font_map[choice - 1][1]}** تغییر یافت.")
            else:
                await message.edit_text("❌ عدد نامعتبر است.")
        except (ValueError, IndexError):
            await message.edit_text("❌ فرمت دستور اشتباه است.")
            
async def save_message_handler(client, message):
    if not message.reply_to_message: return
    try:
        await message.edit_text("... در حال ذخیره پیام")
        await message.reply_to_message.copy("me")
        await message.edit_text("✅ پیام با موفقیت در Saved Messages ذخیره شد.")
    except Exception as e:
        await message.edit_text(f"❌ خطا در ذخیره پیام: {e}")

async def repeat_message_handler(client, message):
    if not message.reply_to_message: return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.edit_text("فرمت اشتباه. مثال: `تکرار 15`"); return
    count = int(parts[1])
    if not 1 <= count <= 100:
        await message.edit_text("تعداد باید بین ۱ تا ۱۰۰ باشد."); return
    await message.delete()
    for _ in range(count):
        try:
            await message.reply_to_message.copy(message.chat.id)
            await asyncio.sleep(0.3)
        except FloodWait as e: await asyncio.sleep(e.value)
        except Exception as e: logger.error(f"Error repeating message: {e}"); break
        
async def reaction_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    owner_id, target_id, chat_id = client.me.id, message.reply_to_message.from_user.id, message.chat.id
    parts = message.text.strip().split()
    AUTO_REACTION_STATUS.setdefault(owner_id, {})
    if len(parts) == 2 and parts[0] == "ریاکشن":
        emoji = parts[1]
        AUTO_REACTION_STATUS[owner_id][(chat_id, target_id)] = emoji
        await message.edit_text(f"✅ واکنش خودکار با {emoji} برای این کاربر در این چت فعال شد.")
    elif len(parts) == 1 and parts[0] == "ریاکشن خاموش":
        if (chat_id, target_id) in AUTO_REACTION_STATUS[owner_id]:
            del AUTO_REACTION_STATUS[owner_id][(chat_id, target_id)]
            await message.edit_text("❌ واکنش خودکار غیرفعال شد.")
        else: await message.edit_text("واکنش خودکاری برای این کاربر فعال نیست.")

async def auto_reaction_processor(client, message):
    owner_id = client.me.id
    if owner_id not in AUTO_REACTION_STATUS or not message.from_user: return
    key = (message.chat.id, message.from_user.id)
    if key in AUTO_REACTION_STATUS[owner_id]:
        emoji = AUTO_REACTION_STATUS[owner_id][key]
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except Exception as e: logger.warning(f"Could not send reaction: {e}")

async def enemy_handler(client, message):
    user_id = client.me.id
    if not ACTIVE_ENEMIES.get(user_id): return
    enemy_list = ACTIVE_ENEMIES.get(user_id, set())
    if message.from_user and (message.from_user.id, message.chat.id) in enemy_list:
        if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
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
        await message.edit_text(f"❌ **حالت دشمن برای {target_user.first_name} در این چت خاموش شد.**")

async def offline_mode_controller(client, message):
    """Handles enabling/disabling offline mode for the user."""
    user_id = client.me.id
    command = message.text.strip()

    if command == "افلاین روشن":
        OFFLINE_MODE_STATUS[user_id] = True
        # Explicitly create a new set for the replied users for this session
        USERS_REPLIED_IN_OFFLINE[user_id] = set()
        logger.info(f"Offline mode ACTIVATED for user {user_id}.")
        await message.edit_text("✅ **حالت آفلاین فعال شد.** به هر کاربر فقط یک بار پاسخ داده می‌شود تا زمانی که این حالت خاموش و مجدداً روشن شود.")

    elif command == "افلاین خاموش":
        OFFLINE_MODE_STATUS[user_id] = False
        # The replied list will be cleared on next activation.
        logger.info(f"Offline mode DEACTIVATED for user {user_id}.")
        await message.edit_text("❌ **حالت آفلاین غیرفعال شد.**")


async def offline_auto_reply_handler(client, message):
    """Automatically replies to private messages if offline mode is on."""
    owner_user_id = client.me.id

    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return

    if OFFLINE_MODE_STATUS.get(owner_user_id, False):
        if owner_user_id not in USERS_REPLIED_IN_OFFLINE:
            USERS_REPLIED_IN_OFFLINE[owner_user_id] = set()

        replied_users_set = USERS_REPLIED_IN_OFFLINE[owner_user_id]
        sender_id = message.from_user.id

        if sender_id not in replied_users_set:
            try:
                await message.reply_text(OFFLINE_REPLY_MESSAGE)
                replied_users_set.add(sender_id)
                logger.info(f"Sent offline auto-reply from {owner_user_id} to {sender_id}.")
            except Exception as e:
                logger.warning(f"Could not auto-reply from {owner_user_id} to {sender_id}: {e}")
        else:
            logger.info(f"User {sender_id} already replied to by {owner_user_id}. Skipping.")

async def auto_save_timed_photo_handler(client, message):
    # Check if it's a photo with a TTL in a private chat from another user
    if message.photo and message.photo.ttl_seconds and message.chat.type == ChatType.PRIVATE:
        try:
            file_path = await client.download_media(message)
            # Send to "Saved Messages"
            await client.send_photo("me", file_path, caption=f"عکس زمان‌دار از {message.chat.first_name} به صورت خودکار ذخیره شد.")
            os.remove(file_path)
            logger.info(f"Automatically saved a timed photo from user {message.chat.id} for owner {client.me.id}")
        except Exception as e:
            logger.error(f"Could not auto-save timed photo for user {client.me.id}: {e}")

async def block_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return
    target_user = message.reply_to_message.from_user
    command = message.text.strip()
    try:
        if command == "بلاک روشن":
            await client.block_user(target_user.id)
            await message.edit_text(f"🚫 کاربر {target_user.first_name} با موفقیت بلاک شد.")
        elif command == "بلاک خاموش":
            await client.unblock_user(target_user.id)
            await message.edit_text(f"✅ کاربر {target_user.first_name} با موفقیت آنبلاک شد.")
    except Exception as e:
        await message.edit_text(f"خطا در اجرای دستور: {e}")
        logger.error(f"Error in block_controller for user {client.me.id}: {e}")

async def mute_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return
    target_user = message.reply_to_message.from_user
    command = message.text.strip()
    try:
        if command == "سکوت روشن":
            await client.archive_chats(target_user.id)
            await message.edit_text(f"🔇 کاربر {target_user.first_name} به حالت سکوت رفت (چت آرشیو شد).")
        elif command == "سکوت خاموش":
            await client.unarchive_chats(target_user.id)
            await message.edit_text(f"🔊 کاربر {target_user.first_name} از حالت سکوت خارج شد (چت از آرشیو خارج شد).")
    except Exception as e:
        await message.edit_text(f"خطا در اجرای دستور: {e}")
        logger.error(f"Error in mute_controller for user {client.me.id}: {e}")


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
    if new_state: # If paused
        await query.answer(f"ساعت با موفقیت متوقف شد.")
    else: # If resumed
        update_user_db(query.from_user.id, "last_deduction_at", datetime.now(TEHRAN_TIMEZONE))
        await query.answer(f"ساعت با موفقیت فعال شد.")

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
    await query.edit_message_text("⚙️ منوی مدیریت dark self:", reply_markup=await self_pro_management_keyboard(query.from_user.id))

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
    
    admin_list = get_admins()
    logger.info(f"Forwarding receipt to admins: {admin_list}")
    caption = (f" رسید جدید برای تایید\nکاربر: {get_user_handle(user)} (ID: `{user.id}`)\n"
               f"تعداد الماس: {amount}\nمبلغ: {cost:,} تومان")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تایید", callback_data=f"approve_{transaction_id}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{transaction_id}")]])
    for admin_id in admin_list:
        try: 
            await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"Successfully sent receipt to admin {admin_id}")
        except Exception as e: 
            logger.error(f"Failed to send receipt to admin {admin_id}: {e}")
    return ConversationHandler.END

async def handle_transaction_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    action, transaction_id = query.data.split("_")
    con, cur = db_connect(); cur.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)); tx = cur.fetchone(); con.close()
    if not tx or tx['status'] != 'pending':
        await query.edit_message_caption(caption="این تراکنش قبلاً پردازش شده است."); return
    
    user_id, amount = tx['user_id'], tx['amount_diamonds']
    logger.info(f"Processing transaction {transaction_id} for user {user_id} with amount {amount}. Action: {action}")

    if action == "approve":
        update_user_balance(user_id, amount, add=True)
        new_status, user_msg, admin_caption = 'approved', f"✅ درخواست شما تایید شد و {amount} الماس به حسابتان اضافه گردید.", f"✅ تراکنش تایید شد."
    else: 
        new_status, user_msg, admin_caption = 'rejected', "❌ درخواست شما توسط ادمین رد شد.", "❌ تراکنش رد شد."
        
    con, cur = db_connect(); cur.execute("UPDATE transactions SET status = ?, approved_by = ? WHERE id = ?", (new_status, query.from_user.id, transaction_id)); con.commit(); con.close()
    await query.edit_message_caption(caption=admin_caption)
    try: 
        await context.bot.send_message(user_id, user_msg)
    except Exception as e: 
        logger.warning(f"Could not notify user {user_id}: {e}")

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
        "admin_remove": (None, f"➖ آیدی عددی ادمینی که می‌خواهید حذف کنید را وارد کنید.\n\nلیست ادمین‌ها:\n`{get_admins()}`", ADMIN_REMOVE),
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
    # Re-show the admin panel
    await query.message.delete()
    # we need to pass an update object to the admin_panel_entry_text function
    # we can create a mock update object or pass the current one
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
    admin_list = get_admins()
    logger.info(f"Forwarding support message to admins: {admin_list}")
    forward_text = (f"📩 **پیام جدید**\nاز: {get_user_handle(user)} (`{user.id}`)\n\n{update.message.text}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ پاسخ", callback_data=f"reply_to_{user.id}")]])
    for admin_id in admin_list:
        try: 
            await context.bot.send_message(admin_id, forward_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"Successfully sent support message to admin {admin_id}")
        except Exception as e: 
            logger.error(f"Failed to forward support msg to admin {admin_id}: {e}")
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
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ورود به حساب تلگرام</title><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background-color:#f4f4f9;color:#333;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}.container{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.1);text-align:center;max-width:400px;width:90%}h1{color:#007bff}p,label{color:#555}input{width:100%;padding:12px;margin:10px 0 20px;border:1px solid #ddd;border-radius:8px;box-sizing:border-box}button{background-color:#007bff;color:#fff;padding:12px 20px;border:none;border-radius:8px;cursor:pointer;font-size:16px;transition:background-color .3s}button:hover{background-color:#0056b3}.session-box{background:#e9ecef;border:1px solid #ced4da;padding:15px;border-radius:8px;word-wrap:break-word;text-align:left;direction:ltr;margin-top:20px}.error{color:#dc3545;margin-bottom:15px}</style></head><body><div class="container"><h1>{{ title }}</h1><p>{{ message|safe }}</p>{% if error %}<p class="error">{{ error }}</p>{% endif %}{% if form_html %}{{ form_html|safe }}{% endif %}{% if session_string %}<h3>Session String با موفقیت ایجاد شد!</h3><p>این متن را کپی کرده و به ربات تلگرام خود ارسال کنید.</p><div class="session-box"><code>{{ session_string }}</code></div>{% endif %}</div></body></html>
"""
@web_app.route('/')
def index(): return "Bot is running!"
@web_app.route('/login/<token>')
def login_page(token):
    session_data = LOGIN_SESSIONS.get(token)
    if not session_data or session_data.get('step') != 'start':
        return render_template_string(HTML_TEMPLATE, title="خطا", message="لینک ورود نامعتبر یا منقضی شده است.")
    
    phone_number = session_data.get('phone')
    if not phone_number:
        form = f'<form method="post" action="/submit_phone/{token}"><label for="phone">شماره تلفن (مثال: +989123456789):</label><input type="text" id="phone" name="phone" required><button type="submit">ارسال کد</button></form>'
        return render_template_string(HTML_TEMPLATE, title="مرحله ۱: شماره تلفن", message="لطفاً شماره تلفن حساب تلگرام خود را وارد کنید.", form_html=form)
    else:
        form = f'<form method="post" action="/submit_phone/{token}"><button type="submit">ارسال کد تایید</button></form>'
        return render_template_string(HTML_TEMPLATE, title="مرحله ۱: تایید شماره", message=f"شماره شما <code>{phone_number}</code> است. برای ارسال کد، دکمه زیر را بزنید.", form_html=form)

@web_app.route('/submit_phone/<token>', methods=['POST'])
def submit_phone(token):
    async def worker():
        session_data = LOGIN_SESSIONS.get(token)
        if not session_data: return "لینک نامعتبر", 400
        
        phone = session_data.get('phone')
        if not phone:
            return render_template_string(HTML_TEMPLATE, title="خطا", message="خطای جلسه. لطفاً از ابتدا در ربات تلگرام شروع کنید.")

        client = Client(name=f"login_{token}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        session_data['client'] = client
        try:
            await client.connect()
            sent_code = await client.send_code(phone)
            session_data['phone_code_hash'] = sent_code.phone_code_hash
            session_data['step'] = 'awaiting_code'
            form = f'<form method="post" action="/submit_code/{token}"><label for="code">کد تایید:</label><input type="text" id="code" name="code" required><button type="submit">تایید کد</button></form>'
            return render_template_string(HTML_TEMPLATE, title="مرحله ۲: کد تایید", message=f"کدی که به تلگرام شما برای شماره {phone} ارسال شد را وارد کنید.", form_html=form)
        except Exception as e:
            logger.error(f"Web login error (send_code) for {token}: {e}"); await client.disconnect(); LOGIN_SESSIONS.pop(token, None)
            return render_template_string(HTML_TEMPLATE, title="خطا", message=f"خطا در ارسال کد: {e}")
    return asyncio.run(worker())

@web_app.route('/submit_code/<token>', methods=['POST'])
def submit_code(token):
    async def worker():
        session_data = LOGIN_SESSIONS.get(token)
        if not session_data or session_data.get('step') != 'awaiting_code': return "جلسه نامعتبر", 400
        
        code, client = request.form['code'], session_data['client']
        try:
            await client.sign_in(session_data['phone'], session_data['phone_code_hash'], code)
            session_string = await client.export_session_string(); await client.disconnect(); LOGIN_SESSIONS.pop(token, None)
            return render_template_string(HTML_TEMPLATE, title="موفقیت!", message="عملیات با موفقیت انجام شد.", session_string=session_string)
        except SessionPasswordNeeded:
            session_data['step'] = 'awaiting_password'
            form = f'<form method="post" action="/submit_password/{token}"><label for="password">رمز تایید دو مرحله‌ای:</label><input type="password" id="password" name="password" required><button type="submit">تایید رمز</button></form>'
            return render_template_string(HTML_TEMPLATE, title="مرحله ۳: تایید دو مرحله‌ای", message="حساب شما دارای رمز عبور است. آن را وارد کنید.", form_html=form)
        except Exception as e:
            logger.error(f"Web login error (sign_in) for {token}: {e}"); await client.disconnect()
            form = f'<form method="post" action="/submit_phone/{token}"><label for="phone">شماره تلفن:</label><input type="text" id="phone" name="phone" value="{session_data.get("phone", "")}" required><button type="submit">ارسال مجدد کد</button></form>'
            return render_template_string(HTML_TEMPLATE, title="مرحله ۱: شماره تلفن", message="کد اشتباه بود. دوباره تلاش کنید.", form_html=form, error=str(e))
    return asyncio.run(worker())

@web_app.route('/submit_password/<token>', methods=['POST'])
def submit_password(token):
    async def worker():
        session_data = LOGIN_SESSIONS.get(token)
        if not session_data or session_data.get('step') != 'awaiting_password': return "جلسه نامعتبر", 400

        password, client = request.form['password'], session_data['client']
        try:
            await client.check_password(password)
            session_string = await client.export_session_string(); await client.disconnect(); LOGIN_SESSIONS.pop(token, None)
            return render_template_string(HTML_TEMPLATE, title="موفقیت!", message="عملیات با موفقیت انجام شد.", session_string=session_string)
        except Exception as e:
            logger.error(f"Web login error (check_password) for {token}: {e}"); await client.disconnect(); LOGIN_SESSIONS.pop(token, None)
            return render_template_string(HTML_TEMPLATE, title="خطا", message=f"رمز عبور اشتباه بود: {e}")
    return asyncio.run(worker())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

def main() -> None:
    global application
    setup_database()
    persistence = PicklePersistence(filepath=os.path.join(DATA_PATH, "bot_persistence.pickle"))
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    application.add_error_handler(error_handler)

    self_pro_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🚀 dark self$'), self_pro_menu_text_handler)],
        states={
            AWAIT_PHONE_CONTACT: [MessageHandler(filters.CONTACT, receive_phone_contact)],
            AWAIT_SESSION_STRING: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_session_string)],
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
            AWAITING_ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_reply_to_user)],
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
    
    logger.info("Bot is starting...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    if os.path.exists(LOCK_FILE_PATH): logger.critical(f"Lock file exists. Exiting."); sys.exit(0)
    try:
        with open(LOCK_FILE_PATH, "w") as f: f.write(str(os.getpid()))
        atexit.register(lambda: os.path.exists(LOCK_FILE_PATH) and os.remove(LOCK_FILE_PATH))
        flask_thread = Thread(target=lambda: web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))))
        flask_thread.daemon = True
        flask_thread.start()
        main()
    finally:
        if os.path.exists(LOCK_FILE_PATH): os.remove(LOCK_FILE_PATH)

