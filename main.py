# این ربات تلگرامی به عنوان پنل دکمه ای برای مدیریت عملیات های ممبر فیک، بازدید و پروفایل عمل می کند.
# توجه: برای حل مشکل Render 'No open ports detected'، یک سرور Flask ساده در یک Thread جداگانه اجرا می شود.

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask 
import threading 
import time
import os
import random
import asyncio
from urllib.parse import urlparse

# --- تنظیمات شما (به درخواست شما به صورت مستقیم در کد قرار داده شد) ---

API_ID = 24218762
API_HASH = "19695584ae95ea9bc5e1483e15b486a7"
ADMIN_ID = 7423552124  # <-- شناسه عددی شما
BOT_TOKEN = "8463921895:AAH8gcFXP6SgF7JDa37fS8parztegDeRsEs" # <-- توکن ربات شما

# --- تنظیمات عمومی ---
TARGET_CHANNEL = "@Your_Target_Channel_Username_Here" 
AVATAR_FOLDER = "random_avatars/" # پوشه تصاویر واقعی برای پروفایل فیک ها
SESSION_RAW_FILE = "aaaaaaaaaa_sessions_raw.txt" # <--- نام فایل سشن شما

# --- توابع کمکی ---

def get_session_strings(filepath):
    """سشن استرینگ ها را از هر خط فایل متنی می خواند."""
    try:
        if not os.path.exists(filepath):
            # اگر فایل وجود ندارد، یک لیست خالی برمی گردانیم
            return []
            
        with open(filepath, 'r', encoding='utf-8') as f:
            # هر خطی که خالی نیست و کاراکترهای سفید ندارد را به عنوان سشن استرینگ می خواند
            sessions = [line.strip() for line in f if line.strip()]
        return sessions
    except Exception as e:
        print(f"❌ خطای بحرانی در خواندن فایل سشن {filepath}: {e}")
        return []


