import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid
)
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, render_template_string, redirect, session, url_for
from threading import Thread
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# ⚠️ Main Settings (Enter your API_ID and API_HASH here)
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://CFNBEFBGWFB:hdhbedfefbegh@cluster0.obohcl3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = None
sessions_collection = None
if MONGO_URI and "<db_password>" not in MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        logging.info("Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
else:
    logging.warning("MONGO_URI is not configured correctly. Please set your password. Session persistence will be disabled.")


# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Clock Font Dictionaries ---
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'７','8':'８','9':'９',':':'：'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth"]
FONT_DISPLAY_NAMES = {
    "cursive": "کشیده", "stylized": "فانتزی", "doublestruck": "توخالی",
    "monospace": "کامپیوتری", "normal": "ساده", "circled": "دایره‌ای", "fullwidth": "پهن"
}
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"


# --- Feature Variables ---
ENEMY_REPLIES = [
    "کیرم تو رحم اجاره ای و خونی مالی مادرت", "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام و اب کوسشو بریزم کف خونه تا فردا صبح کارگرای افغانی برای نظافت اومدن با بوی اب کس مادرت بجقن و ابکیراشون نثار قبر مرده هات بشه", "احمق مادر کونی من کس مادرت گذاشتم تو بازم داری کسشر میگی", "هی بیناموس کیرم بره تو کس ننت واس بابات نشآخ مادر کیری کیرم بره تو کس اجدادت کسکش بیناموس کس ول نسل شوتی ابجی کسده کیرم تو کس مادرت بیناموس کیری کیرم تو کس نسلت ابجی کونی کس نسل سگ ممبر کونی ابجی سگ ممبر سگ کونی کیرم تو کس ننت کیر تو کس مادرت کیر خاندان  تو کس نسلت مادر کونی ابجی کونی کیری ناموس ابجیتو گاییدم سگ حرومی خارکسه مادر کیری با کیر بزنم تو رحم مادرت ناموستو بگام لاشی کونی ابجی کس  خیابونی مادرخونی ننت کیرمو میماله تو میای کص میگی شاخ نشو ییا ببین شاخو کردم تو کون ابجی جندت کس ابجیتو پاره کردم تو شاخ میشی اوبی",
    "کیرم تو کس سیاه مادرت خارکصده", "حروم زاده باک کص ننت با ابکیرم پر میکنم", "منبع اب ایرانو با اب کص مادرت تامین میکنم", "خارکسته میخای مادرتو بگام بعد بیای ادعای شرف کنی کیرم تو شرف مادرت",
    "کیرم تویه اون خرخره مادرت بیا اینحا ببینم تویه نوچه کی دانلود شدی کیفیتت پایینه صدات نمیاد فقط رویه حالیت بی صدا داری امواج های بی ارزش و بیناموسانه از خودت ارسال میکنی که ناگهان دیدی من روانی شدم دست از پا خطا کردم با تبر کائنات کوبیدم رو سر مادرت نمیتونی مارو تازه بالقه گمان کنی", "کیرم تویه اون خرخره مادرت بیا اینحا ببینم تویه نوچه کی دانلود شدی کیفیتت پایینه صدات نمیاد فقط رویه حالیت بی صدا داری امواج های بی ارزش و بیناموسانه از خودت ارسال میکنی که ناگهان دیدی من روانی شدم دست از پا خطا کردم با تبر کائنات کوبیدم رو سر مادرت نمیتونی مارو تازه بالقه گمان کنی",
]
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."
HELP_TEXT = """
** راهنمای کامل دستورات سلف بات **

---
** وضعیت و قالب‌بندی **
 • `تایپ روشن` / `خاموش`: فعال‌سازی حالت "در حال تایپ" در همه چت‌ها.
 • `بازی روشن` / `خاموش`: فعال‌سازی حالت "در حال بازی" در همه چت‌ها.
 • `اینگیلیسی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به انگلیسی.
 • `روسی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به روسی.
 • `چینی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به چینی.
 • `بولد روشن` / `خاموش`: برجسته کردن خودکار تمام پیام‌ها.
 • `سین روشن` / `خاموش`: سین خودکار پیام‌ها در چت شخصی (PV).

---
** ساعت و فونت **
 • `ساعت روشن` / `خاموش`: نمایش یا حذف ساعت از نام پروفایل.
 • `فونت`: نمایش لیست فونت‌های ساعت.
 • `فونت [عدد]`: انتخاب فونت جدید برای ساعت.

---
** مدیریت پیام و کاربر **
 • `حذف [عدد]`: (مثال: `حذف 10`) حذف X پیام آخر شما در چت فعلی.
 • `ذخیره` (با ریپلای): ذخیره کردن پیام مورد نظر در Saved Messages.
 • `تکرار [عدد]` (با ریپلای): تکرار پیام تا سقف 100 بار.
 • `دشمن روشن` / `خاموش` (با ریپلای): فعال/غیرفعال کردن حالت دشمن برای کاربر.
 • `دشمن همگانی روشن` / `خاموش`: فعال/غیرفعال کردن حالت دشمن برای همه.
 • `لیست دشمن`: نمایش لیست تمام دشمنان فعال.
 • `بلاک روشن` / `خاموش` (با ریپلای): بلاک یا آنبلاک کردن کاربر.
 • `سکوت روشن` / `خاموش` (با ریپلای): حذف خودکار پیام‌های کاربر در چت فعلی.
 • `ریاکشن [ایموجی]` (با ریپلای): واکنش خودکار به پیام‌های کاربر با ایموجی دلخواه.
 • `ریاکشن خاموش` (با ریپلای): غیرفعال‌سازی واکنش خودکار برای کاربر.

---
** سرگرمی **
 • `تاس`: ارسال تاس شانسی. (نتیجه تاس شانسی است)
 • `بولینگ`: ارسال بولینگ شانسی.

---
** امنیت و منشی **
 • `پیوی قفل` / `باز`: تمام پیام‌های دریافتی در پیوی را به صورت خودکار حذف می‌کند.
 • `منشی روشن` / `خاموش`: فعال‌سازی پاسخ خودکار در PV.
 • `انتی لوگین روشن` / `خاموش`: خروج خودکار نشست‌های جدید از حساب شما.
 • `کپی روشن` (با ریپلای): کپی کردن پروفایل کاربر مورد نظر.
 • `کپی خاموش`: بازگرداندن پروفایل اصلی شما.
"""
COMMAND_REGEX = r"^(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز)$"


# --- User Status Management (based on User ID) ---
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
SECRETARY_MODE_STATUS = {}
USERS_REPLIED_IN_SECRETARY = {}
MUTED_USERS = {}
USER_FONT_CHOICES = {}
CLOCK_STATUS = {}
BOLD_MODE_STATUS = {}
AUTO_SEEN_STATUS = {}
AUTO_REACTION_TARGETS = {}
AUTO_TRANSLATE_TARGET = {}
ANTI_LOGIN_STATUS = {}
COPY_MODE_STATUS = {}
ORIGINAL_PROFILE_DATA = {}
GLOBAL_ENEMY_STATUS = {}
TYPING_MODE_STATUS = {}
PLAYING_MODE_STATUS = {}
PV_LOCK_STATUS = {}


EVENT_LOOP = asyncio.new_event_loop()
ACTIVE_CLIENTS = {}
ACTIVE_BOTS = {}

# --- Main Bot Functions ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def update_profile_clock(client: Client, user_id: int):
    log_message = f"Starting clock loop for user_id {user_id}..."
    logging.info(log_message)
    
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
                me = await client.get_me()
                current_name = me.first_name
                
                base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()

                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                current_time_str = tehran_time.strftime("%H:%M")
                stylized_time = stylize_time(current_time_str, current_font_style)
                new_name = f"{base_name} {stylized_time}"
                
                if new_name != current_name:
                    await client.update_profile(first_name=new_name)
            
            now = datetime.now(TEHRAN_TIMEZONE)
            sleep_duration = 60 - now.second + 0.1
            await asyncio.sleep(sleep_duration)
        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Clock Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except FloodWait as e:
            logging.warning(f"Clock Task: Flood wait of {e.value}s for user_id {user_id}.")
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            logging.error(f"An error in clock task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)
    
    logging.info(f"Clock task for user_id {user_id} has stopped.")


async def anti_login_task(client: Client, user_id: int):
    logging.info(f"Starting anti-login task for user_id {user_id}...")
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False):
                auths = await client.invoke(functions.account.GetAuthorizations())
                
                current_hash = None
                for auth in auths.authorizations:
                    if auth.current:
                        current_hash = auth.hash
                        break
                
                if current_hash:
                    for auth in auths.authorizations:
                        if auth.hash != current_hash:
                            await client.invoke(functions.account.ResetAuthorization(hash=auth.hash))
                            logging.info(f"Terminated a new session for user {user_id} with hash {auth.hash}")
                            device_info = f"{auth.app_name} on {auth.device_model} ({auth.platform}, {auth.system_version})"
                            location_info = f"from IP {auth.ip} in {auth.country}"
                            message_text = (
                                f"🚨 **هشدار امنیتی: نشست جدید خاتمه داده شد** 🚨\n\n"
                                f"یک دستگاه جدید تلاش کرد وارد حساب شما شود و دسترسی آن به صورت خودکار قطع شد.\n\n"
                                f"**جزئیات نشست:**\n"
                                f"- **دستگاه:** {device_info}\n"
                                f"- **مکان:** {location_info}\n"
                                f"- **زمان ورود:** {auth.date_created.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            await client.send_message("me", message_text)
            await asyncio.sleep(60) # Check every minute
        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Anti-Login Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except Exception as e:
            logging.error(f"An error in anti-login task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(120)

    logging.info(f"Anti-login task for user_id {user_id} has stopped.")


async def status_action_task(client: Client, user_id: int):
    logging.info(f"Starting status action task for user_id {user_id}...")
    chat_ids = []
    last_dialog_fetch = 0

    while user_id in ACTIVE_BOTS:
        try:
            typing_mode = TYPING_MODE_STATUS.get(user_id, False)
            playing_mode = PLAYING_MODE_STATUS.get(user_id, False)

            if not typing_mode and not playing_mode:
                await asyncio.sleep(2) # Sleep and check again if nothing is active
                continue

            action_to_send = ChatAction.TYPING if typing_mode else ChatAction.PLAYING

            # Refresh the dialog list every 5 minutes (300 seconds)
            now = asyncio.get_event_loop().time()
            if not chat_ids or (now - last_dialog_fetch > 300):
                logging.info(f"Refreshing dialog list for user_id {user_id}...")
                new_chat_ids = []
                async for dialog in client.get_dialogs(limit=50): # Increased limit
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chat_ids.append(dialog.chat.id)
                chat_ids = new_chat_ids
                last_dialog_fetch = now
                logging.info(f"Found {len(chat_ids)} chats to update.")

            if not chat_ids:
                logging.warning(f"No suitable chats found for user_id {user_id}.")
                await asyncio.sleep(30) # Wait a bit before trying to fetch dialogs again
                continue

            # Send action to all chats in the cached list
            for chat_id in chat_ids:
                try:
                    await client.send_chat_action(chat_id, action_to_send)
                except FloodWait as e:
                    logging.warning(f"Flood wait in status_action_task. Sleeping for {e.value}s.")
                    await asyncio.sleep(e.value)
                except Exception:
                    # Ignore errors for single chats (e.g., kicked from group)
                    pass
            
            # The action lasts for ~5 seconds, so we sleep for 4 to refresh it just before it expires.
            await asyncio.sleep(4)

        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Status Action Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except Exception as e:
            logging.error(f"An error in status action task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)
            
    logging.info(f"Status action task for user_id {user_id} has stopped.")


# --- Feature Handlers ---
async def translate_text(text: str, target_lang: str) -> str:
    if not text: return ""
    encoded_text = quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0][0][0]
    except Exception as e:
        logging.error(f"Translation failed: {e}")
    return text

async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    if not message.text or re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE):
        return
        
    original_text = message.text
    modified_text = original_text
    
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang:
        modified_text = await translate_text(modified_text, target_lang)
    
    if BOLD_MODE_STATUS.get(user_id, False):
        if not modified_text.startswith(('`', '**', '__', '~~', '||')):
            modified_text = f"**{modified_text}**"
            
    if modified_text != original_text:
        try:
            await message.edit_text(modified_text)
        except Exception as e:
            logging.warning(f"Could not modify outgoing message for user {user_id}: {e}")
    

async def enemy_handler(client, message):
    user_id = client.me.id
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        shuffled_replies = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
        ENEMY_REPLY_QUEUES[user_id] = shuffled_replies
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try:
        await message.reply_text(reply_text)
    except Exception as e:
        logging.warning(f"Could not reply to enemy for user_id {user_id}: {e}")


async def secretary_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if message.from_user:
        target_user_id = message.from_user.id
        if SECRETARY_MODE_STATUS.get(owner_user_id, False):
            replied_users = USERS_REPLIED_IN_SECRETARY.get(owner_user_id, set())
            if target_user_id in replied_users:
                return
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied_users.add(target_user_id)
                USERS_REPLIED_IN_SECRETARY[owner_user_id] = replied_users
            except Exception as e:
                logging.warning(f"Could not auto-reply for user_id {owner_user_id}: {e}")

async def pv_lock_handler(client, message):
    owner_user_id = client.me.id
    if PV_LOCK_STATUS.get(owner_user_id, False):
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Could not perform PV lock action for user {owner_user_id}: {e}")

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    
    reaction_map = AUTO_REACTION_TARGETS.get(user_id, {})
    target_key = message.from_user.id # Simplified key
    
    if emoji := reaction_map.get(target_key):
        try:
            await client.send_reaction(message.chat.id, message.id, emoji)
        except ReactionInvalid:
            await message.reply_text(f"⚠️ **خطا:** ایموجی `{emoji}` برای واکنش معتبر نیست.")
            if target_key in reaction_map: AUTO_REACTION_TARGETS[user_id].pop(target_key, None)
        except Exception as e:
            logging.error(f"Reaction error for user {user_id}: {e}", exc_info=True)

    muted_list = MUTED_USERS.get(user_id, set())
    if (message.from_user.id, message.chat.id) in muted_list:
        try: 
            await message.delete()
            return
        except Exception as e: logging.warning(f"Could not delete muted message for owner {user_id}: {e}")
    

async def auto_seen_handler(client, message):
    user_id = client.me.id
    if AUTO_SEEN_STATUS.get(user_id, False):
        try: await client.read_chat_history(message.chat.id)
        except Exception as e: logging.warning(f"Could not mark history as read for chat {message.chat.id}: {e}")


# --- Command Controllers ---
async def help_controller(client, message):
    await message.edit_text(HELP_TEXT)

async def game_controller(client, message):
    command = message.text.strip()
    emoji = ""
    if command.startswith("تاس"):
        emoji = "🎲"
    elif command == "بولینگ":
        emoji = "🎳"
    
    if emoji:
        try:
            await message.delete()
            await client.send_dice(message.chat.id, emoji=emoji)
        except Exception as e:
            logging.error(f"Error sending game emoji for user {client.me.id}: {e}")

async def font_controller(client, message):
    user_id = client.me.id
    command = message.text.strip().split()

    if len(command) == 1:
        sample_time = "12:34"
        font_list_text = "🔢 **فونت ساعت خود را انتخاب کنید:**\n\n"
        for i, style_key in enumerate(FONT_KEYS_ORDER, 1):
            font_list_text += f"`{stylize_time(sample_time, style_key)}` **{FONT_DISPLAY_NAMES[style_key]}** ({i})\n"
        font_list_text += "\nبرای انتخاب، دستور `فونت [عدد]` را ارسال کنید."
        await message.edit_text(font_list_text)

    elif len(command) == 2 and command[1].isdigit():
        choice = int(command[1])
        if 1 <= choice <= len(FONT_KEYS_ORDER):
            selected_style = FONT_KEYS_ORDER[choice - 1]
            USER_FONT_CHOICES[user_id] = selected_style
            CLOCK_STATUS[user_id] = True 
            await message.edit_text(f"✅ فونت ساعت به **{FONT_DISPLAY_NAMES[selected_style]}** تغییر یافت.")
        else:
            await message.edit_text("⚠️ عدد وارد شده معتبر نیست.")

async def clock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "ساعت روشن":
        CLOCK_STATUS[user_id] = True
        await message.edit_text("✅ ساعت پروفایل فعال شد.")
    elif command == "ساعت خاموش":
        CLOCK_STATUS[user_id] = False
        try:
            me = await client.get_me()
            current_name = me.first_name
            base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()
            if base_name != current_name:
                await client.update_profile(first_name=base_name)
            await message.edit_text("❌ ساعت پروفایل غیرفعال و از نام شما حذف شد.")
        except Exception as e:
            await message.edit_text("❌ ساعت پروفایل غیرفعال شد (خطا در حذف از نام).")
            
async def enemy_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    if command == "دشمن خاموش" and not message.reply_to_message:
        if user_id in ACTIVE_ENEMIES:
            ACTIVE_ENEMIES[user_id].clear()
        if user_id in GLOBAL_ENEMY_STATUS:
            GLOBAL_ENEMY_STATUS[user_id] = False
        await message.edit_text("❌ **همه حالت‌های دشمن (فردی و همگانی) غیرفعال شدند.**")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user: return
    target_user, chat_id = message.reply_to_message.from_user, message.chat.id
    
    if user_id not in ACTIVE_ENEMIES: ACTIVE_ENEMIES[user_id] = set()
    
    if command == "دشمن روشن":
        ACTIVE_ENEMIES[user_id].add((target_user.id, chat_id))
        await message.edit_text(f"✅ **حالت دشمن برای {target_user.first_name} فعال شد.**")
    elif command == "دشمن خاموش":
        ACTIVE_ENEMIES[user_id].discard((target_user.id, chat_id))
        await message.edit_text(f"❌ **حالت دشمن برای {target_user.first_name} خاموش شد.**")

async def list_enemies_controller(client, message):
    user_id = client.me.id
    text = "⛓ **لیست دشمنان فعال:**\n\n"
    
    if GLOBAL_ENEMY_STATUS.get(user_id, False):
        text += "• **حالت دشمن همگانی فعال است.**\n"
    
    enemy_list = ACTIVE_ENEMIES.get(user_id, set())
    if not enemy_list:
        if not GLOBAL_ENEMY_STATUS.get(user_id, False):
            text += "هیچ دشمنی در لیست وجود ندارد."
        await message.edit_text(text)
        return

    text += "\n**دشمنان فردی:**\n"
    user_ids_to_fetch = {enemy[0] for enemy in enemy_list}
    
    try:
        users = await client.get_users(user_ids_to_fetch)
        user_map = {user.id: user for user in users}

        for target_id, chat_id in enemy_list:
            user = user_map.get(target_id)
            if user:
                text += f"- {user.mention} (`{user.id}`) \n"
            else:
                text += f"- کاربر حذف شده (`{target_id}`) \n"
    except Exception as e:
        logging.error(f"Error fetching users for enemy list: {e}")
        text += "خطا در دریافت اطلاعات کاربران."
        
    await message.edit_text(text)


async def block_unblock_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    target_user = message.reply_to_message.from_user
    command = message.text.strip()
    try:
        if command == "بلاک روشن": await client.block_user(target_user.id); await message.edit_text(f"🚫 کاربر **{target_user.first_name}** بلاک شد.")
        elif command == "بلاک خاموش": await client.unblock_user(target_user.id); await message.edit_text(f"✅ کاربر **{target_user.first_name}** آنبلاک شد.")
    except Exception as e: await message.edit_text(f"⚠️ **خطا:** {e}")

async def mute_unmute_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    user_id, target_user, chat_id = client.me.id, message.reply_to_message.from_user, message.chat.id
    target_tuple = (target_user.id, chat_id)
    if user_id not in MUTED_USERS: MUTED_USERS[user_id] = set()

    if message.text.strip() == "سکوت روشن":
        MUTED_USERS[user_id].add(target_tuple)
        await message.edit_text(f"🔇 کاربر **{target_user.first_name}** در این چت سایلنت شد.")
    elif message.text.strip() == "سکوت خاموش":
        MUTED_USERS[user_id].discard(target_tuple)
        await message.edit_text(f"🔊 کاربر **{target_user.first_name}** از سایلنت خارج شد.")

async def auto_reaction_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    user_id, target_user = client.me.id, message.reply_to_message.from_user
    command = message.text.strip()
    target_key = target_user.id
    if user_id not in AUTO_REACTION_TARGETS: AUTO_REACTION_TARGETS[user_id] = {}

    if command.startswith("ریاکشن") and command != "ریاکشن خاموش":
        parts = command.split()
        if len(parts) > 1:
            emoji = parts[-1]
            AUTO_REACTION_TARGETS[user_id][target_key] = emoji
            await message.edit_text(f"✅ واکنش خودکار با {emoji} برای **{target_user.first_name}** فعال شد.")
        else:
            await message.edit_text("⚠️ لطفا یک ایموجی مشخص کنید. مثال: `ریاکشن ❤️`")
    elif command == "ریاکشن خاموش":
        if AUTO_REACTION_TARGETS.get(user_id, {}).pop(target_key, None):
            await message.edit_text(f"❌ واکنش خودکار برای **{target_user.first_name}** غیرفعال شد.")

async def save_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        await message.delete()
        status_msg = await client.send_message(message.chat.id, "⏳ در حال ذخیره...")
        if message.reply_to_message.media:
            file_path = await client.download_media(message.reply_to_message)
            caption = "ذخیره شده با سلف بات"
            if message.reply_to_message.photo: await client.send_photo("me", file_path, caption=caption)
            elif message.reply_to_message.video: await client.send_video("me", file_path, caption=caption)
            else: await client.send_document("me", file_path, caption=caption)
            os.remove(file_path)
        else: await message.reply_to_message.copy("me")
        await status_msg.edit_text("✅ با موفقیت در Saved Messages ذخیره شد.")
        await asyncio.sleep(3)
        await status_msg.delete()
    except Exception as e: 
        await client.send_message(message.chat.id, f"⚠️ خطا در ذخیره: {e}")


async def repeat_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        count = int(message.text.split()[1])
        if count > 100:
            await message.edit_text("⚠️ حداکثر تکرار 100 است.")
            return
        await message.delete()
        for _ in range(count): await message.reply_to_message.copy(message.chat.id); await asyncio.sleep(0.1)
    except Exception: pass

async def delete_messages_controller(client, message):
    try:
        count = int(message.text.split()[1])
        if not (1 <= count <= 100):
            await message.edit_text("⚠️ تعداد باید بین 1 تا 100 باشد.")
            return
        
        message_ids = [message.id]
        async for msg in client.get_chat_history(message.chat.id, limit=count):
            if msg.from_user and msg.from_user.id == client.me.id:
                message_ids.append(msg.id)
        
        await client.delete_messages(message.chat.id, message_ids)
    except Exception as e:
        await message.edit_text(f"⚠️ خطا در حذف پیام: {e}")

async def pv_lock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "پیوی قفل":
        PV_LOCK_STATUS[user_id] = True
        await message.edit_text("قفل پیوی فعال شد ✅")
    elif command == "پیوی باز":
        PV_LOCK_STATUS[user_id] = False
        await message.edit_text("قفل پیوی غیرفعال شد ✅")

async def toggle_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    toggle_map = {
        "اینگیلیسی روشن": ("ترجمه انگلیسی", AUTO_TRANSLATE_TARGET, "en"),
        "اینگیلیسی خاموش": ("ترجمه انگلیسی", AUTO_TRANSLATE_TARGET, None),
        "روسی روشن": ("ترجمه روسی", AUTO_TRANSLATE_TARGET, "ru"),
        "روسی خاموش": ("ترجمه روسی", AUTO_TRANSLATE_TARGET, None),
        "چینی روشن": ("ترجمه چینی", AUTO_TRANSLATE_TARGET, "zh-CN"),
        "چینی خاموش": ("ترجمه چینی", AUTO_TRANSLATE_TARGET, None),
        "بولد روشن": ("بولد خودکار", BOLD_MODE_STATUS, True),
        "بولد خاموش": ("بولد خودکار", BOLD_MODE_STATUS, False),
        "سین روشن": ("سین خودکار", AUTO_SEEN_STATUS, True),
        "سین خاموش": ("سین خودکار", AUTO_SEEN_STATUS, False),
        "منشی روشن": ("منشی", SECRETARY_MODE_STATUS, True),
        "منشی خاموش": ("منشی", SECRETARY_MODE_STATUS, False),
        "انتی لوگین روشن": ("ضد لاگین", ANTI_LOGIN_STATUS, True),
        "انتی لوگین خاموش": ("ضد لاگین", ANTI_LOGIN_STATUS, False),
        "دشمن همگانی روشن": ("دشمن همگانی", GLOBAL_ENEMY_STATUS, True),
        "دشمن همگانی خاموش": ("دشمن همگانی", GLOBAL_ENEMY_STATUS, False),
        "تایپ روشن": ("تایپ خودکار", TYPING_MODE_STATUS, True),
        "تایپ خاموش": ("تایپ خودکار", TYPING_MODE_STATUS, False),
        "بازی روشن": ("بازی خودکار", PLAYING_MODE_STATUS, True),
        "بازی خاموش": ("بازی خودکار", PLAYING_MODE_STATUS, False),
    }

    if command in toggle_map:
        feature_name, status_dict, new_status = toggle_map[command]

        if command == "تایپ روشن":
            PLAYING_MODE_STATUS[user_id] = False
        elif command == "بازی روشن":
            TYPING_MODE_STATUS[user_id] = False
        
        if status_dict is AUTO_TRANSLATE_TARGET:
            lang_code_map = {"اینگیلیسی خاموش": "en", "روسی خاموش": "ru", "چینی خاموش": "zh-CN"}
            lang_to_turn_off = lang_code_map.get(command)
            if new_status:
                AUTO_TRANSLATE_TARGET[user_id] = new_status
            elif AUTO_TRANSLATE_TARGET.get(user_id) == lang_to_turn_off:
                AUTO_TRANSLATE_TARGET[user_id] = None
        else:
            status_dict[user_id] = new_status

        if command == "منشی روشن": USERS_REPLIED_IN_SECRETARY[user_id] = set()
        
        status_text = "فعال" if new_status or (status_dict is AUTO_TRANSLATE_TARGET and AUTO_TRANSLATE_TARGET.get(user_id)) else "غیرفعال"
        await message.edit_text(f"✅ **{feature_name} {status_text} شد.**")

async def copy_profile_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    chat_id = message.chat.id
    original_message_id = message.id

    if command == "کپی روشن":
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.edit_text("⚠️ برای کپی کردن، باید روی پیام شخص مورد نظر ریپلای کنید.")
            return

        await client.delete_messages(chat_id, original_message_id)
        status_msg = await client.send_message(chat_id, "⏳ در حال ذخیره پروفایل اصلی...")
        
        me = await client.get_me()
        me_chat = await client.get_chat("me")
        
        original_photo_paths = []
        async for photo in client.get_chat_photos("me"):
            path = await client.download_media(photo.file_id, file_name=f"original_{user_id}_{photo.file_id}.jpg")
            original_photo_paths.append(path)

        ORIGINAL_PROFILE_DATA[user_id] = {
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "bio": me_chat.bio or "",
            "photo_paths": original_photo_paths,
        }
        
        await status_msg.edit_text("⏳ در حال کپی کردن پروفایل هدف...")
        target_user = message.reply_to_message.from_user
        target_chat = await client.get_chat(target_user.id)
        
        target_photo_paths = []
        async for photo in client.get_chat_photos(target_user.id):
            target_photo_paths.append(await client.download_media(photo.file_id))
            
        current_photo_ids = [p.file_id async for p in client.get_chat_photos("me")]
        if current_photo_ids:
            await client.delete_profile_photos(current_photo_ids)
            
        for path in reversed(target_photo_paths):
            await client.set_profile_photo(photo=path)
            os.remove(path)
            
        await client.update_profile(first_name=target_user.first_name or "", last_name=target_user.last_name or "", bio=target_chat.bio or "")
        
        COPY_MODE_STATUS[user_id] = True
        await status_msg.edit_text(f"✅ پروفایل **{target_user.first_name}** با موفقیت کپی شد.")
        await asyncio.sleep(3)
        await status_msg.delete()

    elif command == "کپی خاموش":
        if user_id not in ORIGINAL_PROFILE_DATA:
            await message.edit_text("⚠️ پروفایلی برای بازگردانی یافت نشد.")
            return

        await client.delete_messages(chat_id, original_message_id)
        status_msg = await client.send_message(chat_id, "⏳ در حال بازگردانی پروفایل اصلی...")
        original_data = ORIGINAL_PROFILE_DATA[user_id]
        
        current_photo_ids = [p.file_id async for p in client.get_chat_photos("me")]
        if current_photo_ids:
            await client.delete_profile_photos(current_photo_ids)
            
        for path in reversed(original_data["photo_paths"]):
            if os.path.exists(path):
                await client.set_profile_photo(photo=path)
                os.remove(path)
            
        restored_name = original_data["first_name"]
        await client.update_profile(first_name=restored_name, last_name=original_data["last_name"], bio=original_data["bio"])
        
        COPY_MODE_STATUS.pop(user_id, None)
        
        if CLOCK_STATUS.get(user_id, True):
            asyncio.create_task(update_profile_clock(client, user_id))
        
        ORIGINAL_PROFILE_DATA.pop(user_id, None)
        await status_msg.edit_text("✅ پروفایل اصلی با موفقیت بازگردانی شد.")
        await asyncio.sleep(3)
        await status_msg.delete()

# --- Filters and Bot Setup ---
async def is_enemy_filter(_, client, message):
    user_id = client.me.id
    if GLOBAL_ENEMY_STATUS.get(user_id, False):
        return True
    return message.from_user and (message.from_user.id, message.chat.id) in ACTIVE_ENEMIES.get(user_id, set())

is_enemy = filters.create(is_enemy_filter)

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    try:
        await client.start()
        user_id = (await client.get_me()).id
    except (UserDeactivated, AuthKeyUnregistered) as e:
        logging.error(f"Session for phone {phone} is invalid ({type(e).__name__}). Removing from database.")
        if sessions_collection is not None:
            sessions_collection.delete_one({'phone_number': phone})
        return

    try:
        if user_id in ACTIVE_BOTS:
            for task in ACTIVE_BOTS[user_id][1]:
                if task: task.cancel()
            ACTIVE_BOTS.pop(user_id, None)
            await asyncio.sleep(1)
        
        # Initialize settings
        USER_FONT_CHOICES[user_id] = font_style
        CLOCK_STATUS[user_id] = not disable_clock
        
        # Handlers Registration
        client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=-5)
        client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
        client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
        client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
        
        client.add_handler(MessageHandler(help_controller, filters.text & filters.me & filters.regex("^راهنما$")))
        client.add_handler(MessageHandler(toggle_controller, filters.text & filters.me & filters.regex("^(اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|بولد روشن|بولد خاموش|سین روشن|سین خاموش|منشی روشن|منشی خاموش|انتی لوگین روشن|انتی لوگین خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش)$")))
        client.add_handler(MessageHandler(pv_lock_controller, filters.text & filters.me & filters.regex("^(پیوی قفل|پیوی باز)$")))
        client.add_handler(MessageHandler(font_controller, filters.text & filters.me & filters.regex(r"^(فونت|فونت \d+)$")))
        client.add_handler(MessageHandler(clock_controller, filters.text & filters.me & filters.regex("^(ساعت روشن|ساعت خاموش)$")))
        client.add_handler(MessageHandler(enemy_controller, filters.text & filters.me & filters.regex("^(دشمن روشن|دشمن خاموش)$")))
        client.add_handler(MessageHandler(list_enemies_controller, filters.text & filters.me & filters.regex("^لیست دشمن$")))
        client.add_handler(MessageHandler(block_unblock_controller, filters.text & filters.reply & filters.me & filters.regex("^(بلاک روشن|بلاک خاموش)$")))
        client.add_handler(MessageHandler(mute_unmute_controller, filters.text & filters.reply & filters.me & filters.regex("^(سکوت روشن|سکوت خاموش)$")))
        client.add_handler(MessageHandler(auto_reaction_controller, filters.text & filters.reply & filters.me & filters.regex("^(ریاکشن .*|ریاکشن خاموش)$")))
        client.add_handler(MessageHandler(copy_profile_controller, filters.text & filters.me & filters.regex("^(کپی روشن|کپی خاموش)$")))
        client.add_handler(MessageHandler(save_message_controller, filters.text & filters.reply & filters.me & filters.regex("^ذخیره$")))
        client.add_handler(MessageHandler(repeat_message_controller, filters.text & filters.reply & filters.me & filters.regex(r"^تکرار \d+$")))
        client.add_handler(MessageHandler(delete_messages_controller, filters.text & filters.me & filters.regex(r"^حذف \d+$")))
        client.add_handler(MessageHandler(game_controller, filters.text & filters.me & filters.regex(r"^(تاس|تاس \d+|بولینگ)$")))
        
        client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me), group=1)
        client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.service), group=1)

        tasks = [
            asyncio.create_task(update_profile_clock(client, user_id)),
            asyncio.create_task(anti_login_task(client, user_id)),
            asyncio.create_task(status_action_task(client, user_id))
        ]
        ACTIVE_BOTS[user_id] = (client, tasks)
        logging.info(f"Successfully started bot instance for user_id {user_id}.")
    except Exception as e:
        logging.error(f"FAILED to start bot instance for {phone}: {e}", exc_info=True)

