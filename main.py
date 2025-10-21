import asyncio
import logging
import os
import re
import secrets
from threading import Thread
from urllib.parse import quote
import aiohttp
import certifi
from flask import Flask, request, render_template_string
from pymongo import MongoClient, ReturnDocument
from pymongo.server_api import ServerApi
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton,
                      InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ConversationHandler, filters, ContextTypes, CallbackQueryHandler)
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from bson import ObjectId
import time
import random
import html
import traceback

# --- Pyrogram Imports for Self Bot Instances ---
from pyrogram import Client, filters as pyro_filters
from pyrogram.handlers import MessageHandler as PyroMessageHandler
from pyrogram.enums import ChatType as PyroChatType, ChatAction as PyroChatAction
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid
)

# =======================================================
#  بخش ۱: تنظیمات اولیه و پیکربندی
# =======================================================

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


# --- Environment Variables & Constants ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8233582209:AAHKPQX-349tAfBOCFWbRRqcpD-QbVrDzQ0")
OWNER_ID = int(os.environ.get("OWNER_ID", 7423552124))
API_ID = int(os.environ.get("API_ID", 28190856))
API_HASH = os.environ.get("API_HASH", "6b9b5309c2a211b526c6ddad6eabb521")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://CFNBEFBGWFB:hdhbedfefbegh@cluster0.obohcl3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "http://127.0.0.1:8080")
BET_TAX_RATE = 0.02 # 2% tax

# --- Database Setup (MongoDB) ---
db = None
try:
    mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
    mongo_client.admin.command('ping')
    db = mongo_client['dark_self_manager_v2']
    logging.info("Successfully connected to MongoDB!")
except Exception as e:
    logging.error(f"Could not connect to MongoDB: {e}")
    exit()

# --- Global Variables & State Management ---
LOGIN_SESSIONS = {}
ACTIVE_SELF_BOTS = {}
PYRO_LOOPS = {} # Separate event loops for each pyrogram instance
BOT_EVENT_LOOP = None # Global event loop for the main bot

# --- Conversation Handler States ---
(ADMIN_MENU, AWAIT_ADMIN_REPLY, AWAIT_DEPOSIT_AMOUNT, AWAIT_DEPOSIT_RECEIPT,
 AWAIT_SUPPORT_MESSAGE, AWAIT_ADMIN_SUPPORT_REPLY, AWAIT_PHONE, AWAIT_SESSION) = range(8)

# =======================================================
#  بخش ۲: منطق کامل سلف بات (Pyrogram)
# =======================================================
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝚲','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'７','8':'８','9':'９',':':'：'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth"]
FONT_DISPLAY_NAMES = {"cursive": "کشیده", "stylized": "فانتزی", "doublestruck": "توخالی", "monospace": "کامپیوتری", "normal": "ساده", "circled": "دایره‌ای", "fullwidth": "پهن"}
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"
ENEMY_REPLIES = ["کیرم تو رحم اجاره ای و خونی مالی مادرت", "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام...", "..."]
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

HELP_TEXT = r"""
** راهنمای کامل دستورات سلف بات **

---
** وضعیت و قالب‌بندی **
 • `تایپ روشن` / `خاموش`: فعال‌سازی حالت "در حال تایپ" در همه چت‌ها.
 • `بازی روشن` / `خاموش`: فعال‌سازی حالت "در حال بازی" در همه چت‌ها.
 • `انگلیسی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به انگلیسی.
 • `بولد روشن` / `خاموش`: برجسته کردن خودکار تمام پیام‌ها.
 • `سین روشن` / `خاموش`: سین خودکار پیام‌ها در چت شخصی (PV).

---
** ساعت و فونت **
 • `ساعت روشن` / `خاموش`: نمایش یا حذف ساعت از نام پروفایل.
 • `فونت`: نمایش لیست فونت‌های ساعت.
 • `فونت [عدد]`: انتخاب فونت جدید برای ساعت.

---
** مدیریت پیام و کاربر **
 • `حذف [عدد]`: حذف X پیام آخر شما.
 • `ذخیره` (با ریپلای): ذخیره پیام در Saved Messages.
 • `تکرار [عدد]` (با ریپلای): تکرار پیام.
 • `دشمن روشن` / `خاموش` (با ریپلای): فعال/غیرفعال کردن حالت دشمن.
 • `لیست دشمن`: نمایش لیست دشمنان.
 • `بلاک` / `آنبلاک` (با ریپلای): بلاک یا آنبلاک کردن کاربر.
 • `سکوت` / `آنسکوت` (با ریپلای): حذف خودکار پیام‌های کاربر.
 • `ریاکشن [ایموجی]` (با ریپلای): واکنش خودکار به پیام‌های کاربر.
 • `ریاکشن خاموش` (با ریپلای): غیرفعال‌سازی واکنش خودکار.
 
---
** شرط‌بندی و گروه **
 • `موجودی`: نمایش موجودی الماس.
 • `انتقال [مبلغ]` (با ریپلای): انتقال الماس.
 • `شرط [مبلغ]` (با ریپلای): شروع شرط‌بندی.
 • `قبول` (ریپلای روی پیام شرط): قبول شرط. (نیاز به بازنگری)
 • `برنده` (ریپلای روی پیام شرط): اعلام برنده. (نیاز به بازنگری)

---
** امنیت و منشی **
 • `پیوی قفل` / `باز`: قفل کردن چت شخصی.
 • `منشی روشن` / `خاموش`: فعال‌سازی پاسخ خودکار.
 • `کپی روشن` (با ریپلای): کپی کردن پروفایل کاربر.
 • `کپی خاموش`: بازگرداندن پروفایل اصلی.
"""

