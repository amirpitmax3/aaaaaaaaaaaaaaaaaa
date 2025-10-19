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

# کتابخانه‌های وب برای زنده نگه داشتن ربات در Render
from flask import Flask

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
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    PasswordHashInvalid,
    ApiIdInvalid,
    PhoneCodeExpired
)
from apscheduler.jobstores.base import JobLookupError


# تنظیمات لاگ‌گیری برای دیباگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors, log them, and gracefully shut down on Conflict.
    خطاهای فنی فقط در کنسول ثبت می شوند و برای OWNER_ID ارسال نمی گردند."""
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error detected. This instance will stop polling gracefully.")
        # This is the correct way to stop the application from within an error handler
        context.application.stop()
        return

    # لاگ کامل خطا در کنسول (محیط رندر) باقی می ماند
    logger.error(f"Exception while handling an update:", exc_info=context.error)
    
    # --- حذف بلاک ارسال خطا به تلگرام ---
    # try:
    #     tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    #     tb_string = "".join(tb_list)
    #     update_str = update.to_dict() if isinstance(update, Update) else str(update)
    #     message = (
    #         f"An exception was raised while handling an update\n"
    #         f"<pre>update = {html.escape(str(update_str))}</pre>\n\n"
    #         f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
    #         f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    #         f"<pre>{html.escape(tb_string)}</pre>"
    #     )
    #     for i in range(0, len(message), 4096):
    #         await context.bot.send_message(
    #             chat_id=OWNER_ID, text=message[i:i+4096], parse_mode=ParseMode.HTML
    #         )
    # except Exception as e:
    #     logger.error(f"Failed to send error notification to owner: {e}")
    # --- پایان حذف بلاک ---
    


# --- بخش وب سرور برای Ping ---
web_app = Flask(__name__)
@web_app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# --- متغیرهای ربات ---
TELEGRAM_TOKEN = "7422142910:AAHJvdDSWpsiFRo7WRCEhsVL1oFWooefl5w"
API_ID = 29645784  # <--- به روز رسانی شد
API_HASH = "8367987651:AAE4qOeiBpJNH4fjCt1trzM7g5cKF8s8qGM"  # <--- به روز رسانی شد
OWNER_ID = 7423552124

# مسیر دیتابیس و فایل قفل در دیسک پایدار Render
DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
DB_PATH = os.path.join(DATA_PATH, "bot_database.db")
SESSION_PATH = DATA_PATH
LOCK_FILE_PATH = os.path.join(DATA_PATH, "bot.lock")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- مراحل ConversationHandler ---
(
    ASK_DIAMOND_AMOUNT, AWAIT_RECEIPT,
    ASK_PHONE_CONTACT, ASK_CODE, ASK_PASSWORD,
    ADMIN_PANEL_MAIN, SETTING_PRICE, SETTING_INITIAL_BALANCE,
    SETTING_SELF_COST, SETTING_CHANNEL_LINK, SETTING_REFERRAL_REWARD,
    SETTING_PAYMENT_CARD, ADMIN_ADD, ADMIN_REMOVE,
    AWAITING_SUPPORT_MESSAGE, AWAITING_ADMIN_REPLY
) = range(16)

# --- استایل‌های فونت ---
FONT_STYLES = {
    'normal': "0123456789", 'monospace': "🟶🟷🟸🟹🟺🟻🟼🟽🟾🟿",
    'doublestruck': "𝟘𝟙𚼉𝟛𝟜𝟝𝟞𝟟𝟠𝟡", 'stylized': "𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫",
    'cursive': "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
}

def stylize_time(time_str: str, style: str) -> str:
    if style not in FONT_STYLES: style = 'normal'
    return time_str.translate(str.maketrans("0123456789", FONT_STYLES[style]))

# --- مدیریت دیتابیس (SQLite) ---
def db_connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con, con.cursor()

def setup_database():
    con, cur = db_connect()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            self_active BOOLEAN DEFAULT FALSE, self_paused BOOLEAN DEFAULT FALSE,
            phone_number TEXT, font_style TEXT DEFAULT 'normal', 
            base_first_name TEXT, base_last_name TEXT, session_string TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN base_last_name TEXT")
        con.commit()
    except sqlite3.OperationalError: pass
    try:
        cur.execute("ALTER TABLE users ADD COLUMN session_string TEXT")
        con.commit()
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
            referrer_id INTEGER, referred_id INTEGER, reward_granted BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (referrer_id, referred_id)
        )
    """)
    default_settings = {
        "diamond_price": "500", "initial_balance": "10", "self_hourly_cost": "5",
        "referral_reward": "20", "payment_card": "شماره کارت خود را اینجا وارد کنید",
        "mandatory_channel": "@YourChannel",
        "mandatory_channel_enabled": "false"
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
        # <--- اصلاح شد: به جای user.id که یک sqlite3.Row بود، از user_id استفاده شد
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

def is_admin(user_id):
    return user_id in get_admins()

def get_user_handle(user: User):
    return f"@{user.username}" if user.username else user.full_name

# --- دکوریتور عضویت اجباری ---
def channel_membership_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        is_enabled = get_setting("mandatory_channel_enabled")
        if is_enabled != 'true':
            return await func(update, context, *args, **kwargs)

        user = update.effective_user
        if is_admin(user.id):
            return await func(update, context, *args, **kwargs)

        channel_id = get_setting("mandatory_channel")
        if not channel_id or not channel_id.startswith('@'):
            logger.warning("Mandatory channel not set or invalid.")
            return await func(update, context, *args, **kwargs)
        
        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                return await func(update, context, *args, **kwargs)
            else:
                raise ValueError("User not a member")
        except Exception:
            channel_link = f"https://t.me/{channel_id.lstrip('@')}"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("عضویت در کانال", url=channel_link)]])
            if update.effective_message:
                 await update.effective_message.reply_text(
                    "برای استفاده از ربات، لطفا ابتدا در کانال ما عضو شوید و سپس دوباره تلاش کنید.",
                    reply_markup=keyboard
                )
            elif update.callback_query:
                await update.callback_query.message.reply_text(
                    "برای استفاده از ربات، لطفا ابتدا در کانال ما عضو شوید و سپس دوباره تلاش کنید.",
                    reply_markup=keyboard
                )
            return
    return wrapper