# --- Web Section (Flask) ---
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سلف بات تلگرام</title><style>@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');body{font-family:'Vazirmatn',sans-serif;background-color:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:20px;box-sizing:border-box;}.container{background:white;padding:30px 40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);text-align:center;width:100%;max-width:480px;}h1{color:#333;margin-bottom:20px;font-size:1.5em;}p{color:#666;line-height:1.6;}form{display:flex;flex-direction:column;gap:15px;margin-top:20px;}input[type="tel"],input[type="text"],input[type="password"]{padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;text-align:left;direction:ltr;}button{padding:12px;background-color:#007bff;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;transition:background-color .2s;}.error{color:#d93025;margin-top:15px;font-weight:bold;}label{font-weight:bold;color:#555;display:block;margin-bottom:5px;text-align:right;}.font-options{border:1px solid #ddd;border-radius:8px;overflow:hidden;}.font-option{display:flex;align-items:center;padding:12px;border-bottom:1px solid #ddd;cursor:pointer;}.font-option:last-child{border-bottom:none;}.font-option input[type="radio"]{margin-left:15px;}.font-option label{display:flex;justify-content:space-between;align-items:center;width:100%;font-weight:normal;cursor:pointer;}.font-option .preview{font-size:1.3em;font-weight:bold;direction:ltr;color:#0056b3;}.success{color:#1e8e3e;}.checkbox-option{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:10px;padding:8px;background-color:#f8f9fa;border-radius:8px;}.checkbox-option label{margin-bottom:0;font-weight:normal;cursor:pointer;color:#444;}</style></head><body><div class="container">
{% if step == 'GET_PHONE' %}<h1>ورود به سلف بات</h1><p>شماره و تنظیمات خود را انتخاب کنید تا ربات فعال شود.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="phone"><div><label for="phone">شماره تلفن (با کد کشور)</label><input type="tel" id="phone" name="phone_number" placeholder="+989123456789" required autofocus></div><div><label>استایل فونت ساعت</label><div class="font-options">{% for name, data in font_previews.items() %}<div class="font-option" onclick="document.getElementById('font-{{ data.style }}').checked = true;"><input type="radio" name="font_style" value="{{ data.style }}" id="font-{{ data.style }}" {% if loop.first %}checked{% endif %}><label for="font-{{ data.style }}"><span>{{ name }}</span><span class="preview">{{ data.preview }}</span></label></div>{% endfor %}</div></div><div class="checkbox-option"><input type="checkbox" id="disable_clock" name="disable_clock"><label for="disable_clock">فعال‌سازی بدون ساعت</label></div><button type="submit">ارسال کد تایید</button></form>
{% elif step == 'GET_CODE' %}<h1>کد تایید</h1><p>کدی به تلگرام شما با شماره <strong>{{ phone_number }}</strong> ارسال شد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="code"><input type="text" name="code" placeholder="کد تایید" required><button type="submit">تایید کد</button></form>
{% elif step == 'GET_PASSWORD' %}<h1>رمز دو مرحله‌ای</h1><p>حساب شما نیاز به رمز تایید دو مرحله‌ای دارد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="password"><input type="password" name="password" placeholder="رمز عبور دو مرحله ای" required><button type="submit">ورود</button></form>
{% elif step == 'SHOW_SUCCESS' %}<h1>✅ ربات فعال شد!</h1><p>ربات با موفقیت فعال شد. برای دسترسی به قابلیت‌ها، در تلگرام پیام `راهنما` را ارسال کنید.</p><form action="{{ url_for('home') }}" method="get" style="margin-top: 20px;"><button type="submit">خروج و ورود مجدد</button></form>{% endif %}</div></body></html>
"""

def get_font_previews():
    sample_time = "12:34"
    return {FONT_DISPLAY_NAMES[key]: {"style": key, "preview": stylize_time(sample_time, key)} for key in FONT_KEYS_ORDER}

async def cleanup_client(phone):
    if client := ACTIVE_CLIENTS.pop(phone, None):
        if client.is_connected: await client.disconnect()

@app_flask.route('/')
def home():
    session.clear()
    return render_template_string(HTML_TEMPLATE, step='GET_PHONE', font_previews=get_font_previews())

@app_flask.route('/login', methods=['POST'])
def login():
    action = request.form.get('action')
    phone = session.get('phone_number')
    try:
        if not EVENT_LOOP.is_running():
            raise RuntimeError("Event loop is not running.")
            
        if action == 'phone':
            session['phone_number'] = request.form.get('phone_number')
            session['font_style'] = request.form.get('font_style')
            session['disable_clock'] = 'on' == request.form.get('disable_clock')
            future = asyncio.run_coroutine_threadsafe(send_code_task(session['phone_number']), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='GET_CODE', phone_number=session['phone_number'])
        elif action == 'code':
            future = asyncio.run_coroutine_threadsafe(sign_in_task(phone, request.form.get('code')), EVENT_LOOP)
            next_step = future.result(45)
            if next_step == 'GET_PASSWORD':
                return render_template_string(HTML_TEMPLATE, step='GET_PASSWORD', phone_number=phone)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
        elif action == 'password':
            future = asyncio.run_coroutine_threadsafe(check_password_task(phone, request.form.get('password')), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
    except Exception as e:
        if phone: 
            try:
                if EVENT_LOOP.is_running():
                    asyncio.run_coroutine_threadsafe(cleanup_client(phone), EVENT_LOOP)
            except RuntimeError:
                pass # Loop is already closed
        logging.error(f"Error during '{action}': {e}", exc_info=True)
        error_map = {
            (PhoneCodeInvalid, PasswordHashInvalid): "کد یا رمز وارد شده اشتباه است.",
            (PhoneNumberInvalid, TypeError): "شماره تلفن نامعتبر است.",
            PhoneCodeExpired: "کد تایید منقضی شده، دوباره تلاش کنید.",
            FloodWait: f"محدودیت تلگرام. لطفا {getattr(e, 'value', 5)} ثانیه دیگر تلاش کنید."
        }
        error_msg = "خطای پیش‌بینی نشده: " + str(e)
        current_step = 'GET_PHONE'
        for err_types, msg in error_map.items():
            if isinstance(e, err_types):
                error_msg = msg
                current_step = 'GET_CODE' if isinstance(e, PhoneCodeInvalid) else 'GET_PASSWORD'
                if isinstance(e, (PhoneNumberInvalid, TypeError, PhoneCodeExpired)): current_step = 'GET_PHONE'
                break
        if current_step == 'GET_PHONE': session.clear()
        return render_template_string(HTML_TEMPLATE, step=current_step, error_message=error_msg, phone_number=phone, font_previews=get_font_previews())
    return redirect(url_for('home'))

async def send_code_task(phone):
    await cleanup_client(phone)
    client = Client(f"user_{phone}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    ACTIVE_CLIENTS[phone] = client
    await client.connect()
    session['phone_code_hash'] = (await client.send_code(phone)).phone_code_hash

async def sign_in_task(phone, code):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.sign_in(phone, session['phone_code_hash'], code)
        session_str = await client.export_session_string()
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )
            
        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
        await cleanup_client(phone)
    except SessionPasswordNeeded:
        return 'GET_PASSWORD'

async def check_password_task(phone, password):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.check_password(password)
        session_str = await client.export_session_string()

        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )

        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
    finally:
        await cleanup_client(phone)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

def run_asyncio_loop():
    global EVENT_LOOP
    asyncio.set_event_loop(EVENT_LOOP)
    
    if sessions_collection is not None:
        logging.info("Found MongoDB collection, attempting to auto-login from database...")
        for doc in sessions_collection.find():
            try:
                session_string = doc['session_string']
                phone = doc.get('phone_number', f"db_session_{doc['_id']}")
                font_style = doc.get('font_style', 'stylized')
                disable_clock = doc.get('disable_clock', False)
                logging.info(f"Auto-starting session for {phone}...")
                EVENT_LOOP.create_task(start_bot_instance(session_string, phone, font_style, disable_clock))
            except Exception as e:
                logging.error(f"Failed to auto-start session for {doc.get('phone_number')}: {e}")

    try:
        EVENT_LOOP.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Event loop stopped by user.")
    finally:
        logging.info("Closing event loop.")
        if EVENT_LOOP.is_running():
            tasks = asyncio.all_tasks(loop=EVENT_LOOP)
            for task in tasks:
                task.cancel()
            
            async def gather_tasks():
                await asyncio.gather(*tasks, return_exceptions=True)

            # Run the gathering task to ensure cancellations are processed
            EVENT_LOOP.run_until_complete(gather_tasks())
            EVENT_LOOP.close()


if __name__ == "__main__":
    logging.info("Starting Telegram Self Bot Service...")
    loop_thread = Thread(target=run_asyncio_loop, daemon=True)
    loop_thread.start()
    run_flask()

import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid
)
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, render_template_string, redirect, session, url_for
from threading import Thread
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# ⚠️ Main Settings (Enter your API_ID and API_HASH here)
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://CFNBEFBGWFB:hdhbedfefbegh@cluster0.obohcl3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = None
sessions_collection = None
if MONGO_URI and "<db_password>" not in MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        logging.info("Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
else:
    logging.warning("MONGO_URI is not configured correctly. Please set your password. Session persistence will be disabled.")


# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Clock Font Dictionaries ---
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'７','8':'８','9':'９',':':'：'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth"]
FONT_DISPLAY_NAMES = {
    "cursive": "کشیده", "stylized": "فانتزی", "doublestruck": "توخالی",
    "monospace": "کامپیوتری", "normal": "ساده", "circled": "دایره‌ای", "fullwidth": "پهن"
}
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"


# --- Feature Variables ---
ENEMY_REPLIES = [
    "کیرم تو رحم اجاره ای و خونی مالی مادرت", "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام و اب کوسشو بریزم کف خونه تا فردا صبح کارگرای افغانی برای نظافت اومدن با بوی اب کس مادرت بجقن و ابکیراشون نثار قبر مرده هات بشه", "احمق مادر کونی من کس مادرت گذاشتم تو بازم داری کسشر میگی", "هی بیناموس کیرم بره تو کس ننت واس بابات نشآخ مادر کیری کیرم بره تو کس اجدادت کسکش بیناموس کس ول نسل شوتی ابجی کسده کیرم تو کس مادرت بیناموس کیری کیرم تو کس نسلت ابجی کونی کس نسل سگ ممبر کونی ابجی سگ ممبر سگ کونی کیرم تو کس ننت کیر تو کس مادرت کیر خاندان  تو کس نسلت مادر کونی ابجی کونی کیری ناموس ابجیتو گاییدم سگ حرومی خارکسه مادر کیری با کیر بزنم تو رحم مادرت ناموستو بگام لاشی کونی ابجی کس  خیابونی مادرخونی ننت کیرمو میماله تو میای کص میگی شاخ نشو ییا ببین شاخو کردم تو کون ابجی جندت کس ابجیتو پاره کردم تو شاخ میشی اوبی",
    "کیرم تو کس سیاه مادرت خارکصده", "حروم زاده باک کص ننت با ابکیرم پر میکنم", "منبع اب ایرانو با اب کص مادرت تامین میکنم", "خارکسته میخای مادرتو بگام بعد بیای ادعای شرف کنی کیرم تو شرف مادرت",
    "کیرم تویه اون خرخره مادرت بیا اینحا ببینم تویه نوچه کی دانلود شدی کیفیتت پایینه صدات نمیاد فقط رویه حالیت بی صدا داری امواج های بی ارزش و بیناموسانه از خودت ارسال میکنی که ناگهان دیدی من روانی شدم دست از پا خطا کردم با تبر کائنات کوبیدم رو سر مادرت نمیتونی مارو تازه بالقه گمان کنی", "کیرم تویه اون خرخره مادرت بیا اینحا ببینم تویه نوچه کی دانلود شدی کیفیتت پایینه صدات نمیاد فقط رویه حالیت بی صدا داری امواج های بی ارزش و بیناموسانه از خودت ارسال میکنی که ناگهان دیدی من روانی شدم دست از پا خطا کردم با تبر کائنات کوبیدم رو سر مادرت نمیتونی مارو تازه بالقه گمان کنی",
]
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."
HELP_TEXT = """
** راهنمای کامل دستورات سلف بات **

