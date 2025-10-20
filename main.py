```python
import asyncio
import logging
import re
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered
)
from datetime import datetime
from zoneinfo import ZoneInfo
import random
import hashlib

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# --- Main Settings ---
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"
BOT_TOKEN = "8233582209:AAHKPQX-349tAfBOCFWbRRqcpD-QbVrDzQ0"
ADMIN_USER_ID = 7423552124  # ادمین اولیه

# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
EVENT_LOOP = asyncio.new_event_loop()
ACTIVE_BOTS = {}  # {user_id: (client, tasks)}
ACTIVE_CLIENTS = {}  # {phone: client}
USERS = {}  # {user_id: {"phone": str, "diamonds": int, "self_active": bool, "self_start_time": float, "invite_link": str, "font_style": str}}
ADMINS = {ADMIN_USER_ID: True}  # {user_id: bool}
SETTINGS = {
    "diamond_price": 40,  # قیمت هر الماس به تومان
    "initial_diamonds": 100,  # الماس اولیه برای کاربران جدید
    "self_cost_per_hour": 10,  # هزینه سلف به ازای هر ساعت (الماس)
    "mandatory_channel": "@YourChannel",  # لینک کانال/گروه اجباری
    "card_number": "1234-5678-9012-3456"  # شماره کارت برای پرداخت
}
TRANSACTIONS = []  # [{"user_id": int, "amount": int, "status": str, "receipt_id": str, "timestamp": float}]
BET_GAMES = {}  # {chat_id: {"amount": int, "players": {user_id: username}}}
OFFLINE_MODE = False
ENEMY_MODE = {}  # {user_id: bool}
INVITE_REWARDS = {}  # {user_id: [invited_user_ids]}

# --- Clock Font Dictionaries ---
FONT_STYLES = {
    "cursive": {'0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗', ':': ':'},
    "stylized": {'0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵', ':': ':'},
    "doublestruck": {'0': '𝟘', '1': '𝟙', '2': '𝟚', '3': '𝟛', '4': '𝟜', '5': '𝟝', '6': '𝟞', '7': '𝟟', '8': '𝟠', '9': '𝟡', ':': ':'},
    "monospace": {'0': '𝟶', '1': '𝟷', '2': '𝟸', '3': '𝟹', '4': '𝟺', '5': '𝟻', '6': '𝟼', '7': '𝟽', '8': '𝟾', '9': '𝟿', ':': ':'},
    "normal": {'0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', ':': ':'},
    "circled": {'0': '⓪', '1': '①', '2': '②', '3': '③', '4': '④', '5': '⑤', '6': '⑥', '7': '⑦', '8': '⑧', '9': '⑨', ':': '∶'},
    "fullwidth": {'0': '０', '1': '１', '2': '２', '3': '３', '4': '４', '5': '５', '6': '６', '7': '７', '8': '８', '9': '۹', ':': '：'},
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
    "کیرم تو رحم اجاره ای و خونی مالی مادرت",
    "کیرم تو کس سیاه مادرت خارکصده",
    "حروم زاده باک کص ننت با ابکیرم پر میکنم",
    "منبع اب ایرانو با اب کص مادرت تامین میکنم",
    "خارکسته میخای مادرتو بگام بعد بیای ادعای شرف کنی کیرم تو شرف مادرت",
]
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."
USER_FONT_CHOICES = {}
CLOCK_STATUS = {}

# --- Bot Setup ---
app = Client("self_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Helper Functions ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

def generate_invite_link(user_id: int) -> str:
    return f"https://t.me/{app.bot_username}?start={hashlib.md5(str(user_id).encode()).hexdigest()}"

async def check_channel_membership(client, user_id: int, channel: str) -> bool:
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True):
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
            logging.error(f"Clock Task: Session for user_id {user_id} is invalid.")
            break
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            logging.error(f"Error in clock task for user_id {user_id}: {e}")
            await asyncio.sleep(60)

async def self_cost_task(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS and USERS.get(user_id, {}).get("self_active", False):
        try:
            user = USERS.get(user_id, {})
            if user["diamonds"] >= SETTINGS["self_cost_per_hour"]:
                USERS[user_id]["diamonds"] -= SETTINGS["self_cost_per_hour"]
                await client.send_message(user_id, f"💎 {SETTINGS['self_cost_per_hour']} الماس برای یک ساعت سلف کسر شد.")
            else:
                USERS[user_id]["self_active"] = False
                await client.send_message(user_id, "❌ موجودی الماس کافی نیست. سلف غیرفعال شد.")
            await asyncio.sleep(3600)
        except Exception as e:
            logging.error(f"Error in self cost task for user_id {user_id}: {e}")
            await asyncio.sleep(60)

# --- Handlers ---
async def start_command(client, message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) > 1:  # دعوت از طریق لینک
        inviter_hash = args[1]
        for inviter_id, data in USERS.items():
            if hashlib.md5(str(inviter_id).encode()).hexdigest() == inviter_hash:
                if user_id not in INVITE_REWARDS.get(inviter_id, []):
                    INVITE_REWARDS.setdefault(inviter_id, []).append(user_id)
                    USERS[inviter_id]["diamonds"] += 50
                    await client.send_message(inviter_id, "🎉 یک کاربر جدید از طریق لینک دعوت شما ثبت‌نام کرد! 50 الماس پاداش دریافت کردید.")
                break
    if user_id not in USERS:
        USERS[user_id] = {"phone": None, "diamonds": SETTINGS["initial_diamonds"], "self_active": False, "self_start_time": 0, "invite_link": generate_invite_link(user_id), "font_style": "stylized"}
        await client.send_message(user_id, "لطفاً شماره تلفن خود را (با فرمت +989xxxxxxxxx) ارسال کنید.")
    else:
        await show_main_menu(client, message)

async def handle_phone(client, message):
    user_id = message.from_user.id
    phone = message.text.strip()
    if not re.match(r"^\+989[0-9]{9}$", phone):
        await message.reply("⚠️ شماره تلفن نامعتبر است. فرمت: +989xxxxxxxxx")
        return
    USERS[user_id]["phone"] = phone
    client = Client(f"user_{phone}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    ACTIVE_CLIENTS[phone] = client
    await client.connect()
    try:
        phone_code_hash = (await client.send_code(phone)).phone_code_hash
        USERS[user_id]["phone_code_hash"] = phone_code_hash
        await message.reply("کدی به تلگرام شما ارسال شد. لطفاً کد تأیید را ارسال کنید.")
    except Exception as e:
        await message.reply(f"⚠️ خطا: {str(e)}")
        await client.disconnect()
        ACTIVE_CLIENTS.pop(phone, None)

async def handle_code(client, message):
    user_id = message.from_user.id
    if user_id not in USERS or not USERS[user_id].get("phone"):
        await message.reply("⚠️ ابتدا شماره تلفن خود را ثبت کنید.")
        return
    phone = USERS[user_id]["phone"]
    code = message.text.strip()
    client = ACTIVE_CLIENTS.get(phone)
    if not client:
        await message.reply("⚠️ جلسه منقضی شده است. دوباره شروع کنید.")
        return
    try:
        await client.sign_in(phone, USERS[user_id]["phone_code_hash"], code)
        session_str = await client.export_session_string()
        USERS[user_id]["session_string"] = session_str
        await start_bot_instance(session_str, phone, user_id, USERS[user_id]["font_style"])
        await client.disconnect()
        ACTIVE_CLIENTS.pop(phone, None)
        await message.reply("✅ با موفقیت وارد شدید!", reply_markup=await get_main_menu())
    except SessionPasswordNeeded:
        await message.reply("رمز دو مرحله‌ای مورد نیاز است. لطفاً رمز را ارسال کنید.")
    except Exception as e:
        await message.reply(f"⚠️ خطا: {str(e)}")
        ACTIVE_CLIENTS.pop(phone, None)
        await client.disconnect()

async def handle_password(client, message):
    user_id = message.from_user.id
    if user_id not in USERS or not USERS[user_id].get("phone"):
        await message.reply("⚠️ ابتدا شماره تلفن خود را ثبت کنید.")
        return
    phone = USERS[user_id]["phone"]
    password = message.text.strip()
    client = ACTIVE_CLIENTS.get(phone)
    if not client:
        await message.reply("⚠️ جلسه منقضی شده است. دوباره شروع کنید.")
        return
    try:
        await client.check_password(password)
        session_str = await client.export_session_string()
        USERS[user_id]["session_string"] = session_str
        await start_bot_instance(session_str, phone, user_id, USERS[user_id]["font_style"])
        await client.disconnect()
        ACTIVE_CLIENTS.pop(phone, None)
        await message.reply("✅ با موفقیت وارد شدید!", reply_markup=await get_main_menu())
    except Exception as e:
        await message.reply(f"⚠️ خطا: {str(e)}")
        ACTIVE_CLIENTS.pop(phone, None)
        await client.disconnect()

async def show_main_menu(client, message):
    user_id = message.from_user.id
    buttons = [
        [InlineKeyboardButton("💎 موجودی", callback_data="balance")],
        [InlineKeyboardButton("🛠 فعال‌سازی سلف", callback_data="activate_self")],
        [InlineKeyboardButton("💳 افزایش موجودی", callback_data="buy_diamonds")],
        [InlineKeyboardButton("🔤 تغییر فونت سلف", callback_data="change_font")],
        [InlineKeyboardButton("🔄 خاموش/روشن سلف", callback_data="toggle_self")],
        [InlineKeyboardButton("🗑 حذف سلف", callback_data="delete_self")],
        [InlineKeyboardButton("🎁 کسب الماس رایگان", callback_data="free_diamonds")],
        [InlineKeyboardButton("🔁 انتقال الماس", callback_data="transfer_diamonds")],
        [InlineKeyboardButton("⚔️ حالت دشمن", callback_data="toggle_enemy")]
    ]
    if user_id in ADMINS:
        buttons.append([InlineKeyboardButton("👑 پنل ادمین", callback_data="admin_panel")])
    await message.reply("به ربات سلف خوش آمدید!", reply_markup=InlineKeyboardMarkup(buttons))

async def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 موجودی", callback_data="balance")],
        [InlineKeyboardButton("🛠 فعال‌سازی سلف", callback_data="activate_self")],
        [InlineKeyboardButton("💳 افزایش موجودی", callback_data="buy_diamonds")],
        [InlineKeyboardButton("🔤 تغییر فونت سلف", callback_data="change_font")],
        [InlineKeyboardButton("🔄 خاموش/روشن سلف", callback_data="toggle_self")],
        [InlineKeyboardButton("🗑 حذف سلف", callback_data="delete_self")],
        [InlineKeyboardButton("🎁 کسب الماس رایگان", callback_data="free_diamonds")],
        [InlineKeyboardButton("🔁 انتقال الماس", callback_data="transfer_diamonds")],
        [InlineKeyboardButton("⚔️ حالت دشمن", callback_data="toggle_enemy")]
    ])

async def handle_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    if data == "balance":
        diamonds = USERS.get(user_id, {}).get("diamonds", 0)
        tooman = diamonds * SETTINGS["diamond_price"]
        await callback_query.message.edit(f"💎 موجودی شما: {diamonds} الماس\n💰 معادل: {tooman:,} تومان", reply_markup=await get_main_menu())
    elif data == "activate_self":
        if not await check_channel_membership(client, user_id, SETTINGS["mandatory_channel"]):
            await callback_query.message.edit(f"⚠️ ابتدا باید در {SETTINGS['mandatory_channel']} عضو شوید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="main_menu")]]))
            return
        if USERS.get(user_id, {}).get("diamonds", 0) < SETTINGS["self_cost_per_hour"]:
            await callback_query.message.edit("⚠️ موجودی الماس کافی نیست.", reply_markup=await get_main_menu())
            return
        await callback_query.message.edit("لطفاً شماره تلفن خود را برای فعال‌سازی سلف (با فرمت +989xxxxxxxxx) ارسال کنید.")
    elif data == "buy_diamonds":
        await callback_query.message.edit("لطفاً تعداد الماس مورد نظر برای خرید را وارد کنید.")
    elif data == "change_font":
        buttons = [[InlineKeyboardButton(FONT_DISPLAY_NAMES[font], callback_data=f"font_{font}")] for font in FONT_KEYS_ORDER]
        buttons.append([InlineKeyboardButton("بازگشت", callback_data="main_menu")])
        await callback_query.message.edit("فونت مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("font_"):
        font = data.split("_")[1]
        USERS[user_id]["font_style"] = font
        USER_FONT_CHOICES[user_id] = font
        CLOCK_STATUS[user_id] = True
        await callback_query.message.edit(f"✅ فونت به {FONT_DISPLAY_NAMES[font]} تغییر یافت.", reply_markup=await get_main_menu())
    elif data == "toggle_self":
        if USERS.get(user_id, {}).get("self_active", False):
            USERS[user_id]["self_active"] = False
            CLOCK_STATUS[user_id] = False
            await callback_query.message.edit("❌ سلف غیرفعال شد.", reply_markup=await get_main_menu())
        else:
            if USERS.get(user_id, {}).get("diamonds", 0) < SETTINGS["self_cost_per_hour"]:
                await callback_query.message.edit("⚠️ موجودی الماس کافی نیست.", reply_markup=await get_main_menu())
                return
            USERS[user_id]["self_active"] = True
            USERS[user_id]["self_start_time"] = time.time()
            CLOCK_STATUS[user_id] = True
            await callback_query.message.edit("✅ سلف فعال شد.", reply_markup=await get_main_menu())
    elif data == "delete_self":
        if user_id in ACTIVE_BOTS:
            client, tasks = ACTIVE_BOTS[user_id]
            for task in tasks:
                task.cancel()
            await client.stop()
            del ACTIVE_BOTS[user_id]
        USERS[user_id]["self_active"] = False
        CLOCK_STATUS[user_id] = False
        await callback_query.message.edit("🗑 سلف حذف شد.", reply_markup=await get_main_menu())
    elif data == "free_diamonds":
        invite_link = USERS[user_id]["invite_link"]
        await callback_query.message.edit(f"لینک دعوت شما:\n{invite_link}\nبا دعوت دوستان و عضویت آن‌ها در {SETTINGS['mandatory_channel']}، 50 الماس رایگان دریافت کنید!", reply_markup=await get_main_menu())
    elif data == "transfer_diamonds":
        await callback_query.message.edit("لطفاً تعداد الماس و آیدی گیرنده (مثل @username) را به صورت زیر وارد کنید:\n10 @username")
    elif data == "toggle_enemy":
        ENEMY_MODE[user_id] = not ENEMY_MODE.get(user_id, False)
        status = "فعال" if ENEMY_MODE[user_id] else "غیرفعال"
        await callback_query.message.edit(f"⚔️ حالت دشمن {status} شد.", reply_markup=await get_main_menu())
    elif data == "main_menu":
        await callback_query.message.edit("منوی اصلی:", reply_markup=await get_main_menu())
    elif data == "admin_panel" and user_id in ADMINS:
        await callback_query.message.edit("پنل ادمین:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("اضافه/حذف ادمین", callback_data="manage_admins")],
            [InlineKeyboardButton("تنظیم قیمت الماس", callback_data="set_diamond_price")],
            [InlineKeyboardButton("تنظیم موجودی اولیه", callback_data="set_initial_diamonds")],
            [InlineKeyboardButton("مشاهده تراکنش‌ها", callback_data="view_transactions")],
            [InlineKeyboardButton("تأیید/رد رسید", callback_data="manage_receipts")],
            [InlineKeyboardButton("تنظیم تعرفه سلف", callback_data="set_self_cost")],
            [InlineKeyboardButton("تنظیم لینک عضویت", callback_data="set_channel")],
            [InlineKeyboardButton("مشاهده وضعیت کاربران", callback_data="view_users")],
            [InlineKeyboardButton("حالت آفلاین روشن/خاموش", callback_data="toggle_offline")],
            [InlineKeyboardButton("مدیریت شرط‌بندی", callback_data="manage_bets")],
            [InlineKeyboardButton("بازگشت", callback_data="main_menu")]
        ]))
    elif data == "manage_admins":
        await callback_query.message.edit("لطفاً آیدی عددی کاربر را برای اضافه/حذف ادمین ارسال کنید (یا برای بازگشت بنویسید 'لغو').")
    elif data == "set_diamond_price":
        await callback_query.message.edit("لطفاً قیمت جدید هر الماس (به تومان) را وارد کنید.")
    elif data == "set_initial_diamonds":
        await callback_query.message.edit("لطفاً تعداد الماس اولیه برای کاربران جدید را وارد کنید.")
    elif data == "view_transactions":
        text = "📜 **لیست تراکنش‌ها:**\n\n"
        for t in TRANSACTIONS:
            status = "تأیید شده" if t["status"] == "approved" else "در انتظار" if t["status"] == "pending" else "رد شده"
            text += f"کاربر: {t['user_id']}\nتعداد الماس: {t['amount']}\nوضعیت: {status}\nزمان: {datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        await callback_query.message.edit(text or "هیچ تراکنشی وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))
    elif data == "manage_receipts":
        pending = [t for t in TRANSACTIONS if t["status"] == "pending"]
        if not pending:
            await callback_query.message.edit("هیچ رسید در انتظاری وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))
            return
        buttons = [[InlineKeyboardButton(f"کاربر {t['user_id']} - {t['amount']} الماس", callback_data=f"receipt_{t['user_id']}_{t['receipt_id']}")] for t in pending]
        buttons.append([InlineKeyboardButton("بازگشت", callback_data="admin_panel")])
        await callback_query.message.edit("رسیدهای در انتظار:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("receipt_"):
        _, target_user_id, receipt_id = data.split("_")
        target_user_id = int(target_user_id)
        buttons = [
            [InlineKeyboardButton("تأیید", callback_data=f"approve_receipt_{target_user_id}_{receipt_id}")],
            [InlineKeyboardButton("رد", callback_data=f"reject_receipt_{target_user_id}_{receipt_id}")],
            [InlineKeyboardButton("بازگشت", callback_data="manage_receipts")]
        ]
        await callback_query.message.edit("انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("approve_receipt_"):
        _, target_user_id, receipt_id = data.split("_")
        target_user_id = int(target_user_id)
        for t in TRANSACTIONS:
            if t["user_id"] == target_user_id and t["receipt_id"] == receipt_id and t["status"] == "pending":
                t["status"] = "approved"
                USERS[target_user_id]["diamonds"] += t["amount"]
                await client.send_message(target_user_id, f"✅ خرید {t['amount']} الماس تأیید شد!")
                break
        await callback_query.message.edit("✅ رسید تأیید شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="manage_receipts")]]))
    elif data.startswith("reject_receipt_"):
        _, target_user_id, receipt_id = data.split("_")
        target_user_id = int(target_user_id)
        for t in TRANSACTIONS:
            if t["user_id"] == target_user_id and t["receipt_id"] == receipt_id and t["status"] == "pending":
                t["status"] = "rejected"
                await client.send_message(target_user_id, "❌ رسید خرید شما رد شد.")
                break
        await callback_query.message.edit("❌ رسید رد شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="manage_receipts")]]))
    elif data == "set_self_cost":
        await callback_query.message.edit("لطفاً تعرفه جدید سلف (الماس در ساعت) را وارد کنید.")
    elif data == "set_channel":
        await callback_query.message.edit("لطفاً لینک جدید کانال/گروه اجباری را وارد کنید (مثال: @YourChannel).")
    elif data == "view_users":
        text = "👥 **وضعیت کاربران:**\n\n"
        for uid, data in USERS.items():
            status = "فعال" if data["self_active"] else "غیرفعال"
            text += f"کاربر: {uid}\nموجودی: {data['diamonds']} الماس\nوضعیت سلف: {status}\nفونت: {FONT_DISPLAY_NAMES.get(data['font_style'], 'نامشخص')}\n\n"
        await callback_query.message.edit(text or "هیچ کاربری وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))
    elif data == "toggle_offline":
        global OFFLINE_MODE
        OFFLINE_MODE = not OFFLINE_MODE
        status = "فعال" if OFFLINE_MODE else "غیرفعال"
        await callback_query.message.edit(f"✅ حالت آفلاین {status} شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))
    elif data == "manage_bets":
        if not BET_GAMES:
            await callback_query.message.edit("هیچ شرط‌بندی فعالی وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))
            return
        text = "🎰 **شرط‌بندی‌های فعال:**\n\n"
        for chat_id, game in BET_GAMES.items():
            text += f"گروه: {chat_id}\nمقدار: {game['amount']} الماس\nبازیکنان: {', '.join(game['players'].values())}\n\n"
        await callback_query.message.edit(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]]))

async def handle_admin_commands(client, message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return
    text = message.text.strip()
    if text.startswith("/send @"):
        try:
            _, username, amount = text.split()
            username = username.lstrip("@")
            amount = int(amount)
            target_user = await client.get_users(username)
            USERS.setdefault(target_user.id, {"diamonds": 0, "self_active": False, "self_start_time": 0, "invite_link": generate_invite_link(target_user.id), "font_style": "stylized"})
            USERS[target_user.id]["diamonds"] += amount
            await message.reply(f"✅ {amount} الماس به {username} ارسال شد.")
            await client.send_message(target_user.id, f"✅ {amount} الماس به موجودی شما اضافه شد.")
        except Exception as e:
            await message.reply(f"⚠️ خطا: {str(e)}")
    elif text.startswith("/start_bet"):
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.reply("⚠️ شرط‌بندی فقط در گروه‌ها ممکن است.")
            return
        try:
            _, amount = text.split()
            amount = int(amount)
            BET_GAMES[message.chat.id] = {"amount": amount, "players": {}}
            await message.reply(f"🎰 شرط‌بندی با {amount} الماس شروع شد! برای شرکت، عدد {amount} را بنویسید.")
        except ValueError:
            await message.reply("⚠️ لطفاً مقدار معتبر وارد کنید. مثال: /start_bet 50")

async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    if user_id not in USERS:
        await start_command(client, message)
        return
    if OFFLINE_MODE and user_id not in ADMINS:
        await message.reply(SECRETARY_REPLY_MESSAGE)
        return
    if user_id in ENEMY_MODE and ENEMY_MODE[user_id]:
        await message.reply(random.choice(ENEMY_REPLIES))
        return
    if USERS[user_id].get("phone") is None:
        await handle_phone(client, message)
    elif USERS[user_id].get("phone_code_hash") and not USERS[user_id].get("session_string"):
        await handle_code(client, message)
    elif USERS[user_id].get("phone_code_hash"):
        await handle_password(client, message)
    elif message.reply_to_message and text.isdigit():  # انتقال الماس در چت خصوصی
        if message.chat.type != ChatType.PRIVATE:
            await message.reply("⚠️ انتقال الماس فقط در چت خصوصی ممکن است.")
            return
        amount = int(text)
        target_user = message.reply_to_message.from_user
        if USERS[user_id]["diamonds"] < amount:
            await message.reply("⚠️ موجودی کافی نیست.")
            return
        USERS.setdefault(target_user.id, {"diamonds": 0, "self_active": False, "self_start_time": 0, "invite_link": generate_invite_link(target_user.id), "font_style": "stylized"})
        USERS[user_id]["diamonds"] -= amount
        USERS[target_user.id]["diamonds"] += amount
        await message.reply(f"""
👤 فرستنده: @{message.from_user.username}
👥 گیرنده: @{target_user.username}
💵 مبلغ: {amount}
🧾 مالیات: ۰
✅ واری28. You can generate a session string for the user's account using the `export_session_string` method from the Pyrogram library. Here's an example of how to do it:

```python
from pyrogram import Client

async def main():
    # Initialize the client with your API ID and Hash
    client = Client("my_session", api_id=API_ID, api_hash=API_HASH)
    
    # Start the client
    await client.start()
    
    # Export the session string
    session_string = await client.export_session_string()
    
    print("Session String:", session_string)
    
    # Stop the client
    await client.stop()

# Run the async function
import asyncio
asyncio.run(main())
```

This code will generate a session string that you can use to log in to the user's account without needing to re-authenticate each time. The session string should be stored securely, as it grants access to the account.

**Important Notes:**
- Replace `API_ID` and `API_HASH` with your actual Telegram API credentials.
- The session string is sensitive information and should be kept confidential to prevent unauthorized access to the account.
- If the account has two-factor authentication enabled, you may need to handle the `SessionPasswordNeeded` exception and provide the password.

Would you like me to explain any part of this process in more detail?