# --- کیبوردهای ربات ---
async def main_reply_keyboard(user_id):
    keyboard = [[KeyboardButton("💎 موجودی"), KeyboardButton("🚀 Self Pro")]]
    row_two = []
    if not is_admin(user_id):
        row_two.append(KeyboardButton("💰 افزایش موجودی"))
        row_two.append(KeyboardButton("💬 پشتیبانی"))
    row_two.append(KeyboardButton("🎁 کسب جم رایگان"))
    keyboard.append(row_two)
    if is_admin(user_id):
        keyboard.append([KeyboardButton("👑 پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def admin_panel_keyboard():
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
    return InlineKeyboardMarkup(keyboard)

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
    get_user(user.id, user.username)
    await update.message.reply_text(
        f"سلام {user.first_name}! به ربات Self Pro خوش آمدید.",
        reply_markup=await main_reply_keyboard(user.id),
    )
    return ConversationHandler.END

# --- منطق خرید الماس ---
@channel_membership_required
async def buy_diamond_start_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تعداد الماسی که قصد خرید دارید را وارد کنید:")
    return ASK_DIAMOND_AMOUNT

async def ask_diamond_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if not 0 < amount <= 10000:
            await update.message.reply_text("لطفا یک عدد بین ۱ تا ۱۰,۰۰۰ وارد کنید.")
            return ASK_DIAMOND_AMOUNT
    except ValueError:
        await update.message.reply_text("لطفا یک عدد صحیح وارد کنید.")
        return ASK_DIAMOND_AMOUNT
    diamond_price = int(get_setting("diamond_price"))
    total_cost = amount * diamond_price
    payment_card = get_setting("payment_card")
    context.user_data.update({'purchase_amount': amount, 'purchase_cost': total_cost})
    text = (f"🧾 **پیش‌فاکتور خرید**\n\n💎 تعداد: {amount}\n💳 مبلغ: {total_cost:,} تومان\n\n"
            f"لطفاً مبلغ را به شماره کارت زیر واریز و سپس **عکس رسید** را ارسال کنید:\n`{payment_card}`")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    return AWAIT_RECEIPT

async def await_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("لطفا فقط عکس رسید را ارسال کنید.")
        return AWAIT_RECEIPT
    user = update.effective_user
    amount = context.user_data.get('purchase_amount', 0)
    cost = context.user_data.get('purchase_cost', 0)
    if amount == 0: return ConversationHandler.END
    con, cur = db_connect()
    cur.execute("INSERT INTO transactions (user_id, amount_diamonds, amount_toman, receipt_file_id) VALUES (?, ?, ?, ?)",
                (user.id, amount, cost, update.message.photo[-1].file_id))
    transaction_id = cur.lastrowid
    con.commit()
    con.close()
    await update.message.reply_text("✅ رسید شما دریافت شد. لطفاً تا زمان بررسی و تایید توسط ادمین صبور باشید.")
    caption = (f" رسید جدید برای تایید\n\nکاربر: {get_user_handle(user)} (ID: `{user.id}`)\n"
               f"تعداد الماس: {amount}\nمبلغ: {cost:,} تومان")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید", callback_data=f"approve_{transaction_id}"),
         InlineKeyboardButton("❌ رد", callback_data=f"reject_{transaction_id}")]])
    for admin_id in get_admins():
        try:
            await context.bot.send_photo(admin_id, update.message.photo[-1].file_id, caption, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send receipt to admin {admin_id}: {e}")
    return ConversationHandler.END

async def handle_transaction_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, transaction_id = query.data.split("_")
    con, cur = db_connect()
    cur.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    tx = cur.fetchone()
    con.close()
    if not tx or tx['status'] != 'pending':
        await query.edit_message_caption(caption="این تراکنش قبلاً پردازش شده است.")
        return
    user_id, amount = tx['user_id'], tx['amount_diamonds']
    if action == "approve":
        update_user_balance(user_id, amount, add=True)
        new_status, user_message, admin_caption = 'approved', f"✅ درخواست شما تایید شد و {amount} الماس به حسابتان اضافه گردید.", f"✅ تراکنش تایید شد.\n {amount} الماس به کاربر اضافه شد."
    else:
        new_status, user_message, admin_caption = 'rejected', "❌ درخواست افزایش موجودی شما توسط ادمین رد شد.", "❌ تراکنش رد شد."
    con, cur = db_connect()
    cur.execute("UPDATE transactions SET status = ?, approved_by = ? WHERE id = ?", (new_status, query.from_user.id, transaction_id))
    con.commit()
    con.close()
    await query.edit_message_caption(caption=admin_caption)
    try: await context.bot.send_message(user_id, user_message)
    except Exception as e: logger.warning(f"Could not notify user {user_id}: {e}")

# --- منطق ورود به سلف (کامل و اصلاح شده) ---
user_sessions = {}
LOGIN_CLIENTS = {} # Temporary clients for auth flow

@channel_membership_required
async def self_pro_menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_db = get_user(user_id)
    if user_db['self_active']:
        await update.message.reply_text("⚙️ منوی مدیریت Self Pro:", reply_markup=await self_pro_management_keyboard(user_id))
        return ConversationHandler.END

    if get_user(user_id)['balance'] < 10:
        await update.message.reply_text("برای فعال سازی سلف، حداقل باید ۱۰ الماس موجودی داشته باشید.")
        return ConversationHandler.END
    
    keyboard = [[KeyboardButton("📱 اشتراک‌گذاری شماره تلفن", request_contact=True)]]
    await update.message.reply_text("لطفا برای فعال‌سازی، شماره تلفن خود را به اشتراک بگذارید.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
    return ASK_PHONE_CONTACT

async def ask_phone_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = f"+{update.message.contact.phone_number.lstrip('+')}"
    user_id = update.effective_user.id

    await update.message.reply_text("شماره شما دریافت شد. در حال ارسال کد...", reply_markup=ReplyKeyboardRemove())
    
    client = Client(name=f"auth_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    LOGIN_CLIENTS[user_id] = client
    context.user_data['phone'] = phone

    try:
        # ---> اضافه شد: تاخیر برای برقراری اتصال پایدار <---
        await asyncio.sleep(1)
        await client.connect()
        sent_code = await client.send_code(phone)
        context.user_data['phone_code_hash'] = sent_code.phone_code_hash
        await update.message.reply_text("کد تایید ارسال شده به تلگرام خود را وارد کنید:")
        return ASK_CODE
    except Exception as e:
        logger.error(f"Pyrogram connection/send_code error for {phone}: {e}", exc_info=True)
        error_message = f"❌ دلیل ناموفق بودن ورود: خطای فنی در ارسال کد.\n\nجزئیات: <code>{type(e).__name__}: {e}</code>"
        await update.message.reply_text(error_message, parse_mode=ParseMode.HTML, reply_markup=await main_reply_keyboard(user_id))
        if user_id in LOGIN_CLIENTS:
            if LOGIN_CLIENTS[user_id].is_connected:
                await LOGIN_CLIENTS[user_id].disconnect()
            del LOGIN_CLIENTS[user_id]
        return ConversationHandler.END

async def ask_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    client = LOGIN_CLIENTS.get(user_id)

    if not client:
        await update.message.reply_text("خطای داخلی رخ داد. لطفا دوباره شروع کنید.", reply_markup=await main_reply_keyboard(user_id))
        return ConversationHandler.END
    
    # اطمینان از اتصال قبل از sign_in
    if not client.is_connected:
        try: await client.connect()
        except Exception as e:
            logger.error(f"Failed to reconnect client for {user_id} in ask_code: {e}", exc_info=True)
            await client.disconnect() # برای اطمینان از پاکسازی
            del LOGIN_CLIENTS[user_id]
            error_message = f"❌ دلیل ناموفق بودن ورود: قطع اتصال موقت.\n\nجزئیات فنی: <code>{type(e).__name__}: {e}</code>"
            await update.message.reply_text(error_message, parse_mode=ParseMode.HTML, reply_markup=await main_reply_keyboard(user_id))
            return ConversationHandler.END

    try:
        await client.sign_in(context.user_data['phone'], context.user_data['phone_code_hash'], code)
        return await process_self_activation(update, context, client)
    except SessionPasswordNeeded:
        # در صورت نیاز به رمز، client در LOGIN_CLIENTS باقی می‌ماند.
        await update.message.reply_text("این اکانت دارای تایید دو مرحله‌ای است. لطفا رمز عبور خود را وارد کنید:")
        return ASK_PASSWORD
    except (PhoneCodeInvalid, PhoneCodeExpired) as e:
        msg = "کد تایید منقضی شده است." if isinstance(e, PhoneCodeExpired) else "کد تایید اشتباه است."
        error_message = f"❌ دلیل ناموفق بودن ورود: {msg}\n\nلطفا با زدن /cancel فرآیند را از ابتدا شروع کنید."
        
        if client.is_connected: await client.disconnect() 
        await update.message.reply_text(error_message, reply_markup=await main_reply_keyboard(user_id))
        del LOGIN_CLIENTS[user_id]
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"An unexpected error during sign-in for user {user_id}: {e}", exc_info=True)
        error_message = f"❌ دلیل ناموفق بودن ورود: خطای ناشناخته در مرحله تایید کد.\n\nجزئیات فنی: <code>{type(e).__name__}: {e}</code>"
        
        # --- اصلاحیه: قطع اتصال کلاینت در خطا ---
        if client.is_connected: await client.disconnect()
        await update.message.reply_text(error_message, parse_mode=ParseMode.HTML, reply_markup=await main_reply_keyboard(user_id))
        del LOGIN_CLIENTS[user_id]
        return ConversationHandler.END

async def ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    user_id = update.effective_user.id
    client = LOGIN_CLIENTS.get(user_id)

    if not client:
        await update.message.reply_text("یک خطای داخلی رخ داده است. لطفا با /cancel مجدَد تلاش کنید.", reply_markup=await main_reply_keyboard(user_id))
        return ConversationHandler.END

    # اطمینان از اتصال قبل از check_password
    if not client.is_connected:
        try: await client.connect()
        except Exception as e:
            logger.error(f"Failed to reconnect client for {user_id} in ask_password: {e}", exc_info=True)
            await client.disconnect()
            del LOGIN_CLIENTS[user_id]
            error_message = f"❌ دلیل ناموفق بودن ورود: قطع اتصال موقت.\n\nجزئیات فنی: <code>{type(e).__name__}: {e}</code>"
            await update.message.reply_text(error_message, parse_mode=ParseMode.HTML, reply_markup=await main_reply_keyboard(user_id))
            return ConversationHandler.END
            
    try:
        await client.check_password(password)
        # در صورت موفقیت، به مرحله فعالسازی بروید
        return await process_self_activation(update, context, client)
    except PasswordHashInvalid:
        error_message = f"❌ دلیل ناموفق بودن ورود: رمز عبور تأیید دو مرحله‌ای اشتباه است.\n\nلطفا با زدن /cancel فرآیند را از ابتدا شروع کنید."
        
        # --- اصلاحیه: قطع اتصال کلاینت در خطا ---
        if client.is_connected: await client.disconnect()
        await update.message.reply_text(error_message, reply_markup=await main_reply_keyboard(user_id))
        del LOGIN_CLIENTS[user_id]
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"An unexpected error during check_password for user {user_id}: {e}", exc_info=True)
        error_message = f"❌ دلیل ناموفق بودن ورود: خطای ناشناخته در مرحله تایید رمز عبور.\n\nجزئیات فنی: <code>{type(e).__name__}: {e}</code>"
        
        # --- اصلاحیه: قطع اتصال کلاینت در خطا ---
        if client.is_connected: await client.disconnect()
        await update.message.reply_text(error_message, parse_mode=ParseMode.HTML, reply_markup=await main_reply_keyboard(user_id))
        del LOGIN_CLIENTS[user_id]
        return ConversationHandler.END

async def process_self_activation(update: Update, context: ContextTypes.DEFAULT_TYPE, temp_client: Client):
    user_id = update.effective_user.id
    
    session_string = await temp_client.export_session_string()
    # کلاینت موقت بعد از استخراج سشن استرینگ قطع می شود (مطابق منطق وب)
    await temp_client.disconnect()
    if user_id in LOGIN_CLIENTS:
        del LOGIN_CLIENTS[user_id]
        
    permanent_client = Client(
        name=f"user_{user_id}",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        # توجه: پارامتر workdir که باعث ذخیره‌سازی فایل سشن روی دیسک می‌شد، حذف شد.
        in_memory=True # تضمین می‌کند که کلاینت دائمی نیز چیزی روی دیسک ذخیره نکند
    )

    await permanent_client.start()
    me = await permanent_client.get_me()
    
    update_user_db(user_id, "base_first_name", me.first_name)
    update_user_db(user_id, "base_last_name", me.last_name or "")
    update_user_db(user_id, "self_active", True)
    update_user_db(user_id, "phone_number", context.user_data['phone'])
    update_user_db(user_id, "session_string", session_string)
    user_sessions[user_id] = permanent_client
    
    asyncio.create_task(self_pro_background_task(user_id, permanent_client, application))
    await update.message.reply_text("✅ Self Pro با موفقیت فعال شد!", reply_markup=await main_reply_keyboard(user_id))
    
    context.user_data.clear()
    return ConversationHandler.END


async def self_pro_background_task(user_id: int, client: Client, application: Application):
    try:
        if not client.is_connected:
            try:
                await client.start()
            except Exception as e:
                logger.error(f"Could not start client for {user_id}: {e}")
                return

        while user_id in user_sessions:
            try:
                user = get_user(user_id)
                if not user or not user['self_active']:
                    break
                if not user['self_paused']:
                    hourly_cost = int(get_setting("self_hourly_cost"))
                    if user['balance'] < hourly_cost:
                        update_user_db(user_id, "self_active", False)
                        update_user_db(user_id, "self_paused", False)
                        await client.stop()
                        del user_sessions[user_id]
                        try:
                            await application.bot.send_message(user_id, "موجودی الماس شما تمام شد و Self Pro غیرفعال گردید.")
                        except Exception:
                            pass
                        break
                    update_user_balance(user_id, hourly_cost, add=False)
                    try:
                        base_name = user['base_first_name']
                        if not base_name:
                            me = await client.get_me()
                            base_name = me.first_name
                            update_user_db(user_id, "base_first_name", base_name)

                        now_str = datetime.now().strftime("%H:%M")
                        styled_time = stylize_time(now_str, user['font_style'])
                        await client.update_profile(first_name=f"{base_name} | {styled_time}")
                    except Exception as e:
                        logger.error(f"Failed to update profile for {user_id}: {e}")
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error inside self_pro_background_task loop for user {user_id}: {e}", exc_info=True)
                await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"Critical error in self_pro_background_task for user {user_id}: {e}", exc_info=True)
    finally:
        logger.info(f"Background task for user {user_id} stopped.")