---
** وضعیت و قالب‌بندی **
 • `تایپ روشن` / `خاموش`: فعال‌سازی حالت "در حال تایپ" در همه چت‌ها.
 • `بازی روشن` / `خاموش`: فعال‌سازی حالت "در حال بازی" در همه چت‌ها.
 • `اینگیلیسی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به انگلیسی.
 • `روسی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به روسی.
 • `چینی روشن` / `خاموش`: ترجمه خودکار پیام‌ها به چینی.
 • `بولد روشن` / `خاموش`: برجسته کردن خودکار تمام پیام‌ها.
 • `سین روشن` / `خاموش`: سین خودکار پیام‌ها در چت شخصی (PV).

---
** ساعت و فونت **
 • `ساعت روشن` / `خاموش`: نمایش یا حذف ساعت از نام پروفایل.
 • `فونت`: نمایش لیست فونت‌های ساعت.
 • `فونت [عدد]`: انتخاب فونت جدید برای ساعت.

---
** مدیریت پیام و کاربر **
 • `حذف [عدد]`: (مثال: `حذف 10`) حذف X پیام آخر شما در چت فعلی.
 • `ذخیره` (با ریپلای): ذخیره کردن پیام مورد نظر در Saved Messages.
 • `تکرار [عدد]` (با ریپلای): تکرار پیام تا سقف 100 بار.
 • `دشمن روشن` / `خاموش` (با ریپلای): فعال/غیرفعال کردن حالت دشمن برای کاربر.
 • `دشمن همگانی روشن` / `خاموش`: فعال/غیرفعال کردن حالت دشمن برای همه.
 • `لیست دشمن`: نمایش لیست تمام دشمنان فعال.
 • `بلاک روشن` / `خاموش` (با ریپلای): بلاک یا آنبلاک کردن کاربر.
 • `سکوت روشن` / `خاموش` (با ریپلای): حذف خودکار پیام‌های کاربر در چت فعلی.
 • `ریاکشن [ایموجی]` (با ریپلای): واکنش خودکار به پیام‌های کاربر با ایموجی دلخواه.
 • `ریاکشن خاموش` (با ریپلای): غیرفعال‌سازی واکنش خودکار برای کاربر.