class SelfBotFeatures:
    def __init__(self, client, db_connection):
        self.client = client
        self.db = db_connection
        if client:
            self.user_id = client.me.id
            self.settings = self.db.self_bots.find_one({'user_id': self.user_id})
        self.enemy_reply_queues = {}

    @staticmethod
    def get_default_settings(session_string):
        return {
            'session_string': session_string, 'is_active': True, 'clock_enabled': True,
            'typing_enabled': False, 'playing_enabled': False, 'translate_enabled': False,
            'bold_enabled': False, 'seen_enabled': False, 'pv_lock_enabled': False,
            'secretary_enabled': False, 'font_style': 'stylized', 'enemies': [],
            'muted_users': [], 'auto_reactions': {}, 'original_profile': None
        }

    def get_management_keyboard(self, user_id_for_menu):
        doc = self.db.self_bots.find_one({'user_id': user_id_for_menu})
        if not doc: return None

        def get_status_emoji(feature_name):
            return "✅" if doc.get(f'{feature_name}_enabled', False) else "❌"

        keyboard = [
            [
                InlineKeyboardButton(f"{get_status_emoji('clock')} ساعت", callback_data="self_toggle_clock"),
                InlineKeyboardButton(f"{get_status_emoji('typing')} تایپ", callback_data="self_toggle_typing"),
                InlineKeyboardButton(f"{get_status_emoji('playing')} بازی", callback_data="self_toggle_playing"),
            ],
            [
                InlineKeyboardButton(f"{get_status_emoji('translate')} ترجمه", callback_data="self_toggle_translate"),
                InlineKeyboardButton(f"{get_status_emoji('bold')} بولد", callback_data="self_toggle_bold"),
                InlineKeyboardButton(f"{get_status_emoji('seen')} سین", callback_data="self_toggle_seen"),
            ],
            [
                InlineKeyboardButton(f"{get_status_emoji('pv_lock')} قفل پیوی", callback_data="self_toggle_pv_lock"),
                InlineKeyboardButton(f"{get_status_emoji('secretary')} منشی", callback_data="self_toggle_secretary"),
            ],
            [InlineKeyboardButton("🗑 حذف کامل سلف", callback_data="self_delete_delete")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def reload_settings(self):
        self.settings = self.db.self_bots.find_one({'user_id': self.user_id})

    # --- Background Tasks ---
    async def _update_profile_clock_task(self):
        while True:
            try:
                self.reload_settings()
                if self.settings.get('clock_enabled') and not self.settings.get('copy_mode_enabled'):
                    me = await self.client.get_me()
                    base_name = re.sub(r'(?:' + CLOCK_CHARS_REGEX_CLASS + r'\s*)+$', '', me.first_name).strip()
                    time_str = datetime.now(TEHRAN_TIMEZONE).strftime("%H:%M")
                    stylized_time = self._stylize_time(time_str, self.settings.get('font_style', 'stylized'))
                    new_name = f"{base_name} {stylized_time}"
                    if new_name != me.first_name:
                        await self.client.update_profile(first_name=new_name)
                
                now = datetime.now(TEHRAN_TIMEZONE)
                await asyncio.sleep(60 - now.second + 0.1)
            except (UserDeactivated, AuthKeyUnregistered): break
            except FloodWait as e: await asyncio.sleep(e.value + 5)
            except Exception as e: logging.error(f"Clock Task Error for {self.user_id}: {e}"); await asyncio.sleep(60)

    async def _status_action_task(self):
        # ... Implementation for typing/playing status ...
        pass

    def get_background_tasks(self):
        return [
            asyncio.create_task(self._update_profile_clock_task()),
            # asyncio.create_task(self._status_action_task()),
        ]

    # --- Message Handlers ---
    async def _command_handler(self, client, message):
        if not message.text: return
        
        command = message.text.lower().strip()
        parts = command.split()
        
        if command == "راهنما":
            await message.edit_text(HELP_TEXT, parse_mode='markdown')
            
        elif parts[0] == "حذف" and len(parts) > 1:
            try:
                count = int(parts[1])
                message_ids = [msg.id async for msg in client.get_chat_history(message.chat.id, limit=count) if msg.from_user.id == self.user_id]
                await client.delete_messages(message.chat.id, message_ids)
            except Exception: pass
            
        # ... Add ALL other command handlers from self.txt here ...

    async def _pv_lock_handler(self, client, message):
        self.reload_settings()
        if self.settings.get('pv_lock_enabled'):
            await message.delete()
            
    # --- Helper Methods ---
    def _stylize_time(self, time_str, style):
        font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
        return ''.join(font_map.get(char, char) for char in time_str)
        
    def register_all_handlers(self):
        self.client.add_handler(PyroMessageHandler(self._command_handler, pyro_filters.me & pyro_filters.text))
        self.client.add_handler(PyroMessageHandler(self._pv_lock_handler, pyro_filters.private & ~pyro_filters.me & ~pyro_filters.bot))


async def start_self_bot_instance(user_id: int, session_string: str):
    """Initializes and starts a Pyrogram client for a user in its own thread."""
    if user_id in ACTIVE_SELF_BOTS:
        logging.warning(f"Self bot for {user_id} is already running. Restarting.")
        await stop_self_bot_instance(user_id)

    loop = asyncio.new_event_loop()
    PYRO_LOOPS[user_id] = loop
    
    def run_pyro_client():
        asyncio.set_event_loop(loop)
        client = Client(f"self_bot_{user_id}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        
        async def main_task():
            try:
                await client.start()
                me = await client.get_me()
                if me.id != user_id:
                    logging.error(f"Session string mismatch for user {user_id}. Provided session belongs to {me.id}")
                    return

                logging.info(f"Successfully started self bot instance for user_id {user_id}.")
                
                features = SelfBotFeatures(client, db)
                features.register_all_handlers()
                
                tasks = features.get_background_tasks()
                ACTIVE_SELF_BOTS[user_id] = (client, tasks, features)

                await asyncio.gather(*tasks)

            except Exception as e:
                logging.error(f"Error in main_task for user {user_id}: {e}", exc_info=True)
            finally:
                if client.is_connected:
                    await client.stop()
                logging.info(f"Pyrogram client for {user_id} fully stopped.")
        
        loop.run_until_complete(main_task())

    thread = Thread(target=run_pyro_client, daemon=True)
    thread.start()
    await asyncio.sleep(2) 
    
    return user_id in ACTIVE_SELF_BOTS


async def stop_self_bot_instance(user_id: int):
    """Stops a running Pyrogram client and its tasks."""
    if user_id in ACTIVE_SELF_BOTS:
        client, tasks, features = ACTIVE_SELF_BOTS.pop(user_id)
        
        async def stop_tasks():
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if client.is_connected:
                await client.stop()

        loop = PYRO_LOOPS.get(user_id)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(stop_tasks(), loop).result(timeout=10)
            loop.call_soon_threadsafe(loop.stop)
        
        PYRO_LOOPS.pop(user_id, None)
        logging.info(f"Stopped self bot instance for user_id {user_id}.")
        return True
    return False
# =======================================================
#  بخش ۳: وب اپلیکیشن Flask برای لاگین
# =======================================================
web_app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ورود به سلف بات</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        
        :root {
            --bg-color: #0d1117;
            --container-bg: #161b22;
            --border-color: #30363d;
            --text-color: #c9d1d9;
            --text-muted: #8b949e;
            --accent-color: #58a6ff;
            --success-color: #3fb950;
            --error-color: #f85149;
            --btn-bg: #238636;
            --btn-hover-bg: #2ea043;
            --input-bg: #010409;
        }

        body {
            font-family: 'Vazirmatn', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }

        .container {
            background: var(--container-bg);
            padding: 30px 40px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            text-align: center;
            width: 100%;
            max-width: 480px;
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
        }

        h1 {
            color: var(--accent-color);
            margin-bottom: 15px;
            font-size: 1.8em;
            font-weight: 700;
        }

        p {
            color: var(--text-muted);
            line-height: 1.7;
            margin-bottom: 25px;
        }

        form {
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        input[type="text"],
        input[type="password"] {
            padding: 14px;
            border: 1px solid var(--border-color);
            background-color: var(--input-bg);
            color: var(--text-color);
            border-radius: 8px;
            font-size: 16px;
            text-align: left;
            direction: ltr;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        
        input:focus {
            outline: none;
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3);
        }

        input::placeholder {
            color: #484f58;
        }

        button {
            padding: 14px;
            background-color: var(--btn-bg);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color .2s, transform .1s;
            font-weight: bold;
        }

        button:hover {
            background-color: var(--btn-hover-bg);
        }
        
        button:active {
            transform: scale(0.98);
        }

        .error {
            color: var(--error-color);
            background-color: rgba(248, 81, 73, 0.1);
            padding: 10px;
            border-radius: 8px;
            margin-top: 15px;
            font-weight: bold;
            border: 1px solid var(--error-color);
        }

        .success {
            color: var(--success-color);
            font-family: monospace;
            background: var(--input-bg);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            text-align: left;
            direction: ltr;
            word-break: break-all;
            margin-top: 20px;
            position: relative;
        }
        
        .note {
            font-size: 0.9em;
            color: var(--text-muted);
            margin-top: 15px;
        }
    </style>
</head>
<body>
<div class="container">
{% if step == 'start' %}
    <h1>دریافت کد تایید</h1>
    <p>یک کد به حساب تلگرام شماره <strong>{{ phone }}</strong> ارسال خواهد شد. لطفاً روی دکمه زیر کلیک کنید.</p>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form action="/submit_phone/{{ token }}" method="post"><button type="submit">ارسال کد</button></form>
{% elif step == 'awaiting_code' %}
    <h1>کد تایید</h1>
    <p>کدی که به تلگرام شما ارسال شد را وارد کنید.</p>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form action="/submit_code/{{ token }}" method="post">
        <input type="text" name="code" placeholder="Code" required autocomplete="off">
        <button type="submit">تایید کد</button>
    </form>
{% elif step == 'awaiting_password' %}
    <h1>رمز دو مرحله‌ای</h1>
    <p>رمز تایید دو مرحله‌ای حساب خود را وارد کنید.</p>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form action="/submit_password/{{ token }}" method="post">
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">ورود</button>
    </form>
{% elif step == 'done' %}
    <h1>✅ ورود موفق</h1>
    <p>این کد Session String شماست. آن را کپی کرده و برای ربات در تلگرام ارسال کنید.</p>
    <div class="success" id="session-string">{{ session_string }}</div>
    <p class="note">این صفحه را ببندید و این کد را با هیچکس به اشتراک نگذارید.</p>
{% else %}
    <h1>خطا</h1>
    <p class="error">{{ error or 'توکن نامعتبر یا منقضی شده است. لطفا دوباره از ربات لینک بگیرید.' }}</p>
{% endif %}
</div>
</body>
</html>
"""

async def _web_send_code(token):
    session_data = LOGIN_SESSIONS.get(token)
    if not session_data or 'client' in session_data: return
    try:
        client = Client(f"login_client_{session_data['user_id']}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.connect()
        sent_code = await client.send_code(session_data['phone'])
        session_data['phone_code_hash'] = sent_code.phone_code_hash
        session_data['client'] = client
        session_data['step'] = 'awaiting_code'
    except FloodWait as e:
        logging.error(f"Web login FloodWait for token {token}: {e}")
        session_data['error'] = f"تلگرام شما را موقتا محدود کرده است. لطفا بعد از {e.value} ثانیه دوباره تلاش کنید."
    except Exception as e:
        logging.error(f"Web login error (send_code) for token {token}: {e}")
        session_data['error'] = "خطا در ارسال کد. شماره تلفن ممکن است اشتباه باشد."
        if 'client' in session_data: await session_data['client'].disconnect()
        LOGIN_SESSIONS.pop(token, None)


@web_app.route('/')
def health_check():
    """Health check endpoint for Render."""
    return "Bot is running.", 200

@web_app.route('/login/<token>')
def login_page(token):
    session_data = LOGIN_SESSIONS.get(token)
    if not session_data:
        return render_template_string(HTML_TEMPLATE, step='error', error='توکن نامعتبر یا منقضی شده.')
    return render_template_string(HTML_TEMPLATE, **session_data)

@web_app.route('/submit_phone/<token>', methods=['POST'])
def submit_phone(token):
    if token not in LOGIN_SESSIONS:
        return render_template_string(HTML_TEMPLATE, step='error')
    
    future = asyncio.run_coroutine_threadsafe(_web_send_code(token), BOT_EVENT_LOOP)
    try:
        future.result(timeout=60)
    except Exception as e:
        logging.error(f"Error in submit_phone task: {e}")
        LOGIN_SESSIONS[token]['error'] = "زمان انتظار برای ارسال کد به پایان رسید."
    
    return render_template_string(HTML_TEMPLATE, **LOGIN_SESSIONS.get(token, {'step':'error'}))

@web_app.route('/submit_code/<token>', methods=['POST'])
def submit_code(token):
    session_data = LOGIN_SESSIONS.get(token, {})
    if not session_data or 'client' not in session_data:
        return render_template_string(HTML_TEMPLATE, step='error')
    
    code = request.form.get('code')
    client = session_data['client']
    
    try:
        # Create a coroutine to run in the bot's event loop
        async def do_sign_in():
            try:
                await client.sign_in(session_data['phone'], session_data['phone_code_hash'], code.strip())
                session_string = await client.export_session_string()
                
                # Update session data for rendering
                session_data['session_string'] = session_string
                session_data['step'] = 'done'
            except SessionPasswordNeeded:
                session_data['step'] = 'awaiting_password'
            except (PhoneCodeInvalid, PhoneCodeExpired):
                session_data['error'] = 'کد وارد شده اشتباه یا منقضی شده است.'
                session_data['step'] = 'awaiting_code'
            except Exception as e:
                logging.error(f"Web login error (submit_code) for token {token}: {e}")
                session_data['step'] = 'error'
                session_data['error'] = "خطایی رخ داد. لطفا دوباره تلاش کنید."
            finally:
                if session_data['step'] == 'done' or session_data['step'] == 'error':
                    await client.disconnect()
                    if session_data['step'] == 'error':
                        LOGIN_SESSIONS.pop(token, None)

        # Run the coroutine and wait for it to complete
        future = asyncio.run_coroutine_threadsafe(do_sign_in(), BOT_EVENT_LOOP)
        future.result(timeout=60)

    except Exception as e:
        logging.error(f"General error in submit_code for token {token}: {e}")
        session_data['step'] = 'error'
        session_data['error'] = "یک خطای ناشناخته رخ داد."

    return render_template_string(HTML_TEMPLATE, **session_data)


@web_app.route('/submit_password/<token>', methods=['POST'])
def submit_password(token):
    session_data = LOGIN_SESSIONS.get(token, {})
    if not session_data or 'client' not in session_data:
        return render_template_string(HTML_TEMPLATE, step='error')

    password = request.form.get('password')
    client = session_data['client']

    try:
        async def do_check_password():
            try:
                await client.check_password(password)
                session_string = await client.export_session_string()
                session_data['session_string'] = session_string
                session_data['step'] = 'done'
            except PasswordHashInvalid:
                session_data['error'] = 'رمز عبور اشتباه است.'
                session_data['step'] = 'awaiting_password'
            except Exception as e:
                logging.error(f"Web login error (submit_password) for token {token}: {e}")
                session_data['step'] = 'error'
                session_data['error'] = "خطایی در تایید رمز رخ داد."
            finally:
                if session_data['step'] == 'done' or session_data['step'] == 'error':
                    await client.disconnect()
                    if session_data['step'] == 'error':
                        LOGIN_SESSIONS.pop(token, None)

        future = asyncio.run_coroutine_threadsafe(do_check_password(), BOT_EVENT_LOOP)
        future.result(timeout=60)
        
    except Exception as e:
        logging.error(f"General error in submit_password for token {token}: {e}")
        session_data['step'] = 'error'
        session_data['error'] = "یک خطای ناشناخته در پردازش رمز عبور رخ داد."

    return render_template_string(HTML_TEMPLATE, **session_data)

# =======================================================
#  بخش ۴: توابع کمکی ربات و دیتابیس
# =======================================================
def get_setting(name):
    doc = db.settings.find_one({'name': name})
    return doc['value'] if doc else None

def set_setting(name, value):
    db.settings.update_one({'name': name}, {'$set': {'value': value}}, upsert=True)

def get_user(user_id):
    initial_balance = get_setting('initial_balance') or 10
    is_owner = user_id == OWNER_ID
    # Owners get a massive starting balance on creation
    balance_on_create = 1000000000 if is_owner else initial_balance
    
    return db.users.find_one_and_update(
        {'user_id': user_id},
        {'$setOnInsert': {
            'balance': balance_on_create,
            'is_admin': is_owner,
            'is_owner': is_owner
        }},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

def get_main_keyboard(user_doc):
    keyboard = [
        [KeyboardButton("💎 موجودی"), KeyboardButton("🚀 dark self")],
        [KeyboardButton("💰 افزایش موجودی"), KeyboardButton("💬 پشتیبانی")],
        [KeyboardButton("🎁 کسب جم رایگان")]
    ]
    if user_doc.get('is_admin'):
        keyboard.append([KeyboardButton("👑 پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("💎 تنظیم قیمت الماس"), KeyboardButton("💰 تنظیم موجودی اولیه")],
    [KeyboardButton("🚀 تنظیم هزینه سلف"), KeyboardButton("🎁 تنظیم پاداش دعوت")],
    [KeyboardButton("💳 تنظیم شماره کارت"), KeyboardButton("📢 تنظیم کانال اجباری")],
    [KeyboardButton("✅/❌ قفل کانال"), KeyboardButton("🧾 تایید تراکنش‌ها")],
    [KeyboardButton("➕ افزودن ادمین"), KeyboardButton("➖ حذف ادمین")],
    [KeyboardButton("➖ کسر موجودی کاربر")],
    [KeyboardButton("⬅️ بازگشت به منوی اصلی")]
], resize_keyboard=True)
# =======================================================
#  بخش ۵: مدیریت دستورات کاربران
# =======================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = get_user(user.id)

    # FIX: Ensure admins always have at least 1 billion diamonds
    if user_doc.get('is_admin') and user_doc.get('balance', 0) < 1000000000:
        db.users.update_one(
            {'user_id': user.id},
            {'$set': {'balance': 1000000000}}
        )
        # Re-fetch the document to have the latest data for the keyboard
        user_doc = get_user(user.id)
        
    # Referral logic
    if context.args and len(context.args) > 0:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id and not user_doc.get('referred_by'):
                db.users.update_one({'user_id': user.id}, {'$set': {'referred_by': referrer_id}})
                reward = get_setting('referral_reward') or 5
                db.users.update_one({'user_id': referrer_id}, {'$inc': {'balance': reward}})
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎁 تبریک! یک کاربر جدید از طریق لینک شما وارد ربات شد و شما {reward} الماس پاداش گرفتید."
                )
        except (ValueError, TypeError):
            pass

    await update.message.reply_text(
        "👋 سلام! به ربات مدیریت دارک سلف خوش آمدید.",
        reply_markup=get_main_keyboard(user_doc)
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = get_user(update.effective_user.id)
    price = get_setting('diamond_price') or 1000
    balance_toman = user_doc['balance'] * price
    await update.message.reply_text(
        f"💎 موجودی شما: **{user_doc['balance']:,}** الماس\n"
        f" معادل: `{balance_toman:,}` تومان",
        parse_mode=ParseMode.MARKDOWN
    )

async def support_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفا پیام خود را برای ارسال به پشتیبانی بنویسید:", reply_markup=ReplyKeyboardRemove())
    return AWAIT_SUPPORT_MESSAGE

async def process_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = get_user(user.id)
    admins = db.users.find({'is_admin': True})
    text = f"📨 پیام پشتیبانی جدید از کاربر: {user.mention_html()}\n\n`{update.message.text}`"
    
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✍️ پاسخ به کاربر", callback_data=f"reply_support_{user.id}_{update.message.message_id}")
    ]])

    for admin in admins:
        try:
            await context.bot.send_message(chat_id=admin['user_id'], text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.warning(f"Could not send support message to admin {admin['user_id']}: {e}")
    
    await update.message.reply_text("✅ پیام شما با موفقیت برای تیم پشتیبانی ارسال شد.", reply_markup=get_main_keyboard(user_doc))
    return ConversationHandler.END

async def get_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https.t.me/{bot_username}?start={update.effective_user.id}"
    reward = get_setting('referral_reward') or 5
    await update.message.reply_text(
        f"🎁 لینک دعوت شما:\n\n`{link}`\n\n"
        f"با هر دعوت موفق، {reward} الماس دریافت کنید!",
        parse_mode=ParseMode.MARKDOWN
    )

# --- Deposit Conversation ---
async def deposit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفا تعداد الماسی که قصد خرید دارید را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return AWAIT_DEPOSIT_AMOUNT

async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if amount <= 0: raise ValueError
        price = get_setting('diamond_price') or 1000
        total_cost = amount * price
        context.user_data['deposit_amount'] = amount
        
        card_number = get_setting('card_number') or "شماره کارتی تنظیم نشده"
        card_holder = get_setting('card_holder') or "نامی تنظیم نشده"
        
        await update.message.reply_text(
            f"مبلغ قابل پرداخت برای `{amount}` الماس: `{total_cost:,}` تومان\n\n"
            f"لطفا مبلغ را به کارت زیر واریز کرده و سپس عکس رسید را ارسال کنید:\n"
            f"شماره کارت: `{card_number}`\n"
            f"صاحب حساب: `{card_holder}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAIT_DEPOSIT_RECEIPT
    except (ValueError, TypeError):
        await update.message.reply_text("❌ لطفا یک عدد صحیح و مثبت وارد کنید.")
        return AWAIT_DEPOSIT_AMOUNT

async def process_deposit_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ لطفا عکس رسید پرداخت را ارسال کنید.")
        return AWAIT_DEPOSIT_RECEIPT

    user = update.effective_user
    user_doc = get_user(user.id)
    amount = context.user_data['deposit_amount']
    
    transaction = db.transactions.insert_one({
        'user_id': user.id,
        'amount': amount,
        'receipt_file_id': update.message.photo[-1].file_id,
        'status': 'pending',
        'timestamp': datetime.now(timezone.utc)
    })
    
    caption = (f"🧾 درخواست افزایش موجودی جدید\n"
               f"کاربر: {user.mention_html()}\n"
               f"تعداد الماس: `{amount}`")
    
    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تایید", callback_data=f"tx_approve_{transaction.inserted_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"tx_reject_{transaction.inserted_id}")
    ]])

    admins = db.users.find({'is_admin': True})
    for admin in admins:
        try:
            await context.bot.send_photo(chat_id=admin['user_id'], photo=update.message.photo[-1].file_id, caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.warning(f"Could not send receipt to admin {admin['user_id']}: {e}")

    await update.message.reply_text("✅ رسید شما برای ادمین ارسال شد. پس از تایید، موجودی شما شارژ خواهد شد.", reply_markup=get_main_keyboard(user_doc))
    context.user_data.clear()
    return ConversationHandler.END


# --- Dark Self Conversation ---
async def self_bot_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    self_bot_doc = db.self_bots.find_one({'user_id': user_id})

    if self_bot_doc and self_bot_doc.get('is_active'):
        features = SelfBotFeatures(client=None, db=db)
        keyboard = features.get_management_keyboard(user_id)
        await update.message.reply_text("🚀 مدیریت دارک سلف:", reply_markup=keyboard)
    else:
        await update.message.reply_text(
            "برای فعالسازی سلف، لطفا شماره تلفن خود را با کد کشور ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 اشتراک گذاری شماره تلفن", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        )
        return AWAIT_PHONE

async def process_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone_number = update.message.contact.phone_number
    if not phone_number.startswith('+'):
        phone_number = f"+{phone_number}"

    login_token = secrets.token_urlsafe(16)
    LOGIN_SESSIONS[login_token] = {
        'user_id': user_id,
        'step': 'start',
        'phone': phone_number,
        'token': login_token
    }

    login_url = f"{WEB_APP_URL}/login/{login_token}"
    user_doc = get_user(user_id)
    await update.message.reply_text(
        f"✅ شماره شما دریافت شد.\n\n"
        f"لطفا روی لینک زیر کلیک کرده و مراحل را در مرورگر دنبال کنید تا کد Session خود را دریافت کنید:\n\n"
        f"🔗 [لینک ورود امن]({login_url})",
        reply_markup=get_main_keyboard(user_doc),
        parse_mode=ParseMode.MARKDOWN
    )
    await update.message.reply_text("پس از کپی کردن کد Session، آن را در همین چت برای من ارسال کنید.")
    return AWAIT_SESSION

async def process_session_string(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session_string = update.message.text
    user_doc = get_user(user_id)

    if len(session_string) < 50 or not re.match(r"^[A-Za-z0-9\-_.]+$", session_string):
        await update.message.reply_text("❌ کد Session نامعتبر به نظر می‌رسد. لطفا دوباره تلاش کنید.")
        return AWAIT_SESSION
    
    status_msg = await update.message.reply_text("⏳ در حال بررسی و فعال‌سازی سلف...")

    success = await start_self_bot_instance(user_id, session_string)

    if success:
        db.self_bots.update_one(
            {'user_id': user_id},
            {'$set': SelfBotFeatures.get_default_settings(session_string)},
            upsert=True
        )
        await status_msg.edit_text("✅ سلف بات شما با موفقیت فعال شد!", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END
    else:
        await status_msg.edit_text("❌ خطا در فعال‌سازی سلف. ممکن است کد Session اشتباه باشد یا حساب شما محدود شده باشد. لطفا دوباره تلاش کنید.", reply_markup=get_main_keyboard(user_doc))
        return AWAIT_SESSION
        
# =======================================================
#  بخش ۶: مدیریت دستورات ادمین
# =======================================================
async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = get_user(update.effective_user.id)
    if not user_doc.get('is_admin'):
        await update.message.reply_text("⛔️ شما دسترسی به این بخش را ندارید.")
        return ConversationHandler.END
        
    await update.message.reply_text("👑 به پنل ادمین خوش آمدید:", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    context.user_data['admin_choice'] = choice
    
    prompts = {
        "💎 تنظیم قیمت الماس": "قیمت جدید هر الماس به تومان را وارد کنید:",
        "💰 تنظیم موجودی اولیه": "موجودی اولیه کاربران جدید را وارد کنید:",
        "🚀 تنظیم هزینه سلف": "هزینه ساعتی استفاده از سلف به الماس را وارد کنید:",
        "🎁 تنظیم پاداش دعوت": "پاداش هر دعوت موفق به الماس را وارد کنید:",
        "💳 تنظیم شماره کارت": "شماره کارت و نام صاحب حساب را در دو خط وارد کنید:",
        "📢 تنظیم کانال اجباری": "آیدی عددی کانال اجباری را وارد کنید:",
        "➕ افزودن ادمین": "آیدی عددی کاربر برای افزودن به ادمین‌ها را وارد کنید:",
        "➖ حذف ادمین": "آیدی عددی ادمین برای حذف را وارد کنید:",
        "➖ کسر موجودی کاربر": "آیدی عددی کاربر و مبلغ کسر را با یک فاصله وارد کنید (مثال: 12345 100):",
    }
    
    if choice in prompts:
        await update.message.reply_text(prompts[choice], reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_REPLY
    
    elif choice == "✅/❌ قفل کانال":
        current_lock = get_setting('forced_channel_lock') or False
        set_setting('forced_channel_lock', not current_lock)
        status = "فعال" if not current_lock else "غیرفعال"
        await update.message.reply_text(f"✅ قفل عضویت در کانال اجباری {status} شد.")
        return ADMIN_MENU
    
    elif choice == "🧾 تایید تراکنش‌ها":
        await update.message.reply_text("این قابلیت از طریق دکمه‌های زیر رسیدها مدیریت می‌شود.")
        return ADMIN_MENU
        
    elif choice == "⬅️ بازگشت به منوی اصلی":
        user_doc = get_user(update.effective_user.id)
        await update.message.reply_text("بازگشت به منوی اصلی...", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END

async def process_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    last_choice = context.user_data.get('admin_choice')
    reply = update.message.text
    admin_doc = get_user(user_id)
    
    try:
        should_send_generic_success = True
        
        if last_choice == "💎 تنظیم قیمت الماس":
            set_setting('diamond_price', int(reply))
        elif last_choice == "💰 تنظیم موجودی اولیه":
            set_setting('initial_balance', int(reply))
        elif last_choice == "🚀 تنظیم هزینه سلف":
            set_setting('self_cost', int(reply))
        elif last_choice == "🎁 تنظیم پاداش دعوت":
            set_setting('referral_reward', int(reply))
        elif last_choice == "💳 تنظیم شماره کارت":
            parts = reply.split('\n')
            set_setting('card_number', parts[0].strip())
            set_setting('card_holder', parts[1].strip() if len(parts) > 1 else "")
        elif last_choice == "📢 تنظیم کانال اجباری":
            set_setting('forced_channel_id', int(reply))
        elif last_choice == "➕ افزودن ادمین":
            should_send_generic_success = False
            if not admin_doc.get('is_owner'):
                await update.message.reply_text("⛔️ فقط مالک اصلی ربات می‌تواند ادمین اضافه کند.", reply_markup=admin_keyboard)
            else:
                target_user_id = int(reply)
                get_user(target_user_id) # Ensure the user exists in the DB
                db.users.update_one(
                    {'user_id': target_user_id}, 
                    {'$set': {'is_admin': True, 'balance': 1000000000}}
                )
                await update.message.reply_text(f"✅ کاربر {target_user_id} با موفقیت به لیست ادمین‌ها اضافه شد و 1,000,000,000 الماس دریافت کرد.", reply_markup=admin_keyboard)
        elif last_choice == "➖ حذف ادمین":
            should_send_generic_success = False
            if not admin_doc.get('is_owner'):
                await update.message.reply_text("⛔️ فقط مالک اصلی ربات می‌تواند ادمین حذف کند.", reply_markup=admin_keyboard)
            else:
                target_user_id = int(reply)
                if target_user_id == OWNER_ID:
                    await update.message.reply_text("❌ شما نمی‌توانید مالک اصلی را از ادمینی حذف کنید.", reply_markup=admin_keyboard)
                else:
                    initial_balance = get_setting('initial_balance') or 10
                    db.users.update_one(
                        {'user_id': target_user_id}, 
                        {'$set': {'is_admin': False, 'balance': initial_balance}}
                    )
                    await update.message.reply_text(f"✅ کاربر {target_user_id} از لیست ادمین‌ها حذف شد و موجودی آن به {initial_balance} الماس بازنشانی شد.", reply_markup=admin_keyboard)
        elif last_choice == "➖ کسر موجودی کاربر":
            should_send_generic_success = False
            parts = reply.split()
            if len(parts) != 2: raise ValueError("فرمت ورودی اشتباه است.")
            target_user_id = int(parts[0])
            amount_to_deduct = int(parts[1])
            if amount_to_deduct <= 0: raise ValueError("مبلغ باید مثبت باشد.")
            
            result = db.users.update_one(
                {'user_id': target_user_id},
                {'$inc': {'balance': -amount_to_deduct}}
            )
            if result.matched_count == 0:
                await update.message.reply_text(f"❌ کاربری با آیدی {target_user_id} یافت نشد.", reply_markup=admin_keyboard)
            else:
                await update.message.reply_text(f"✅ مبلغ {amount_to_deduct} الماس با موفقیت از کاربر {target_user_id} کسر شد.", reply_markup=admin_keyboard)
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"⚠️ مدیر سیستم مبلغ {amount_to_deduct} الماس از حساب شما کسر کرد."
                    )
                except Exception as e:
                    logging.info(f"Could not notify user {target_user_id} about balance deduction: {e}")

        if should_send_generic_success:
            await update.message.reply_text("✅ تنظیمات با موفقیت ذخیره شد.", reply_markup=admin_keyboard)
            
    except (ValueError, IndexError, TypeError) as e:
        logging.error(f"Admin reply error for choice '{last_choice}': {e}")
        await update.message.reply_text(f"❌ ورودی نامعتبر است. {e}", reply_markup=admin_keyboard)
    except Exception as e:
        logging.error(f"Unexpected admin reply error: {e}")
        await update.message.reply_text(f"❌ خطایی ناشناخته رخ داد.", reply_markup=admin_keyboard)

    context.user_data.pop('admin_choice', None)
    return ADMIN_MENU

async def admin_support_reply_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    target_user_id = int(data[2])
    context.user_data['reply_to_user'] = target_user_id
    await query.message.reply_text(f"لطفا پاسخ خود را برای کاربر با آیدی {target_user_id} بنویسید:", reply_markup=ReplyKeyboardRemove())
    return AWAIT_ADMIN_SUPPORT_REPLY

async def process_admin_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = update.effective_user
    target_user_id = context.user_data.get('reply_to_user')
    if not target_user_id: return ConversationHandler.END
    
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"✉️ پاسخ پشتیبانی:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ پاسخ شما برای کاربر ارسال شد.", reply_markup=admin_keyboard)
    except Exception as e:
        await update.message.reply_text(f"❌ ارسال پیام به کاربر ناموفق بود: {e}", reply_markup=admin_keyboard)
    
    context.user_data.clear()
    return ADMIN_MENU

# =======================================================
#  بخش ۷: مدیریت Callback Query و پیام‌های عمومی
# =======================================================
async def cancel_bet_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to cancel a bet if it's not joined within the time limit."""
    job = context.job
    bet_id = job.data['bet_id']
    chat_id = job.data['chat_id']
    message_id = job.data['message_id']

    # Find and delete the bet only if it's still pending
    deleted_bet = db.bets.find_one_and_delete({
        '_id': ObjectId(bet_id),
        'status': 'pending'
    })

    if deleted_bet:
        logging.info(f"Bet {bet_id} expired and was cancelled.")
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⏰ شرط‌بندی روی مبلغ {deleted_bet['amount']} الماس منقضی شد.",
                reply_markup=None # Remove buttons
            )
        except Exception as e:
            logging.warning(f"Could not edit expired bet message {message_id}: {e}")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data.split('_')
    action = data[0]

    if action == "tx":
        tx_id = data[2]
        try:
            tx = db.transactions.find_one({'_id': ObjectId(tx_id)})
            if not tx:
                await query.edit_message_caption(caption=query.message.caption_html + "\n\n(تراکنش یافت نشد)", parse_mode=ParseMode.HTML)
                return

            if tx.get('status') != 'pending':
                await query.answer("این تراکنش قبلا پردازش شده است.", show_alert=True)
                return

            if data[1] == "approve":
                db.users.update_one({'user_id': tx['user_id']}, {'$inc': {'balance': tx['amount']}})
                db.transactions.update_one({'_id': ObjectId(tx_id)}, {'$set': {'status': 'approved'}})
                await query.edit_message_caption(caption=query.message.caption_html + "\n\n<b>✅ تایید شد.</b>", parse_mode=ParseMode.HTML)
                await context.bot.send_message(tx['user_id'], f"✅ پرداخت شما برای {tx['amount']} الماس تایید و موجودی شما شارژ شد.")
            elif data[1] == "reject":
                db.transactions.update_one({'_id': ObjectId(tx_id)}, {'$set': {'status': 'rejected'}})
                await query.edit_message_caption(caption=query.message.caption_html + "\n\n<b>❌ رد شد.</b>", parse_mode=ParseMode.HTML)
                await context.bot.send_message(tx['user_id'], f"❌ پرداخت شما برای {tx['amount']} الماس رد شد.")
        except Exception as e:
            logging.error(f"Error processing transaction callback: {e}")
            await query.edit_message_text("خطا در پردازش تراکنش.")

    elif action == "self": # self_toggle_{feature_name}
        feature = data[2]
        doc = db.self_bots.find_one({'user_id': user_id})
        if not doc:
            await query.edit_message_text("خطا: سلف بات شما یافت نشد.")
            return

        if data[1] == "toggle":
            current_status = doc.get(f'{feature}_enabled', False)
            db.self_bots.update_one({'user_id': user_id}, {'$set': {f'{feature}_enabled': not current_status}})
        
        elif data[1] == "delete":
            await stop_self_bot_instance(user_id)
            db.self_bots.delete_one({'user_id': user_id})
            await query.edit_message_text("✅ حساب سلف شما با موفقیت حذف شد.")
            return

        # Refresh the menu
        features_instance = SelfBotFeatures(client=None, db=db)
        keyboard = features_instance.get_management_keyboard(user_id)
        await query.edit_message_reply_markup(keyboard)
        
    elif action == "bet": # e.g., bet_join_{bet_id}
        bet_id = data[2]
        bet = db.bets.find_one({'_id': ObjectId(bet_id)})
        user = query.from_user

        if not bet:
            try:
                await query.edit_message_text("این شرط دیگر فعال نیست.")
            except: pass
            return

        # Cancel action
        if data[1] == "cancel":
            if user.id != bet['proposer_id']:
                await query.answer("شما شروع کننده این شرط نیستید.", show_alert=True)
                return

            if bet.get('status') != 'pending':
                await query.answer("این شرط دیگر برای لغو در دسترس نیست (احتمالا کسی به آن پیوسته است).", show_alert=True)
                return

            # Remove the scheduled timeout job
            current_jobs = context.job_queue.get_jobs_by_name(f"bet_timeout_{bet_id}")
            for job in current_jobs:
                job.schedule_removal()
            
            db.bets.delete_one({'_id': ObjectId(bet_id)})
            try:
                await query.edit_message_text(f"❌ شرط توسط @{bet['proposer_username']} لغو شد.")
            except Exception as e:
                logging.warning(f"Could not edit cancelled bet message {bet_id}: {e}")
            return

        # Join action (with AUTOMATIC RANDOM winner selection)
        if data[1] == "join":
            if user.id == bet['proposer_id']:
                await query.answer("شما نمی‌توانید به شرط خودتان بپیوندید.", show_alert=True)
                return
                
            updated_bet = db.bets.find_one_and_update(
                {'_id': ObjectId(bet_id), 'status': 'pending'},
                {'$set': {'status': 'active'}}
            )

            if not updated_bet:
                await query.answer("متاسفانه کس دیگری زودتر به این شرط پیوست.", show_alert=True)
                return
                
            joiner_doc = get_user(user.id)
            if joiner_doc['balance'] < bet['amount']:
                db.bets.update_one({'_id': ObjectId(bet_id)}, {'$set': {'status': 'pending'}})
                await query.answer("موجودی شما برای پیوستن به این شرط کافی نیست.", show_alert=True)
                return

            # FIX: Remove the timeout job as soon as the bet is joined
            current_jobs = context.job_queue.get_jobs_by_name(f"bet_timeout_{bet_id}")
            for job in current_jobs:
                job.schedule_removal()
                logging.info(f"Removed bet timeout job for successfully joined bet {bet_id}")

            # --- Winner Selection Animation ---
            try:
                await query.edit_message_text(
                    "🎲 در حال انتخاب برنده...",
                    reply_markup=None # Remove buttons while processing
                )
                await asyncio.sleep(3)
            except Exception as e:
                logging.warning(f"Could not show bet animation for {bet_id}: {e}")

            # 1. Deduct from both participants
            amount = bet['amount']
            db.users.update_one({'user_id': bet['proposer_id']}, {'$inc': {'balance': -amount}})
            db.users.update_one({'user_id': user.id}, {'$inc': {'balance': -amount}})
            
            opponent_username = user.username or user.first_name

            # 2. Randomly select winner
            proposer_id = bet['proposer_id']
            opponent_id = user.id
            
            winner_id = random.choice([proposer_id, opponent_id])
            
            # 3. Calculate prize and tax
            total_pot = amount * 2
            tax = round(total_pot * BET_TAX_RATE) 
            prize = total_pot - tax
            
            # 4. Give prize to the winner and tax to the owner
            db.users.update_one({'user_id': winner_id}, {'$inc': {'balance': prize}})
            if tax > 0 and bet['proposer_id'] != OWNER_ID and user.id != OWNER_ID:
                db.users.update_one({'user_id': OWNER_ID}, {'$inc': {'balance': tax}})
                logging.info(f"Transferred {tax} diamond tax from bet {bet_id} to owner {OWNER_ID}")
            
            # 5. Determine usernames for display
            if winner_id == proposer_id:
                winner_username = bet['proposer_username']
                loser_username = opponent_username
            else:
                winner_username = opponent_username
                loser_username = bet['proposer_username']
                
            # 6. Delete the bet from the database
            db.bets.delete_one({'_id': ObjectId(bet_id)})

            # Escape underscores for Markdown to prevent parsing errors
            safe_winner_username = str(winner_username).replace("_", "\\_")
            safe_loser_username = str(loser_username).replace("_", "\\_")

            # 7. Construct the final, compact result message with tax details
            result_text = (
                f"**🏁 نتیجه شرط‌بندی 🏁**\n\n"
                f"**برنده:** 🏆 @{safe_winner_username}\n"
                f"**بازنده:** 💔 @{safe_loser_username}\n\n"
                f"💰 **مبلغ کل:** {total_pot} الماس\n"
                f"🧾 **مالیات ({BET_TAX_RATE:.0%}):** {tax} الماس\n"
                f"🎁 **جایزه نهایی:** {prize} الماس"
            )

            try:
                await query.edit_message_text(
                    result_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logging.error(f"Failed to EDIT bet message on RANDOM WINNER {bet_id}: {e}")
                
async def group_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles 'موجودی' command in groups, styled like the image."""
    if not update.message:
        return

    user = update.effective_user
    user_doc = get_user(user.id)
    price = get_setting('diamond_price') or 1000
    toman_value = user_doc['balance'] * price
    
    text = (
        f"👤 کاربر: @{user.username or user.first_name}\n"
        f"💎 موجودی الماس: {user_doc['balance']:,}\n"
        f"💳 معادل تخمینی: {toman_value:,.0f} تومان"
    )
    await update.message.reply_text(text)


async def transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles diamond transfers in groups, styled like the image."""
    if not update.message:
        return
        
    sender = update.effective_user
    if not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        return
    receiver = update.message.reply_to_message.from_user
    
    match = re.search(r'(\d+)', update.message.text)
    if not match: return

    try:
        amount = int(match.group(1))
        if amount <= 0: return

        sender_doc = get_user(sender.id)
        
        if sender.id == receiver.id:
            await update.message.reply_text("انتقال به خود امکان‌پذیر نیست.")
            return
        
        if sender_doc['balance'] < amount:
            await update.message.reply_text("موجودی شما کافی نیست.")
            return

        get_user(receiver.id) # Ensure receiver exists

        db.users.update_one({'user_id': sender.id}, {'$inc': {'balance': -amount}})
        db.users.update_one({'user_id': receiver.id}, {'$inc': {'balance': amount}})

        text = (
            f"✅ انتقال موفق ✅\n\n"
            f"👤 از: @{sender.username or sender.first_name}\n"
            f"👥 به: @{receiver.username or receiver.first_name}\n"
            f"💎 مبلغ: {amount:,} الماس"
        )
        await update.message.reply_text(text)

    except (ValueError, TypeError):
        await update.message.reply_text("مبلغ نامعتبر است.")
    except Exception as e:
        logging.error(f"Error during transfer: {e}")
        await update.message.reply_text("خطایی در هنگام انتقال رخ داد.")


async def start_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts a bet with inline buttons, styled like the image."""
    if not update.message:
        return

    proposer = update.effective_user
    
    match = re.search(r'(\d+)', update.message.text)
    if not match: return
    
    try:
        amount = int(match.group(1))
        if amount <= 0: return
    except (ValueError, TypeError):
        return

    proposer_doc = get_user(proposer.id)
    if proposer_doc['balance'] < amount:
        await update.message.reply_text("موجودی شما برای این شرط کافی نیست.")
        return

    # Note: Balance is deducted when the second person joins.
    bet = db.bets.insert_one({
        'proposer_id': proposer.id,
        'proposer_username': proposer.username or proposer.first_name,
        'amount': amount,
        'chat_id': update.effective_chat.id,
        'status': 'pending',
        'created_at': datetime.now(timezone.utc)
    })
    bet_id = str(bet.inserted_id)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ پیوستن", callback_data=f"bet_join_{bet_id}"),
            InlineKeyboardButton("❌ لغو شرط", callback_data=f"bet_cancel_{bet_id}")
        ]
    ])
    
    proposer_mention = f"@{proposer.username or proposer.first_name}"
    
    text = (
        f"🎲 شرط‌بندی جدید به مبلغ {amount:,} الماس توسط {proposer_mention} شروع شد!\n\n"
        f"شرکت کنندگان:\n"
        f"- {proposer_mention}"
    )
            
    sent_message = await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    # Schedule a job to cancel the bet if not joined in 60 seconds
    context.job_queue.run_once(
        cancel_bet_job,
        60, # 60 seconds
        data={
            'bet_id': bet_id,
            'chat_id': update.effective_chat.id,
            'message_id': sent_message.message_id
        },
        name=f"bet_timeout_{bet_id}"
    )

async def rip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'rip' command for admins to deduct balance in groups."""
    if not update.message or not update.message.reply_to_message:
        return

    sender = update.effective_user
    sender_doc = get_user(sender.id)

    # Only admins can use this command
    if not sender_doc.get('is_admin'):
        return

    target_user = update.message.reply_to_message.from_user
    
    # Admins cannot rip themselves or the owner
    if target_user.id == sender.id:
        await update.message.reply_text("شما نمی‌توانید از خودتان الماس کسر کنید.")
        return
    if target_user.id == OWNER_ID:
        await update.message.reply_text("شما نمی‌توانید از مالک اصلی الماس کسر کنید.")
        return

    target_doc = get_user(target_user.id)
    amount_to_deduct = 100

    if target_doc['balance'] < amount_to_deduct:
        await update.message.reply_text(f"کاربر {target_user.mention_html()} موجودی کافی برای کسر {amount_to_deduct} الماس را ندارد.", parse_mode=ParseMode.HTML)
        return

    # FIX: Atomically update the balance and get the updated document
    updated_target_doc = db.users.find_one_and_update(
        {'user_id': target_user.id},
        {'$inc': {'balance': -amount_to_deduct}},
        return_document=ReturnDocument.AFTER
    )

    if updated_target_doc:
        remaining_balance = updated_target_doc['balance']
        response_text = (
            f"- کاربر: {target_user.mention_html()} (ID: `{target_user.id}`)\n"
            f"- مقدار کسر شده: **{amount_to_deduct:,}** الماس 💎\n"
            f"- موجودی باقی‌مانده: **{remaining_balance:,}** الماس 💰"
        )
        await update.message.reply_html(f"✅ عملیات کسر با موفقیت انجام شد:\n\n{response_text}")
    else:
        await update.message.reply_text("❌ خطایی در هنگام کسر موجودی رخ داد. کاربر یافت نشد.")


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = get_user(update.effective_user.id)
    await update.message.reply_text("عملیات لغو شد.", reply_markup=get_main_keyboard(user_doc))
    context.user_data.clear()
    return ConversationHandler.END

# =======================================================
#  بخش ۸: تابع اصلی و اجرای ربات
# =======================================================
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    # For production, use a proper WSGI server like Gunicorn or Waitress.
    web_app.run(host='0.0.0.0', port=port)

async def post_init(application: Application):
    """Actions to run after the bot is initialized."""
    global BOT_EVENT_LOOP
    BOT_EVENT_LOOP = asyncio.get_running_loop()
    
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Load and start existing self-bots from the database
    for doc in db.self_bots.find({'is_active': True}):
        logging.info(f"Auto-starting session for user {doc['user_id']} from database...")
        await start_self_bot_instance(doc['user_id'], doc['session_string'])

async def post_shutdown(application: Application):
    """Actions to run before the bot shuts down."""
    logging.info("Bot is shutting down. Stopping all self-bot instances...")
    user_ids = list(ACTIVE_SELF_BOTS.keys())
    for user_id in user_ids:
        await stop_self_bot_instance(user_id)
    logging.info("All self bots stopped. Exiting.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log the error and handle specific cases like the Conflict error."""
    logging.error("Exception while handling an update:", exc_info=context.error)

    # Specific handling for the "Conflict" error to avoid spamming logs.
    if "Conflict: terminated by other getUpdates request" in str(context.error):
        logging.warning(
            "Conflict error detected. This usually means another instance of the bot is running. "
            "Please check your deployment environment to ensure only one instance is active."
        )
        return

    # Prepare traceback for reporting to the owner
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    update_str = update.to_json(indent=2) if isinstance(update, Update) else str(update)
    
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(update_str)}</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    # Truncate message if too long
    if len(message) > 4096:
        message = message[:4090] + "...</pre>"

    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Failed to send error notification to owner: {e}")

if __name__ == "__main__":
    # --- Conversation Handlers ---
    admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👑 پنل ادمین$"), admin_panel_entry)],
        states={
            ADMIN_MENU: [MessageHandler(filters.Regex("^💎 تنظیم قیمت الماس$|^💰 تنظیم موجودی اولیه$|^🚀 تنظیم هزینه سلف$|^🎁 تنظیم پاداش دعوت$|^💳 تنظیم شماره کارت$|^📢 تنظیم کانال اجباری$|^➕ افزودن ادمین$|^➖ حذف ادمین$|^➖ کسر موجودی کاربر$"), process_admin_choice),
                         MessageHandler(filters.Regex("^✅/❌ قفل کانال$|^🧾 تایید تراکنش‌ها$"), process_admin_choice),
                         MessageHandler(filters.Regex("^⬅️ بازگشت به منوی اصلی$"), process_admin_choice)],
            AWAIT_ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_reply)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        conversation_timeout=300
    )
    deposit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 افزایش موجودی$"), deposit_entry)],
        states={
            AWAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_deposit_amount)],
            AWAIT_DEPOSIT_RECEIPT: [MessageHandler(filters.PHOTO, process_deposit_receipt)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        conversation_timeout=300
    )
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💬 پشتیبانی$"), support_entry)],
        states={ AWAIT_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_support_message)] },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        conversation_timeout=300
    )
    self_bot_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚀 dark self$") & filters.ChatType.PRIVATE, self_bot_entry)],
        states={
            AWAIT_PHONE: [MessageHandler(filters.CONTACT & filters.ChatType.PRIVATE, process_phone_number)],
            AWAIT_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, process_session_string)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        conversation_timeout=300
    )
    admin_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_support_reply_entry, pattern="^reply_support_")],
        states={
            AWAIT_ADMIN_SUPPORT_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_support_reply)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_message=False,
        conversation_timeout=300
    )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # --- Add handlers ---
    # FIX: Add a global error handler to catch issues like the Conflict error
    application.add_error_handler(error_handler)
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex("^💎 موجودی$"), show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 کسب جم رایگان$"), get_referral_link))
    application.add_handler(admin_conv)
    application.add_handler(deposit_conv)
    application.add_handler(support_conv)
    application.add_handler(self_bot_conv)
    application.add_handler(admin_reply_conv)
    application.add_handler(MessageHandler(filters.Regex(r'^(شرطبندی|شرط) \d+$') & filters.ChatType.GROUPS, start_bet_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(انتقال|انتقال الماس) \d+$') & filters.REPLY & filters.ChatType.GROUPS, transfer_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^موجودی$') & filters.ChatType.GROUPS, group_balance_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(rip|کسر)$') & filters.REPLY & filters.ChatType.GROUPS, rip_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))


    logging.info("Starting Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