# --- بقیه توابع ---
@channel_membership_required
async def toggle_self_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user = get_user(query.from_user.id)
    new_state = not user['self_paused']
    update_user_db(query.from_user.id, 'self_paused', new_state)
    status_text = "متوقف" if new_state else "فعال"
    await query.answer(f"ساعت با موفقیت {status_text} شد.")
    await query.edit_message_reply_markup(reply_markup=await self_pro_management_keyboard(query.from_user.id))

@channel_membership_required
async def change_font_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفا یک فونت برای نمایش زمان انتخاب کنید:", reply_markup=await font_selection_keyboard(query.from_user.id))

@channel_membership_required
async def set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    font_style = query.data.replace("set_font_", "")
    user_id = query.from_user.id
    update_user_db(user_id, 'font_style', font_style)
    await query.answer(f"فونت با موفقیت به {font_style} تغییر یافت.")
    await query.edit_message_reply_markup(reply_markup=await font_selection_keyboard(user_id))

@channel_membership_required
async def back_to_self_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("⚙️ منوی مدیریت Self Pro:", reply_markup=await self_pro_management_keyboard(query.from_user.id))

@channel_membership_required
async def delete_self_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton(" بله، حذف کن", callback_data="delete_self_final"), InlineKeyboardButton(" خیر", callback_data="back_to_self_menu")]]
    await query.edit_message_text("آیا از حذف کامل سلف خود مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))

@channel_membership_required
async def delete_self_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user(user_id)
    
    if user_id in user_sessions:
        client = user_sessions[user_id]
        try:
            if not client.is_connected:
                await client.start()
            
            first_name_to_restore = user_data['base_first_name'] if user_data['base_first_name'] else ""
            last_name_to_restore = user_data['base_last_name'] if user_data['base_last_name'] else ""
            
            await client.update_profile(first_name=first_name_to_restore, last_name=last_name_to_restore)
            logger.info(f"Successfully restored name for user {user_id}")
            
        except Exception as e:
            logger.error(f"Could not restore name for user {user_id}: {e}")
        finally:
            if client.is_connected:
                await client.stop()
            user_sessions.pop(user_id, None)

    # حذف فایل سشن در صورت وجود، هرچند با in_memory دیگر نباید فایلی وجود داشته باشد.
    session_file = os.path.join(SESSION_PATH, f"user_{user_id}.session")
    if os.path.exists(session_file):
        os.remove(session_file)
        
    update_user_db(user_id, 'self_active', False)
    update_user_db(user_id, 'self_paused', False)
    update_user_db(user_id, 'base_first_name', None)
    update_user_db(user_id, 'base_last_name', None)
    update_user_db(user_id, 'session_string', None)

    await query.answer("سلف شما با موفقیت حذف شد و نام شما بازیابی گردید.")
    await query.edit_message_text("سلف شما حذف شد. نام اصلی شما بازیابی شد.")

@channel_membership_required
async def check_balance_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = get_user(update.effective_user.id)
    toman_equivalent = user_data['balance'] * int(get_setting("diamond_price"))
    text = (f"👤 کاربر: <b>{get_user_handle(update.effective_user)}</b>\n\n"
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # --- منطق تمیز کردن کلاینت Pyrogram در صورت وجود ---
    user_id = update.effective_user.id
    client = LOGIN_CLIENTS.get(user_id)
    if client:
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting client in /cancel for {user_id}: {e}")
        finally:
            LOGIN_CLIENTS.pop(user_id, None)
            
    context.user_data.clear()
    await update.message.reply_text("عملیات قبلی لغو شد.", reply_markup=await main_reply_keyboard(update.effective_user.id))
    return ConversationHandler.END

async def resolve_bet_logic(chat_id: int, message_id: int, bet_info: dict, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="🎲 تاس‌ها در حال چرخش هستند...", reply_markup=None)
    await asyncio.sleep(3)
    participants_list = list(bet_info['participants'])
    random.shuffle(participants_list)
    winner_id = random.choice(participants_list)
    losers_list = [p_id for p_id in participants_list if p_id != winner_id]
    bet_amount = bet_info['amount']
    total_pot = bet_amount * len(participants_list)
    tax = math.ceil(total_pot * 0.02)
    prize = total_pot - tax
    update_user_balance(winner_id, prize, add=True)
    for p_id in bet_info['participants']:
        if 'users_in_bet' in context.chat_data:
            context.chat_data['users_in_bet'].discard(p_id)
    winner_handle = get_user_handle(await context.bot.get_chat(winner_id))
    losers_handles = ", ".join([get_user_handle(await context.bot.get_chat(loser_id)) for loser_id in losers_list])
    result_text = (f"<b>◈ ━━━ 🎲 نتیجه شرط‌بندی 🎲 ━━━ ◈</b>\n<b>مبلغ:</b> {bet_amount} الماس\n\n"
                   f"🏆 <b>برنده:</b> {winner_handle}\n"
                   f"💔 <b>بازنده(ها):</b> {losers_handles or 'هیچ‌کس'}\n\n"
                   f"💰 <b>جایزه:</b> {prize} الماس (با کسر {tax} الماس مالیات)\n"
                   f"<b>◈ ━━━ Self Pro ━━━ ◈</b>")
    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=result_text, parse_mode=ParseMode.HTML)

async def end_bet_on_timeout(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data['chat_id']
    chat_data = context.application.chat_data.get(chat_id, {})
    bet_info = job_data['bet_info']

    for p_id in bet_info['participants']:
        update_user_balance(p_id, bet_info['amount'], add=True)
        if 'users_in_bet' in chat_data:
            chat_data['users_in_bet'].discard(p_id)
            
    if 'bets' in chat_data:
        chat_data['bets'].pop(job_data['message_id'], None)

    await context.bot.edit_message_text(chat_id=chat_id, message_id=job_data['message_id'], text="⌛️ زمان شرط‌بندی تمام شد و مبلغ به شرکت‌کنندگان بازگردانده شد.")

@channel_membership_required
async def start_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'users_in_bet' not in context.chat_data: context.chat_data['users_in_bet'] = set()
    creator = update.effective_user
    if creator.id in context.chat_data['users_in_bet']:
        await update.message.reply_text("شما در حال حاضر در یک شرط‌بندی دیگر فعال هستید."); return
    try:
        amount = int(context.args[0])
        if amount <= 0: await update.message.reply_text("مبلغ شرط باید بیشتر از صفر باشد."); return
    except (IndexError, ValueError):
        await update.message.reply_text("لطفا مبلغ شرط را مشخص کنید. مثال: /bet 100"); return
    if get_user(creator.id, creator.username)['balance'] < amount:
        await update.message.reply_text("موجودی شما برای شروع این شرط‌بندی کافی نیست."); return
    update_user_balance(creator.id, amount, add=False)
    bet_message = await update.message.reply_text("در حال ایجاد شرط...")
    bet_info = {'amount': amount, 'creator_id': creator.id, 'participants': {creator.id}}
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ پیوستن", callback_data=f"join_bet_{bet_message.message_id}"), InlineKeyboardButton("❌ لغو شرط", callback_data=f"cancel_bet_{bet_message.message_id}")]])
    text = (f"🎲 شرط‌بندی جدید به مبلغ <b>{amount}</b> الماس توسط {get_user_handle(creator)} شروع شد!\n\n"
            f"نفر دوم که بپیوندد، برنده مشخص خواهد شد.\n\n"
            f"<b>شرکت کنندگان:</b>\n- {get_user_handle(creator)}")
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=bet_message.message_id, text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    job_data = {'message_id': bet_message.message_id, 'bet_info': bet_info, 'chat_id': update.effective_chat.id}
    job = context.job_queue.run_once(end_bet_on_timeout, 60, data=job_data, name=f"bet_{bet_message.message_id}")
    bet_info['job'] = job
    if 'bets' not in context.chat_data: context.chat_data['bets'] = {}
    context.chat_data['bets'][bet_message.message_id] = bet_info
    context.chat_data['users_in_bet'].add(creator.id)

@channel_membership_required
async def join_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user = query.from_user
    message_id = int(query.data.split("_")[-1])
    bets = context.chat_data.get('bets', {})
    if message_id not in bets: await query.answer("این شرط‌بندی دیگر فعال نیست.", show_alert=True); return
    bet_info = bets[message_id]
    if user.id in bet_info['participants']: await query.answer("شما قبلاً در این شرط شرکت کرده‌اید.", show_alert=True); return
    if user.id in context.chat_data.get('users_in_bet', set()): await query.answer("شما در حال حاضر در یک شرط‌بندی دیگر فعال هستید.", show_alert=True); return
    if get_user(user.id, user.username)['balance'] < bet_info['amount']:
        await query.answer("موجودی شما برای شرکت در این شرط‌بندی کافی نیست.", show_alert=True); return
    update_user_balance(user.id, bet_info['amount'], add=False)
    bet_info['participants'].add(user.id)
    context.chat_data['users_in_bet'].add(user.id)
    await query.answer("شما به شرط پیوستید! نتیجه بلافاصله اعلام می‌شود...")
    
    try:
        bet_info['job'].schedule_removal()
    except JobLookupError:
        logger.warning(f"Job for bet {message_id} already removed or finished.")
        
    context.chat_data['bets'].pop(message_id, None)
    await resolve_bet_logic(chat_id=update.effective_chat.id, message_id=message_id, bet_info=bet_info, context=context)

async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    message_id = int(query.data.split("_")[-1])
    bets = context.chat_data.get('bets', {})
    if message_id not in bets: await query.answer("این شرط‌بندی دیگر فعال نیست.", show_alert=True); return
    bet_info = bets[message_id]
    if query.from_user.id != bet_info['creator_id']:
        await query.answer("فقط شروع‌کننده می‌تواند شرط را لغو کند.", show_alert=True); return
    
    try:
        bet_info['job'].schedule_removal()
    except JobLookupError:
        logger.warning(f"Attempted to cancel an already finished/removed job for bet {message_id}.")

    for p_id in bet_info['participants']:
        update_user_balance(p_id, bet_info['amount'], add=True)
        if 'users_in_bet' in context.chat_data:
            context.chat_data['users_in_bet'].discard(p_id)
    context.chat_data['bets'].pop(message_id, None)
    await query.message.edit_text(f"🎲 شرط‌بندی توسط {get_user_handle(query.from_user)} لغو شد و مبلغ به شرکت‌کنندگان بازگردانده شد.")
    await query.answer("شرط با موفقیت لغو شد.")

@channel_membership_required
async def admin_panel_entry_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("شما دسترسی به این بخش را ندارید."); return ConversationHandler.END
    await update.message.reply_text("👑 به پنل ادمین خوش آمدید:", reply_markup=await admin_panel_keyboard())
    return ADMIN_PANEL_MAIN

async def ask_for_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    setting_map = {
        "admin_set_price": ("diamond_price", "💎 قیمت جدید هر الماس به تومان را وارد کنید:", SETTING_PRICE),
        "admin_set_initial_balance": ("initial_balance", "💰 موجودی اولیه کاربران جدید را وارد کنید:", SETTING_INITIAL_BALANCE),
        "admin_set_self_cost": ("self_hourly_cost", "🚀 هزینه ساعتی سلف را وارد کنید:", SETTING_SELF_COST),
        "admin_set_referral_reward": ("referral_reward", "🎁 پاداش دعوت را وارد کنید:", SETTING_REFERRAL_REWARD),
        "admin_set_payment_card": ("payment_card", "💳 شماره کارت جدید را وارد کنید:", SETTING_PAYMENT_CARD),
        "admin_set_channel": ("mandatory_channel", "📢 آیدی کانال اجباری (با @) را وارد کنید:", SETTING_CHANNEL_LINK),
    }
    
    if query.data not in setting_map:
        return ADMIN_PANEL_MAIN

    setting_key, prompt, next_state = setting_map[query.data]
    context.user_data["setting_key"] = setting_key
    await query.edit_message_text(prompt); return next_state

async def receive_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_value = update.message.text
    setting_key = context.user_data.pop("setting_key", None)
    if not setting_key: return ADMIN_PANEL_MAIN
    update_setting(setting_key, new_value)
    await update.message.reply_text("✅ تنظیمات با موفقیت ذخیره شد.")
    await update.message.reply_text("👑 پنل ادمین:", reply_markup=await admin_panel_keyboard())
    return ADMIN_PANEL_MAIN
    
async def toggle_channel_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current_state = get_setting("mandatory_channel_enabled")
    new_state = "false" if current_state == "true" else "true"
    update_setting("mandatory_channel_enabled", new_state)
    status_text = "فعال" if new_state == "true" else "غیرفعال"
    await query.answer(f"قفل کانال با موفقیت {status_text} شد.")
    await query.edit_message_reply_markup(reply_markup=await admin_panel_keyboard())


@channel_membership_required
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا پیام خود را برای ارسال به پشتیبانی بنویسید.", reply_markup=ReplyKeyboardRemove())
    return AWAITING_SUPPORT_MESSAGE

async def forward_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_text("✅ پیام شما برای پشتیبانی ارسال شد.", reply_markup=await main_reply_keyboard(user.id))
    forward_text = (f"📩 **پیام پشتیبانی جدید**\n\n👤 **از:** {get_user_handle(user)} (ID: `{user.id}`)\n\n📝 **متن:**\n{update.message.text}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ پاسخ", callback_data=f"reply_to_{user.id}")]])
    for admin_id in get_admins():
        try: await context.bot.send_message(admin_id, forward_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        except Exception as e: logger.error(f"Failed to forward support message to admin {admin_id}: {e}")
    return ConversationHandler.END

async def ask_for_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
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

def main() -> None:
    global application
    setup_database()
    
    persistence = PicklePersistence(filepath=os.path.join(DATA_PATH, "bot_persistence.pickle"))
    
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    
    application.add_error_handler(error_handler)

    # A non-persistent conversation handler for the login flow
    login_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🚀 Self Pro$'), self_pro_menu_text_handler)],
        states={
            ASK_PHONE_CONTACT: [MessageHandler(filters.CONTACT, ask_phone_contact)],
            ASK_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_code)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        persistent=False,
        name="login_conversation"
    )

    # The main conversation handler for other features (can be persistent)
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
                CallbackQueryHandler(ask_for_setting, pattern=r"admin_set_"),
                CallbackQueryHandler(toggle_channel_lock, pattern=r"^admin_toggle_channel_lock$")
            ],
            SETTING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_INITIAL_BALANCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_SELF_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_REFERRAL_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_PAYMENT_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            SETTING_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_setting)],
            AWAITING_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message_to_admin)],
            AWAITING_ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_reply_to_user)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        persistent=True,
        name="main_conversation"
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(login_conv)
    application.add_handler(main_conv)
    application.add_handler(CommandHandler("bet", start_bet, filters=filters.ChatType.GROUPS))
    application.add_handler(CallbackQueryHandler(join_bet, pattern=r"^join_bet_"))
    application.add_handler(CallbackQueryHandler(cancel_bet, pattern=r"^cancel_bet_"))
    application.add_handler(CallbackQueryHandler(handle_transaction_approval, pattern=r"^(approve|reject)_\d+$"))
    application.add_handler(CallbackQueryHandler(toggle_self_pause, pattern=r"^self_(pause|resume)$"))
    application.add_handler(CallbackQueryHandler(change_font_menu, pattern=r"^change_font_menu$"))
    application.add_handler(CallbackQueryHandler(set_font, pattern=r"^set_font_"))
    application.add_handler(CallbackQueryHandler(back_to_self_menu, pattern=r"^back_to_self_menu$"))
    application.add_handler(CallbackQueryHandler(delete_self_confirm, pattern=r"^delete_self_confirm$"))
    application.add_handler(CallbackQueryHandler(delete_self_final, pattern=r"^delete_self_final$"))
    application.add_handler(MessageHandler(filters.Regex('^💎 موجودی$'), check_balance_text_handler))
    application.add_handler(MessageHandler(filters.Regex('^🎁 کسب جم رایگان$'), referral_menu_text_handler))
    application.add_handler(MessageHandler(filters.REPLY & filters.Regex(r'^(انتقال الماس\s*\d+|\d+)$'), handle_transfer))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, group_text_handler))
    logger.info("Bot is starting...")
    # ---> اصلاح شد: پارامتر غیرمجاز close_bot_methods حذف شد <---
    application.run_polling(drop_pending_updates=True)

def cleanup_lock_file():
    if os.path.exists(LOCK_FILE_PATH):
        os.remove(LOCK_FILE_PATH)
        logger.info("Lock file removed.")

if __name__ == "__main__":
    logger.info("Waiting for 2 seconds before acquiring lock...")
    time.sleep(2)

    if os.path.exists(LOCK_FILE_PATH):
        logger.critical(f"Lock file {LOCK_FILE_PATH} exists, another instance is running. Exiting gracefully.")
        sys.exit(0)
        
    try:
        with open(LOCK_FILE_PATH, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(cleanup_lock_file)
        logger.info(f"Lock file created at {LOCK_FILE_PATH}")
        
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        main()
    finally:
        cleanup_lock_file()