---
** سرگرمی **
 • `تاس`: ارسال تاس شانسی. (نتیجه تاس شانسی است)
 • `بولینگ`: ارسال بولینگ شانسی.

---
** امنیت و منشی **
 • `پیوی قفل` / `باز`: تمام پیام‌های دریافتی در پیوی را به صورت خودکار حذف می‌کند.
 • `منشی روشن` / `خاموش`: فعال‌سازی پاسخ خودکار در PV.
 • `انتی لوگین روشن` / `خاموش`: خروج خودکار نشست‌های جدید از حساب شما.
 • `کپی روشن` (با ریپلای): کپی کردن پروفایل کاربر مورد نظر.
 • `کپی خاموش`: بازگرداندن پروفایل اصلی شما.
"""
COMMAND_REGEX = r"^(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز)$"


# --- User Status Management (based on User ID) ---
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
SECRETARY_MODE_STATUS = {}
USERS_REPLIED_IN_SECRETARY = {}
MUTED_USERS = {}
USER_FONT_CHOICES = {}
CLOCK_STATUS = {}
BOLD_MODE_STATUS = {}
AUTO_SEEN_STATUS = {}
AUTO_REACTION_TARGETS = {}
AUTO_TRANSLATE_TARGET = {}
ANTI_LOGIN_STATUS = {}
COPY_MODE_STATUS = {}
ORIGINAL_PROFILE_DATA = {}
GLOBAL_ENEMY_STATUS = {}
TYPING_MODE_STATUS = {}
PLAYING_MODE_STATUS = {}
PV_LOCK_STATUS = {}


EVENT_LOOP = asyncio.new_event_loop()
ACTIVE_CLIENTS = {}
ACTIVE_BOTS = {}

# --- Main Bot Functions ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def update_profile_clock(client: Client, user_id: int):
    log_message = f"Starting clock loop for user_id {user_id}..."
    logging.info(log_message)
    
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
                me = await client.get_me()
                current_name = me.first_name
                
                base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()

                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                current_time_str = tehran_time.strftime("%H:%M")
                stylized_time = stylize_time(current_time_str, current_font_style)
                new_name = f"{base_name} {stylized_time}"
                
                if new_name != current_name:
                    await client.update_profile(first_name=new_name)
            
            now = datetime.now(TEHRAN_TIMEZONE)
            sleep_duration = 60 - now.second + 0.1
            await asyncio.sleep(sleep_duration)
        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Clock Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except FloodWait as e:
            logging.warning(f"Clock Task: Flood wait of {e.value}s for user_id {user_id}.")
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            logging.error(f"An error in clock task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)
    
    logging.info(f"Clock task for user_id {user_id} has stopped.")


async def anti_login_task(client: Client, user_id: int):
    logging.info(f"Starting anti-login task for user_id {user_id}...")
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False):
                auths = await client.invoke(functions.account.GetAuthorizations())
                
                current_hash = None
                for auth in auths.authorizations:
                    if auth.current:
                        current_hash = auth.hash
                        break
                
                if current_hash:
                    for auth in auths.authorizations:
                        if auth.hash != current_hash:
                            await client.invoke(functions.account.ResetAuthorization(hash=auth.hash))
                            logging.info(f"Terminated a new session for user {user_id} with hash {auth.hash}")
                            device_info = f"{auth.app_name} on {auth.device_model} ({auth.platform}, {auth.system_version})"
                            location_info = f"from IP {auth.ip} in {auth.country}"
                            message_text = (
                                f"🚨 **هشدار امنیتی: نشست جدید خاتمه داده شد** 🚨\n\n"
                                f"یک دستگاه جدید تلاش کرد وارد حساب شما شود و دسترسی آن به صورت خودکار قطع شد.\n\n"
                                f"**جزئیات نشست:**\n"
                                f"- **دستگاه:** {device_info}\n"
                                f"- **مکان:** {location_info}\n"
                                f"- **زمان ورود:** {auth.date_created.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            await client.send_message("me", message_text)
            await asyncio.sleep(60) # Check every minute
        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Anti-Login Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except Exception as e:
            logging.error(f"An error in anti-login task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(120)

    logging.info(f"Anti-login task for user_id {user_id} has stopped.")


async def status_action_task(client: Client, user_id: int):
    logging.info(f"Starting status action task for user_id {user_id}...")
    chat_ids = []
    last_dialog_fetch = 0

    while user_id in ACTIVE_BOTS:
        try:
            typing_mode = TYPING_MODE_STATUS.get(user_id, False)
            playing_mode = PLAYING_MODE_STATUS.get(user_id, False)

            if not typing_mode and not playing_mode:
                await asyncio.sleep(2) # Sleep and check again if nothing is active
                continue

            action_to_send = ChatAction.TYPING if typing_mode else ChatAction.PLAYING

            # Refresh the dialog list every 5 minutes (300 seconds)
            now = asyncio.get_event_loop().time()
            if not chat_ids or (now - last_dialog_fetch > 300):
                logging.info(f"Refreshing dialog list for user_id {user_id}...")
                new_chat_ids = []
                async for dialog in client.get_dialogs(limit=50): # Increased limit
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chat_ids.append(dialog.chat.id)
                chat_ids = new_chat_ids
                last_dialog_fetch = now
                logging.info(f"Found {len(chat_ids)} chats to update.")

            if not chat_ids:
                logging.warning(f"No suitable chats found for user_id {user_id}.")
                await asyncio.sleep(30) # Wait a bit before trying to fetch dialogs again
                continue

            # Send action to all chats in the cached list
            for chat_id in chat_ids:
                try:
                    await client.send_chat_action(chat_id, action_to_send)
                except FloodWait as e:
                    logging.warning(f"Flood wait in status_action_task. Sleeping for {e.value}s.")
                    await asyncio.sleep(e.value)
                except Exception:
                    # Ignore errors for single chats (e.g., kicked from group)
                    pass
            
            # The action lasts for ~5 seconds, so we sleep for 4 to refresh it just before it expires.
            await asyncio.sleep(4)

        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Status Action Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except Exception as e:
            logging.error(f"An error in status action task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)
            
    logging.info(f"Status action task for user_id {user_id} has stopped.")


# --- Feature Handlers ---
async def translate_text(text: str, target_lang: str) -> str:
    if not text: return ""
    encoded_text = quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0][0][0]
    except Exception as e:
        logging.error(f"Translation failed: {e}")
    return text

async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    if not message.text or re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE):
        return
        
    original_text = message.text
    modified_text = original_text
    
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang:
        modified_text = await translate_text(modified_text, target_lang)
    
    if BOLD_MODE_STATUS.get(user_id, False):
        if not modified_text.startswith(('`', '**', '__', '~~', '||')):
            modified_text = f"**{modified_text}**"
            
    if modified_text != original_text:
        try:
            await message.edit_text(modified_text)
        except Exception as e:
            logging.warning(f"Could not modify outgoing message for user {user_id}: {e}")
    

async def enemy_handler(client, message):
    user_id = client.me.id
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        shuffled_replies = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
        ENEMY_REPLY_QUEUES[user_id] = shuffled_replies
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try:
        await message.reply_text(reply_text)
    except Exception as e:
        logging.warning(f"Could not reply to enemy for user_id {user_id}: {e}")


async def secretary_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if message.from_user:
        target_user_id = message.from_user.id
        if SECRETARY_MODE_STATUS.get(owner_user_id, False):
            replied_users = USERS_REPLIED_IN_SECRETARY.get(owner_user_id, set())
            if target_user_id in replied_users:
                return
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied_users.add(target_user_id)
                USERS_REPLIED_IN_SECRETARY[owner_user_id] = replied_users
            except Exception as e:
                logging.warning(f"Could not auto-reply for user_id {owner_user_id}: {e}")

async def pv_lock_handler(client, message):
    owner_user_id = client.me.id
    if PV_LOCK_STATUS.get(owner_user_id, False):
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Could not perform PV lock action for user {owner_user_id}: {e}")

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    
    reaction_map = AUTO_REACTION_TARGETS.get(user_id, {})
    target_key = message.from_user.id # Simplified key
    
    if emoji := reaction_map.get(target_key):
        try:
            await client.send_reaction(message.chat.id, message.id, emoji)
        except ReactionInvalid:
            await message.reply_text(f"⚠️ **خطا:** ایموجی `{emoji}` برای واکنش معتبر نیست.")
            if target_key in reaction_map: AUTO_REACTION_TARGETS[user_id].pop(target_key, None)
        except Exception as e:
            logging.error(f"Reaction error for user {user_id}: {e}", exc_info=True)

    muted_list = MUTED_USERS.get(user_id, set())
    if (message.from_user.id, message.chat.id) in muted_list:
        try: 
            await message.delete()
            return
        except Exception as e: logging.warning(f"Could not delete muted message for owner {user_id}: {e}")
    

async def auto_seen_handler(client, message):
    user_id = client.me.id
    if AUTO_SEEN_STATUS.get(user_id, False):
        try: await client.read_chat_history(message.chat.id)
        except Exception as e: logging.warning(f"Could not mark history as read for chat {message.chat.id}: {e}")


# --- Command Controllers ---
async def help_controller(client, message):
    await message.edit_text(HELP_TEXT)

async def game_controller(client, message):
    command = message.text.strip()
    emoji = ""
    if command.startswith("تاس"):
        emoji = "🎲"
    elif command == "بولینگ":
        emoji = "🎳"
    
    if emoji:
        try:
            await message.delete()
            await client.send_dice(message.chat.id, emoji=emoji)
        except Exception as e:
            logging.error(f"Error sending game emoji for user {client.me.id}: {e}")

async def font_controller(client, message):
    user_id = client.me.id
    command = message.text.strip().split()

    if len(command) == 1:
        sample_time = "12:34"
        font_list_text = "🔢 **فونت ساعت خود را انتخاب کنید:**\n\n"
        for i, style_key in enumerate(FONT_KEYS_ORDER, 1):
            font_list_text += f"`{stylize_time(sample_time, style_key)}` **{FONT_DISPLAY_NAMES[style_key]}** ({i})\n"
        font_list_text += "\nبرای انتخاب، دستور `فونت [عدد]` را ارسال کنید."
        await message.edit_text(font_list_text)

    elif len(command) == 2 and command[1].isdigit():
        choice = int(command[1])
        if 1 <= choice <= len(FONT_KEYS_ORDER):
            selected_style = FONT_KEYS_ORDER[choice - 1]
            USER_FONT_CHOICES[user_id] = selected_style
            CLOCK_STATUS[user_id] = True 
            await message.edit_text(f"✅ فونت ساعت به **{FONT_DISPLAY_NAMES[selected_style]}** تغییر یافت.")
        else:
            await message.edit_text("⚠️ عدد وارد شده معتبر نیست.")

async def clock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "ساعت روشن":
        CLOCK_STATUS[user_id] = True
        await message.edit_text("✅ ساعت پروفایل فعال شد.")
    elif command == "ساعت خاموش":
        CLOCK_STATUS[user_id] = False
        try:
            me = await client.get_me()
            current_name = me.first_name
            base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()
            if base_name != current_name:
                await client.update_profile(first_name=base_name)
            await message.edit_text("❌ ساعت پروفایل غیرفعال و از نام شما حذف شد.")
        except Exception as e:
            await message.edit_text("❌ ساعت پروفایل غیرفعال شد (خطا در حذف از نام).")
            
async def enemy_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    if command == "دشمن خاموش" and not message.reply_to_message:
        if user_id in ACTIVE_ENEMIES:
            ACTIVE_ENEMIES[user_id].clear()
        if user_id in GLOBAL_ENEMY_STATUS:
            GLOBAL_ENEMY_STATUS[user_id] = False
        await message.edit_text("❌ **همه حالت‌های دشمن (فردی و همگانی) غیرفعال شدند.**")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user: return
    target_user, chat_id = message.reply_to_message.from_user, message.chat.id
    
    if user_id not in ACTIVE_ENEMIES: ACTIVE_ENEMIES[user_id] = set()
    
    if command == "دشمن روشن":
        ACTIVE_ENEMIES[user_id].add((target_user.id, chat_id))
        await message.edit_text(f"✅ **حالت دشمن برای {target_user.first_name} فعال شد.**")
    elif command == "دشمن خاموش":
        ACTIVE_ENEMIES[user_id].discard((target_user.id, chat_id))
        await message.edit_text(f"❌ **حالت دشمن برای {target_user.first_name} خاموش شد.**")

async def list_enemies_controller(client, message):
    user_id = client.me.id
    text = "⛓ **لیست دشمنان فعال:**\n\n"
    
    if GLOBAL_ENEMY_STATUS.get(user_id, False):
        text += "• **حالت دشمن همگانی فعال است.**\n"
    
    enemy_list = ACTIVE_ENEMIES.get(user_id, set())
    if not enemy_list:
        if not GLOBAL_ENEMY_STATUS.get(user_id, False):
            text += "هیچ دشمنی در لیست وجود ندارد."
        await message.edit_text(text)
        return

    text += "\n**دشمنان فردی:**\n"
    user_ids_to_fetch = {enemy[0] for enemy in enemy_list}
    
    try:
        users = await client.get_users(user_ids_to_fetch)
        user_map = {user.id: user for user in users}

        for target_id, chat_id in enemy_list:
            user = user_map.get(target_id)
            if user:
                text += f"- {user.mention} (`{user.id}`) \n"
            else:
                text += f"- کاربر حذف شده (`{target_id}`) \n"
    except Exception as e:
        logging.error(f"Error fetching users for enemy list: {e}")
        text += "خطا در دریافت اطلاعات کاربران."
        
    await message.edit_text(text)


async def block_unblock_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    target_user = message.reply_to_message.from_user
    command = message.text.strip()
    try:
        if command == "بلاک روشن": await client.block_user(target_user.id); await message.edit_text(f"🚫 کاربر **{target_user.first_name}** بلاک شد.")
        elif command == "بلاک خاموش": await client.unblock_user(target_user.id); await message.edit_text(f"✅ کاربر **{target_user.first_name}** آنبلاک شد.")
    except Exception as e: await message.edit_text(f"⚠️ **خطا:** {e}")

async def mute_unmute_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    user_id, target_user, chat_id = client.me.id, message.reply_to_message.from_user, message.chat.id
    target_tuple = (target_user.id, chat_id)
    if user_id not in MUTED_USERS: MUTED_USERS[user_id] = set()

    if message.text.strip() == "سکوت روشن":
        MUTED_USERS[user_id].add(target_tuple)
        await message.edit_text(f"🔇 کاربر **{target_user.first_name}** در این چت سایلنت شد.")
    elif message.text.strip() == "سکوت خاموش":
        MUTED_USERS[user_id].discard(target_tuple)
        await message.edit_text(f"🔊 کاربر **{target_user.first_name}** از سایلنت خارج شد.")

async def auto_reaction_controller(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    user_id, target_user = client.me.id, message.reply_to_message.from_user
    command = message.text.strip()
    target_key = target_user.id
    if user_id not in AUTO_REACTION_TARGETS: AUTO_REACTION_TARGETS[user_id] = {}

    if command.startswith("ریاکشن") and command != "ریاکشن خاموش":
        parts = command.split()
        if len(parts) > 1:
            emoji = parts[-1]
            AUTO_REACTION_TARGETS[user_id][target_key] = emoji
            await message.edit_text(f"✅ واکنش خودکار با {emoji} برای **{target_user.first_name}** فعال شد.")
        else:
            await message.edit_text("⚠️ لطفا یک ایموجی مشخص کنید. مثال: `ریاکشن ❤️`")
    elif command == "ریاکشن خاموش":
        if AUTO_REACTION_TARGETS.get(user_id, {}).pop(target_key, None):
            await message.edit_text(f"❌ واکنش خودکار برای **{target_user.first_name}** غیرفعال شد.")

async def save_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        await message.delete()
        status_msg = await client.send_message(message.chat.id, "⏳ در حال ذخیره...")
        if message.reply_to_message.media:
            file_path = await client.download_media(message.reply_to_message)
            caption = "ذخیره شده با سلف بات"
            if message.reply_to_message.photo: await client.send_photo("me", file_path, caption=caption)
            elif message.reply_to_message.video: await client.send_video("me", file_path, caption=caption)
            else: await client.send_document("me", file_path, caption=caption)
            os.remove(file_path)
        else: await message.reply_to_message.copy("me")
        await status_msg.edit_text("✅ با موفقیت در Saved Messages ذخیره شد.")
        await asyncio.sleep(3)
        await status_msg.delete()
    except Exception as e: 
        await client.send_message(message.chat.id, f"⚠️ خطا در ذخیره: {e}")


async def repeat_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        count = int(message.text.split()[1])
        if count > 100:
            await message.edit_text("⚠️ حداکثر تکرار 100 است.")
            return
        await message.delete()
        for _ in range(count): await message.reply_to_message.copy(message.chat.id); await asyncio.sleep(0.1)
    except Exception: pass

async def delete_messages_controller(client, message):
    try:
        count = int(message.text.split()[1])
        if not (1 <= count <= 100):
            await message.edit_text("⚠️ تعداد باید بین 1 تا 100 باشد.")
            return
        
        message_ids = [message.id]
        async for msg in client.get_chat_history(message.chat.id, limit=count):
            if msg.from_user and msg.from_user.id == client.me.id:
                message_ids.append(msg.id)
        
        await client.delete_messages(message.chat.id, message_ids)
    except Exception as e:
        await message.edit_text(f"⚠️ خطا در حذف پیام: {e}")

async def pv_lock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    if command == "پیوی قفل":
        PV_LOCK_STATUS[user_id] = True
        await message.edit_text("قفل پیوی فعال شد ✅")
    elif command == "پیوی باز":
        PV_LOCK_STATUS[user_id] = False
        await message.edit_text("قفل پیوی غیرفعال شد ✅")

async def toggle_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    toggle_map = {
        "اینگیلیسی روشن": ("ترجمه انگلیسی", AUTO_TRANSLATE_TARGET, "en"),
        "اینگیلیسی خاموش": ("ترجمه انگلیسی", AUTO_TRANSLATE_TARGET, None),
        "روسی روشن": ("ترجمه روسی", AUTO_TRANSLATE_TARGET, "ru"),
        "روسی خاموش": ("ترجمه روسی", AUTO_TRANSLATE_TARGET, None),
        "چینی روشن": ("ترجمه چینی", AUTO_TRANSLATE_TARGET, "zh-CN"),
        "چینی خاموش": ("ترجمه چینی", AUTO_TRANSLATE_TARGET, None),
        "بولد روشن": ("بولد خودکار", BOLD_MODE_STATUS, True),
        "بولد خاموش": ("بولد خودکار", BOLD_MODE_STATUS, False),
        "سین روشن": ("سین خودکار", AUTO_SEEN_STATUS, True),
        "سین خاموش": ("سین خودکار", AUTO_SEEN_STATUS, False),
        "منشی روشن": ("منشی", SECRETARY_MODE_STATUS, True),
        "منشی خاموش": ("منشی", SECRETARY_MODE_STATUS, False),
        "انتی لوگین روشن": ("ضد لاگین", ANTI_LOGIN_STATUS, True),
        "انتی لوگین خاموش": ("ضد لاگین", ANTI_LOGIN_STATUS, False),
        "دشمن همگانی روشن": ("دشمن همگانی", GLOBAL_ENEMY_STATUS, True),
        "دشمن همگانی خاموش": ("دشمن همگانی", GLOBAL_ENEMY_STATUS, False),
        "تایپ روشن": ("تایپ خودکار", TYPING_MODE_STATUS, True),
        "تایپ خاموش": ("تایپ خودکار", TYPING_MODE_STATUS, False),
        "بازی روشن": ("بازی خودکار", PLAYING_MODE_STATUS, True),
        "بازی خاموش": ("بازی خودکار", PLAYING_MODE_STATUS, False),
    }

    if command in toggle_map:
        feature_name, status_dict, new_status = toggle_map[command]

        if command == "تایپ روشن":
            PLAYING_MODE_STATUS[user_id] = False
        elif command == "بازی روشن":
            TYPING_MODE_STATUS[user_id] = False
        
        if status_dict is AUTO_TRANSLATE_TARGET:
            lang_code_map = {"اینگیلیسی خاموش": "en", "روسی خاموش": "ru", "چینی خاموش": "zh-CN"}
            lang_to_turn_off = lang_code_map.get(command)
            if new_status:
                AUTO_TRANSLATE_TARGET[user_id] = new_status
            elif AUTO_TRANSLATE_TARGET.get(user_id) == lang_to_turn_off:
                AUTO_TRANSLATE_TARGET[user_id] = None
        else:
            status_dict[user_id] = new_status

        if command == "منشی روشن": USERS_REPLIED_IN_SECRETARY[user_id] = set()
        
        status_text = "فعال" if new_status or (status_dict is AUTO_TRANSLATE_TARGET and AUTO_TRANSLATE_TARGET.get(user_id)) else "غیرفعال"
        await message.edit_text(f"✅ **{feature_name} {status_text} شد.**")

async def copy_profile_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    chat_id = message.chat.id
    original_message_id = message.id

    if command == "کپی روشن":
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.edit_text("⚠️ برای کپی کردن، باید روی پیام شخص مورد نظر ریپلای کنید.")
            return

        await client.delete_messages(chat_id, original_message_id)
        status_msg = await client.send_message(chat_id, "⏳ در حال ذخیره پروفایل اصلی...")
        
        me = await client.get_me()
        me_chat = await client.get_chat("me")
        
        original_photo_paths = []
        async for photo in client.get_chat_photos("me"):
            path = await client.download_media(photo.file_id, file_name=f"original_{user_id}_{photo.file_id}.jpg")
            original_photo_paths.append(path)

        ORIGINAL_PROFILE_DATA[user_id] = {
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "bio": me_chat.bio or "",
            "photo_paths": original_photo_paths,
        }
        
        await status_msg.edit_text("⏳ در حال کپی کردن پروفایل هدف...")
        target_user = message.reply_to_message.from_user
        target_chat = await client.get_chat(target_user.id)
        
        target_photo_paths = []
        async for photo in client.get_chat_photos(target_user.id):
            target_photo_paths.append(await client.download_media(photo.file_id))
            
        current_photo_ids = [p.file_id async for p in client.get_chat_photos("me")]
        if current_photo_ids:
            await client.delete_profile_photos(current_photo_ids)
            
        for path in reversed(target_photo_paths):
            await client.set_profile_photo(photo=path)
            os.remove(path)
            
        await client.update_profile(first_name=target_user.first_name or "", last_name=target_user.last_name or "", bio=target_chat.bio or "")
        
        COPY_MODE_STATUS[user_id] = True
        await status_msg.edit_text(f"✅ پروفایل **{target_user.first_name}** با موفقیت کپی شد.")
        await asyncio.sleep(3)
        await status_msg.delete()

    elif command == "کپی خاموش":
        if user_id not in ORIGINAL_PROFILE_DATA:
            await message.edit_text("⚠️ پروفایلی برای بازگردانی یافت نشد.")
            return

        await client.delete_messages(chat_id, original_message_id)
        status_msg = await client.send_message(chat_id, "⏳ در حال بازگردانی پروفایل اصلی...")
        original_data = ORIGINAL_PROFILE_DATA[user_id]
        
        current_photo_ids = [p.file_id async for p in client.get_chat_photos("me")]
        if current_photo_ids:
            await client.delete_profile_photos(current_photo_ids)
            
        for path in reversed(original_data["photo_paths"]):
            if os.path.exists(path):
                await client.set_profile_photo(photo=path)
                os.remove(path)
            
        restored_name = original_data["first_name"]
        await client.update_profile(first_name=restored_name, last_name=original_data["last_name"], bio=original_data["bio"])
        
        COPY_MODE_STATUS.pop(user_id, None)
        
        if CLOCK_STATUS.get(user_id, True):
            asyncio.create_task(update_profile_clock(client, user_id))
        
        ORIGINAL_PROFILE_DATA.pop(user_id, None)
        await status_msg.edit_text("✅ پروفایل اصلی با موفقیت بازگردانی شد.")
        await asyncio.sleep(3)
        await status_msg.delete()

# --- Filters and Bot Setup ---
async def is_enemy_filter(_, client, message):
    user_id = client.me.id
    if GLOBAL_ENEMY_STATUS.get(user_id, False):
        return True
    return message.from_user and (message.from_user.id, message.chat.id) in ACTIVE_ENEMIES.get(user_id, set())

is_enemy = filters.create(is_enemy_filter)

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    try:
        await client.start()
        user_id = (await client.get_me()).id
    except (UserDeactivated, AuthKeyUnregistered) as e:
        logging.error(f"Session for phone {phone} is invalid ({type(e).__name__}). Removing from database.")
        if sessions_collection is not None:
            sessions_collection.delete_one({'phone_number': phone})
        return

    try:
        if user_id in ACTIVE_BOTS:
            for task in ACTIVE_BOTS[user_id][1]:
                if task: task.cancel()
            ACTIVE_BOTS.pop(user_id, None)
            await asyncio.sleep(1)
        
        # Initialize settings
        USER_FONT_CHOICES[user_id] = font_style
        CLOCK_STATUS[user_id] = not disable_clock
        
        # Handlers Registration
        client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=-5)
        client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
        client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
        client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
        
        client.add_handler(MessageHandler(help_controller, filters.text & filters.me & filters.regex("^راهنما$")))
        client.add_handler(MessageHandler(toggle_controller, filters.text & filters.me & filters.regex("^(اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|بولد روشن|بولد خاموش|سین روشن|سین خاموش|منشی روشن|منشی خاموش|انتی لوگین روشن|انتی لوگین خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش)$")))
        client.add_handler(MessageHandler(pv_lock_controller, filters.text & filters.me & filters.regex("^(پیوی قفل|پیوی باز)$")))
        client.add_handler(MessageHandler(font_controller, filters.text & filters.me & filters.regex(r"^(فونت|فونت \d+)$")))
        client.add_handler(MessageHandler(clock_controller, filters.text & filters.me & filters.regex("^(ساعت روشن|ساعت خاموش)$")))
        client.add_handler(MessageHandler(enemy_controller, filters.text & filters.me & filters.regex("^(دشمن روشن|دشمن خاموش)$")))
        client.add_handler(MessageHandler(list_enemies_controller, filters.text & filters.me & filters.regex("^لیست دشمن$")))
        client.add_handler(MessageHandler(block_unblock_controller, filters.text & filters.reply & filters.me & filters.regex("^(بلاک روشن|بلاک خاموش)$")))
        client.add_handler(MessageHandler(mute_unmute_controller, filters.text & filters.reply & filters.me & filters.regex("^(سکوت روشن|سکوت خاموش)$")))
        client.add_handler(MessageHandler(auto_reaction_controller, filters.text & filters.reply & filters.me & filters.regex("^(ریاکشن .*|ریاکشن خاموش)$")))
        client.add_handler(MessageHandler(copy_profile_controller, filters.text & filters.me & filters.regex("^(کپی روشن|کپی خاموش)$")))
        client.add_handler(MessageHandler(save_message_controller, filters.text & filters.reply & filters.me & filters.regex("^ذخیره$")))
        client.add_handler(MessageHandler(repeat_message_controller, filters.text & filters.reply & filters.me & filters.regex(r"^تکرار \d+$")))
        client.add_handler(MessageHandler(delete_messages_controller, filters.text & filters.me & filters.regex(r"^حذف \d+$")))
        client.add_handler(MessageHandler(game_controller, filters.text & filters.me & filters.regex(r"^(تاس|تاس \d+|بولینگ)$")))
        
        client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me), group=1)
        client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.service), group=1)

        tasks = [
            asyncio.create_task(update_profile_clock(client, user_id)),
            asyncio.create_task(anti_login_task(client, user_id)),
            asyncio.create_task(status_action_task(client, user_id))
        ]
        ACTIVE_BOTS[user_id] = (client, tasks)
        logging.info(f"Successfully started bot instance for user_id {user_id}.")
    except Exception as e:
        logging.error(f"FAILED to start bot instance for {phone}: {e}", exc_info=True)

# --- Web Section (Flask) ---
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سلف بات تلگرام</title><style>@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');body{font-family:'Vazirmatn',sans-serif;background-color:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:20px;box-sizing:border-box;}.container{background:white;padding:30px 40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);text-align:center;width:100%;max-width:480px;}h1{color:#333;margin-bottom:20px;font-size:1.5em;}p{color:#666;line-height:1.6;}form{display:flex;flex-direction:column;gap:15px;margin-top:20px;}input[type="tel"],input[type="text"],input[type="password"]{padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;text-align:left;direction:ltr;}button{padding:12px;background-color:#007bff;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;transition:background-color .2s;}.error{color:#d93025;margin-top:15px;font-weight:bold;}label{font-weight:bold;color:#555;display:block;margin-bottom:5px;text-align:right;}.font-options{border:1px solid #ddd;border-radius:8px;overflow:hidden;}.font-option{display:flex;align-items:center;padding:12px;border-bottom:1px solid #ddd;cursor:pointer;}.font-option:last-child{border-bottom:none;}.font-option input[type="radio"]{margin-left:15px;}.font-option label{display:flex;justify-content:space-between;align-items:center;width:100%;font-weight:normal;cursor:pointer;}.font-option .preview{font-size:1.3em;font-weight:bold;direction:ltr;color:#0056b3;}.success{color:#1e8e3e;}.checkbox-option{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:10px;padding:8px;background-color:#f8f9fa;border-radius:8px;}.checkbox-option label{margin-bottom:0;font-weight:normal;cursor:pointer;color:#444;}</style></head><body><div class="container">
{% if step == 'GET_PHONE' %}<h1>ورود به سلف بات</h1><p>شماره و تنظیمات خود را انتخاب کنید تا ربات فعال شود.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="phone"><div><label for="phone">شماره تلفن (با کد کشور)</label><input type="tel" id="phone" name="phone_number" placeholder="+989123456789" required autofocus></div><div><label>استایل فونت ساعت</label><div class="font-options">{% for name, data in font_previews.items() %}<div class="font-option" onclick="document.getElementById('font-{{ data.style }}').checked = true;"><input type="radio" name="font_style" value="{{ data.style }}" id="font-{{ data.style }}" {% if loop.first %}checked{% endif %}><label for="font-{{ data.style }}"><span>{{ name }}</span><span class="preview">{{ data.preview }}</span></label></div>{% endfor %}</div></div><div class="checkbox-option"><input type="checkbox" id="disable_clock" name="disable_clock"><label for="disable_clock">فعال‌سازی بدون ساعت</label></div><button type="submit">ارسال کد تایید</button></form>
{% elif step == 'GET_CODE' %}<h1>کد تایید</h1><p>کدی به تلگرام شما با شماره <strong>{{ phone_number }}</strong> ارسال شد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="code"><input type="text" name="code" placeholder="کد تایید" required><button type="submit">تایید کد</button></form>
{% elif step == 'GET_PASSWORD' %}<h1>رمز دو مرحله‌ای</h1><p>حساب شما نیاز به رمز تایید دو مرحله‌ای دارد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="password"><input type="password" name="password" placeholder="رمز عبور دو مرحله ای" required><button type="submit">ورود</button></form>
{% elif step == 'SHOW_SUCCESS' %}<h1>✅ ربات فعال شد!</h1><p>ربات با موفقیت فعال شد. برای دسترسی به قابلیت‌ها، در تلگرام پیام `راهنما` را ارسال کنید.</p><form action="{{ url_for('home') }}" method="get" style="margin-top: 20px;"><button type="submit">خروج و ورود مجدد</button></form>{% endif %}</div></body></html>
"""