def get_random_avatar_path(avatar_folder):
    """یک مسیر رندوم از تصاویر موجود در پوشه را برمی گرداند."""
    try:
        if not os.path.exists(avatar_folder):
            os.makedirs(avatar_folder)
            return None
        
        avatars = [f for f in os.listdir(avatar_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if avatars:
            return os.path.join(avatar_folder, random.choice(avatars))
        return None
    except Exception:
        return None

def parse_post_link(link):
    """لینک پست را تجزیه کرده و شناسه چت و شناسه پیام را برمی گرداند."""
    try:
        parsed_url = urlparse(link)
        path_parts = [p for p in parsed_url.path.split('/') if p]
        
        if len(path_parts) >= 2 and path_parts[0] == 'c':
            # لینک به شکل https://t.me/c/ChannelID/MessageID
            chat_id = int("-100" + path_parts[1])
            message_id = int(path_parts[2])
            return chat_id, message_id
        
        elif len(path_parts) >= 1:
            # لینک به شکل https://t.me/ChannelUsername/MessageID
            # یا اگر t.me/ تنها باشد، این قسمت کار نمی کند و باید لینک کامل باشد.
            if len(path_parts) == 1:
                # ممکن است یک یوزرنیم کانال باشد، اما MessageID لازم است.
                return None, None
            
            chat_id = "@" + path_parts[0]
            message_id = int(path_parts[1])
            return chat_id, message_id
            
        return None, None
    except Exception:
        return None, None


async def run_session_command(session_string, command, channel_username, avatar_folder=None, message_id=None):
    """یک عملیات مشخص را روی یک سشن فیک اجرا می کند."""
    
    # Pyrogram برای نام سشن به یک نام یونیک نیاز دارد، از یک UUID استفاده می کنیم.
    session_name = "Session_" + str(random.randint(10000, 99999)) 
    
    # 2. تعریف کلاینت با استفاده از Session String
    app_client = Client(
        name=session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string, # استفاده از سشن استرینگ
        in_memory=True # بهتر است برای سشن استرینگ ها از in_memory استفاده شود
    )
    avatar_path = get_random_avatar_path(avatar_folder) if command == 'set_profile' else None

    try:
        # اتصال به سشن
        await app_client.start()
        
        # برای اطمینان از دسترسی به چت، آن را دریافت می کنیم
        try:
            target_chat = await app_client.get_chat(channel_username)
        except Exception:
             # اگر کانال یافت نشد یا دسترسی نبود، خطا می دهد و ادامه نمی دهیم
            await app_client.stop()
            return f"❌ [خطا] {session_name}: کانال {channel_username} یافت نشد یا سشن دسترسی ندارد."


        if command == 'add_member':
            # Pyrogram به صورت هوشمند از join_chat برای کانال ها استفاده می کند.
            await app_client.join_chat(channel_username)
            result = f"✅ [افزودن موفق] {session_name} به {channel_username} اضافه شد."
        
        elif command == 'remove_member':
            await app_client.leave_chat(channel_username)
            result = f"🗑️ [حذف موفق] {session_name} از {channel_username} حذف شد."

        elif command == 'set_profile' and avatar_path:
            # حذف عکس قدیمی (برای طبیعی بودن) و تنظیم عکس جدید
            photos = await app_client.get_profile_photos("me")
            if photos:
                # حذف همه عکس های قدیمی
                await app_client.delete_profile_photos([p.file_id for p in photos])
            
            await app_client.set_profile_photo(photo=avatar_path)
            
            # افزودن نام فیک رندوم برای واقعی تر شدن
            first_names = ["علی", "سارا", "رضا", "مریم", "جواد", "زهرا", "محمد", "فاطمه", "امیر", "لیلا"]
            last_names = ["کرمی", "احمدی", "نوری", "حسینی", "رضایی", "طاهری", "شریفی", "قاسمی", "صابری", "کیانی"]
            
            # تنظیم نام و نام خانوادگی
            await app_client.update_profile(
                first_name=random.choice(first_names), 
                last_name=random.choice(last_names)
            )

            result = f"🖼️ [تنظیم پروفایل] {session_name} با عکس رندوم و نام جدید به‌روزرسانی شد."

        elif command == 'add_view':
            if not message_id:
                await app_client.stop()
                return f"❌ [خطا] {session_name}: شناسه پیام برای بازدید لازم است."
            
            # 1. مطمئن می شویم سشن در کانال عضو است
            try:
                # اگر سشن عضو نباشد، join_chat سعی می کند عضو شود.
                await app_client.join_chat(channel_username) 
            except Exception:
                await app_client.stop()
                return f"⚠️ [خطا] {session_name}: نتوانست عضو کانال شود. بازدید انجام نشد."

            # 2. بازدید از پست (فراخوانی get_messages یا read_history بازدید را ثبت می کند)
            # Pyrogram با خواندن پیام ها به صورت خودکار بازدید را ثبت می کند.
            await app_client.get_messages(
                chat_id=channel_username, 
                message_ids=message_id, 
                replies=0
            )

            result = f"👁️ [بازدید موفق] {session_name} پست {message_id} را در {channel_username} بازدید کرد."
        
        else:
            result = f"❓ [عملیات نامشخص] {session_name} عملیات انجام نشد."

        await app_client.stop()
        return result
        
    except Exception as e:
        # مکث تصادفی برای جلوگیری از محدودیت‌های سیل (Flood Limit)
        await asyncio.sleep(random.uniform(5, 15)) 
        return f"❌ [خطا در {command}] {session_name}: {type(e).__name__}: {str(e)}"

# --- تعریف ربات تلگرامی (Bot Client) ---

bot_app = Client(
    name="BotPanel", # نام سشن برای ربات
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN
)

# --- منوی اصلی و دکمه ها ---

def main_menu():
    """ایجاد کیبورد اصلی پنل مدیریت."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ افزودن ممبر", callback_data="add_members"),
            InlineKeyboardButton("➖ حذف ممبر", callback_data="remove_members")
        ],
        [
            InlineKeyboardButton("🖼️ تنظیم پروفایل (رندوم)", callback_data="set_profiles")
        ],
        [
            InlineKeyboardButton("👁️ شبیه‌ساز بازدید/ری‌اکشن", callback_data="simulate_views")
        ],
        [
            InlineKeyboardButton("تنظیم کانال هدف", callback_data="set_channel")
        ]
    ])

# --- هندلرهای دستورات و پیام ها ---

@bot_app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start_command(client, message):
    session_strings = get_session_strings(SESSION_RAW_FILE)
    num_sessions = len(session_strings)
    
    if not num_sessions:
        info_text = f"⚠️ **خطا:** هیچ سشن استرینگی در فایل `{SESSION_RAW_FILE}` یافت نشد."
    else:
        info_text = f"✅ **پنل فعال:** {num_sessions} سشن فیک آماده کار هستند."

    await message.reply_text(
        f"به پنل مدیریت خوش آمدید.\n\n"
        f"کانال هدف فعلی: **{TARGET_CHANNEL}**\n"
        f"{info_text}",
        reply_markup=main_menu()
    )

@bot_app.on_callback_query(filters.user(ADMIN_ID))
async def callback_handler(client, callback_query):
    global TARGET_CHANNEL 
    data = callback_query.data
    
    await callback_query.answer("درخواست شما در حال پردازش است.", show_alert=False)
    
    session_strings = get_session_strings(SESSION_RAW_FILE)
    
    # --- عملیات افزودن ممبر ---
    if data == "add_members":
        if not session_strings:
            return await callback_query.message.edit_text(f"❌ هیچ سشن استرینگی در فایل `{SESSION_RAW_FILE}` یافت نشد.", reply_markup=main_menu())

        await callback_query.message.edit_text(f"شروع افزودن {len(session_strings)} ممبر به **{TARGET_CHANNEL}**...", reply_markup=None)
        
        results = await asyncio.gather(*[
            run_session_command(s, 'add_member', TARGET_CHANNEL) for s in session_strings
        ])
        
        success_count = sum(1 for r in results if r.startswith("✅"))
        await callback_query.message.reply_text(
            f"✅ **عملیات افزودن به پایان رسید:** {success_count}/{len(session_strings)} موفق.", 
            reply_markup=main_menu()
        )
    
    # --- عملیات حذف ممبر ---
    elif data == "remove_members":
        if not session_strings:
            return await callback_query.message.edit_text(f"❌ هیچ سشن استرینگی در فایل `{SESSION_RAW_FILE}` یافت نشد.", reply_markup=main_menu())

        await callback_query.message.edit_text(f"شروع حذف {len(session_strings)} ممبر از **{TARGET_CHANNEL}**...", reply_markup=None)
        
        results = await asyncio.gather(*[
            run_session_command(s, 'remove_member', TARGET_CHANNEL) for s in session_strings
        ])
        
        success_count = sum(1 for r in results if r.startswith("🗑️"))
        await callback_query.message.reply_text(
            f"🗑️ **عملیات حذف به پایان رسید:** {success_count}/{len(session_strings)} موفق.", 
            reply_markup=main_menu()
        )

    # --- عملیات تنظیم پروفایل (رندوم) ---
    elif data == "set_profiles":
        if not session_strings:
             return await callback_query.message.edit_text(f"❌ هیچ سشن استرینگی در فایل `{SESSION_RAW_FILE}` برای تنظیم پروفایل یافت نشد.", reply_markup=main_menu())

        if not get_random_avatar_path(AVATAR_FOLDER):
            return await callback_query.message.edit_text(
                f"!!! خطا: پوشه **`{AVATAR_FOLDER}`** خالی است.\n\n"
                f"لطفا چند عکس با ظاهر واقعی را در این پوشه قرار دهید.",
                reply_markup=main_menu()
            )
        
        await callback_query.message.edit_text(f"🖼️ شروع تنظیم پروفایل رندوم برای {len(session_strings)} سشن...", reply_markup=None)
        
        results = await asyncio.gather(*[
            run_session_command(s, 'set_profile', TARGET_CHANNEL, AVATAR_FOLDER) for s in session_strings
        ])

        success_count = sum(1 for r in results if r.startswith("🖼️"))
        await callback_query.message.reply_text(
            f"🖼️ **عملیات تنظیم پروفایل به پایان رسید:** {success_count}/{len(session_strings)} موفق.", 
            reply_markup=main_menu()
        )
        
    # --- شبیه ساز بازدید/ری‌اکشن ---
    elif data == "simulate_views":
        await callback_query.message.edit_text(
            "⚠️ **مدیریت بازدید/ری‌اکشن:**\n\n"
            "برای افزودن بازدید واقعی به پست، دستور زیر را ارسال کنید:\n"
            "دستور بازدید: `/boost <تعداد_بازدید> <لینک_پست>`\n"
            "مثال: `/boost 100 https://t.me/ChannelUsername/1234`\n\n"
            "**توجه:** ری‌اکشن هنوز پیاده‌سازی نشده است.",
            reply_markup=main_menu()
        )
        
    # --- تنظیم کانال هدف ---
    elif data == "set_channel":
        await callback_query.message.edit_text(
            "لطفاً یوزرنیم کانال هدف جدید را به صورت زیر ارسال کنید:\n"
            "`/setchannel @YourNewChannel`",
            reply_markup=main_menu()
        )
        
# --- هندلر دستور /boost (بازدید واقعی) ---
@bot_app.on_message(filters.command("boost") & filters.user(ADMIN_ID))
async def boost_command(client, message):
    session_strings = get_session_strings(SESSION_RAW_FILE)
    if not session_strings:
        return await message.reply_text(f"❌ هیچ سشن استرینگی در فایل `{SESSION_RAW_FILE}` یافت نشد.", reply_markup=main_menu())
        
    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            return await message.reply_text("فرمت صحیح: `/boost <تعداد> <لینک_پست>`", reply_markup=main_menu())
        
        count = int(command_parts[1])
        post_link = command_parts[2]
        
        if count <= 0:
            return await message.reply_text("تعداد بازدید باید یک عدد مثبت باشد.", reply_markup=main_menu())

        # تجزیه لینک
        channel_id, message_id = parse_post_link(post_link)
        
        if not channel_id or not message_id:
            return await message.reply_text(
                "❌ **خطا در لینک:** لطفاً لینک پست را با فرمت صحیح (مانند `https://t.me/ChannelUsername/123` یا `https://t.me/c/ChannelID/123`) وارد کنید.", 
                reply_markup=main_menu()
            )
            
        # محدود کردن تعداد سشن‌ها به تعداد درخواستی
        sessions_to_use = session_strings[:min(count, len(session_strings))]
        
        await message.reply_text(
            f"🚀 **شروع عملیات بازدید واقعی:**\n\n"
            f"تعداد سشن‌های مورد استفاده: **{len(sessions_to_use)}** (حداکثر {count} بازدید درخواست شده)\n"
            f"هدف: **{channel_id}/{message_id}**\n\n"
            f"**لطفا صبر کنید...** این عملیات ممکن است کمی زمان ببرد.",
            reply_markup=None
        )
        
        # اجرای موازی عملیات بازدید
        tasks = [
            run_session_command(s, 'add_view', channel_id, message_id=message_id) 
            for s in sessions_to_use
        ]
        
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r.startswith("👁️"))
        
        await message.reply_text(
            f"✅ **عملیات بازدید به پایان رسید:**\n"
            f"بازدیدهای موفق: **{success_count}** از {len(sessions_to_use)} سشن.", 
            reply_markup=main_menu()
        )

    except ValueError:
        await message.reply_text("لطفاً یک عدد صحیح برای تعداد وارد کنید.", reply_markup=main_menu())
    except Exception as e:
        await message.reply_text(f"خطا در اجرای دستور: {e}", reply_markup=main_menu())

# --- هندلر دستور /setchannel (تنظیم کانال هدف) ---
@bot_app.on_message(filters.command("setchannel") & filters.user(ADMIN_ID))
async def setchannel_command(client, message):
    global TARGET_CHANNEL 
    
    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            return await message.reply_text("لطفاً یوزرنیم کانال هدف را بعد از دستور /setchannel وارد کنید.", reply_markup=main_menu())

        new_channel = command_parts[1]
        if not new_channel.startswith('@'):
            return await message.reply_text("یوزرنیم کانال باید با '@' شروع شود.")
        
        TARGET_CHANNEL = new_channel
        await message.reply_text(
            f"✅ **کانال هدف با موفقیت تغییر کرد:** {TARGET_CHANNEL}",
            reply_markup=main_menu()
        )
    except Exception as e:
        await message.reply_text(f"خطا در تنظیم کانال: {e}", reply_markup=main_menu())
        
# --------------------------------------------------------------------------------
# --- سرور Flask برای چک کردن سلامت Render (Health Check) ---
# --------------------------------------------------------------------------------

# تعریف اپلیکیشن Flask
web_app = Flask(__name__)

# تعریف مسیر برای چک کردن سلامت
@web_app.route('/')
def health_check():
    # پاسخ ساده HTTP 200 برای تأیید فعال بودن سرویس
    return 'Telegram Bot is Running and Healthy', 200

# تابع برای اجرای سرور Flask در یک رشته جداگانه
def run_flask_server():
    # پورت مورد نیاز را از متغیر محیطی Render می خواند (به طور پیش‌فرض 5000)
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Starting Flask Web Server on port {port} for Render Health Check...")
    # هاست 0.0.0.0 ضروری است تا در محیط کانتینر Render به درستی اجرا شود
    web_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --------------------------------------------------------------------------------
# --- اجرای اصلی ---
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    # 1. سرور Flask را در یک رشته جداگانه شروع کنید
    flask_thread = threading.Thread(target=run_flask_server)
    # daemon=True اجازه می دهد که برنامه اصلی حتی اگر این رشته در حال اجراست، بسته شود
    flask_thread.daemon = True 
    flask_thread.start()
    
    # 2. ربات Pyrogram را در رشته اصلی اجرا کنید (bot_app.run() مسدود کننده است)
    print("🤖 Starting Pyrogram Bot in main thread...")
    print(f"API ID: {API_ID}, ADMIN ID: {ADMIN_ID}")
    
    try:
        bot_app.run() 
    except Exception as e:
        print(f"🛑 Error running Pyrogram bot: {e}")