def get_font_previews():
    sample_time = "12:34"
    return {FONT_DISPLAY_NAMES[key]: {"style": key, "preview": stylize_time(sample_time, key)} for key in FONT_KEYS_ORDER}

async def cleanup_client(phone):
    if client := ACTIVE_CLIENTS.pop(phone, None):
        if client.is_connected: await client.disconnect()

@app_flask.route('/')
def home():
    session.clear()
    return render_template_string(HTML_TEMPLATE, step='GET_PHONE', font_previews=get_font_previews())

@app_flask.route('/login', methods=['POST'])
def login():
    action = request.form.get('action')
    phone = session.get('phone_number')
    try:
        if not EVENT_LOOP.is_running():
            raise RuntimeError("Event loop is not running.")
            
        if action == 'phone':
            session['phone_number'] = request.form.get('phone_number')
            session['font_style'] = request.form.get('font_style')
            session['disable_clock'] = 'on' == request.form.get('disable_clock')
            future = asyncio.run_coroutine_threadsafe(send_code_task(session['phone_number']), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='GET_CODE', phone_number=session['phone_number'])
        elif action == 'code':
            future = asyncio.run_coroutine_threadsafe(sign_in_task(phone, request.form.get('code')), EVENT_LOOP)
            next_step = future.result(45)
            if next_step == 'GET_PASSWORD':
                return render_template_string(HTML_TEMPLATE, step='GET_PASSWORD', phone_number=phone)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
        elif action == 'password':
            future = asyncio.run_coroutine_threadsafe(check_password_task(phone, request.form.get('password')), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
    except Exception as e:
        if phone: 
            try:
                if EVENT_LOOP.is_running():
                    asyncio.run_coroutine_threadsafe(cleanup_client(phone), EVENT_LOOP)
            except RuntimeError:
                pass # Loop is already closed
        logging.error(f"Error during '{action}': {e}", exc_info=True)
        error_map = {
            (PhoneCodeInvalid, PasswordHashInvalid): "کد یا رمز وارد شده اشتباه است.",
            (PhoneNumberInvalid, TypeError): "شماره تلفن نامعتبر است.",
            PhoneCodeExpired: "کد تایید منقضی شده، دوباره تلاش کنید.",
            FloodWait: f"محدودیت تلگرام. لطفا {getattr(e, 'value', 5)} ثانیه دیگر تلاش کنید."
        }
        error_msg = "خطای پیش‌بینی نشده: " + str(e)
        current_step = 'GET_PHONE'
        for err_types, msg in error_map.items():
            if isinstance(e, err_types):
                error_msg = msg
                current_step = 'GET_CODE' if isinstance(e, PhoneCodeInvalid) else 'GET_PASSWORD'
                if isinstance(e, (PhoneNumberInvalid, TypeError, PhoneCodeExpired)): current_step = 'GET_PHONE'
                break
        if current_step == 'GET_PHONE': session.clear()
        return render_template_string(HTML_TEMPLATE, step=current_step, error_message=error_msg, phone_number=phone, font_previews=get_font_previews())
    return redirect(url_for('home'))

async def send_code_task(phone):
    await cleanup_client(phone)
    client = Client(f"user_{phone}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    ACTIVE_CLIENTS[phone] = client
    await client.connect()
    session['phone_code_hash'] = (await client.send_code(phone)).phone_code_hash

async def sign_in_task(phone, code):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.sign_in(phone, session['phone_code_hash'], code)
        session_str = await client.export_session_string()
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )
            
        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
        await cleanup_client(phone)
    except SessionPasswordNeeded:
        return 'GET_PASSWORD'

async def check_password_task(phone, password):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.check_password(password)
        session_str = await client.export_session_string()

        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )

        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
    finally:
        await cleanup_client(phone)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

def run_asyncio_loop():
    global EVENT_LOOP
    asyncio.set_event_loop(EVENT_LOOP)
    
    if sessions_collection is not None:
        logging.info("Found MongoDB collection, attempting to auto-login from database...")
        for doc in sessions_collection.find():
            try:
                session_string = doc['session_string']
                phone = doc.get('phone_number', f"db_session_{doc['_id']}")
                font_style = doc.get('font_style', 'stylized')
                disable_clock = doc.get('disable_clock', False)
                logging.info(f"Auto-starting session for {phone}...")
                EVENT_LOOP.create_task(start_bot_instance(session_string, phone, font_style, disable_clock))
            except Exception as e:
                logging.error(f"Failed to auto-start session for {doc.get('phone_number')}: {e}")

    try:
        EVENT_LOOP.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Event loop stopped by user.")
    finally:
        logging.info("Closing event loop.")
        if EVENT_LOOP.is_running():
            tasks = asyncio.all_tasks(loop=EVENT_LOOP)
            for task in tasks:
                task.cancel()
            
            async def gather_tasks():
                await asyncio.gather(*tasks, return_exceptions=True)

            # Run the gathering task to ensure cancellations are processed
            EVENT_LOOP.run_until_complete(gather_tasks())
            EVENT_LOOP.close()


if __name__ == "__main__":
    logging.info("Starting Telegram Self Bot Service...")
    loop_thread = Thread(target=run_asyncio_loop, daemon=True)
    loop_thread.start()
    run_flask()
