# این ربات تلگرامی به عنوان پنل دکمه ای برای مدیریت عملیات های ممبر فیک، بازدید و پروفایل عمل می کند.
# توجه: تمام سشن استرینگ های فیک از فایل 'aaaaaaaaaa_sessions_raw.txt' خوانده می شود.
# هشدار: مقادیر API_ID, API_HASH, ADMIN_ID و BOT_TOKEN به صورت مستقیم در این کد تعریف شده‌اند.

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import os
import random
import asyncio

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

async def run_session_command(session_string, command, channel_username, avatar_folder=None):
    """یک عملیات مشخص را روی یک سشن فیک اجرا می کند."""
    
    # Pyrogram برای نام سشن به یک نام یونیک نیاز دارد، از یک UUID استفاده می کنیم.
    # به خاطر اینکه سشن استرینگ در Pyrogram خود شامل اطلاعات احراز هویت است، ما فقط باید آن را وارد کنیم.
    # نام سشن می تواند هر چیزی باشد.
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
            "⚠️ **شبیه‌ساز بازدید/ری‌اکشن فعال شد.**\n\n"
            "برای افزودن بازدید یا ری‌اکشن، باید دستور را مستقیماً ارسال کنید. (فعلا فقط شبیه سازی بازدید ساده فعال است)\n"
            "دستور بازدید: `/boost <تعداد> <لینک_پست>`\n"
            "مثال: `/boost 10000 https://t.me/c/12345/67`\n\n"
            "**توجه:** این بخش نیاز به پیاده‌سازی پیچیده‌تر با استفاده از متدهای API تلگرام برای ری‌اکشن و بازدید واقعی دارد.",
            reply_markup=main_menu()
        )
        
    # --- تنظیم کانال هدف ---
    elif data == "set_channel":
        await callback_query.message.edit_text(
            "لطفاً یوزرنیم کانال هدف جدید را به صورت زیر ارسال کنید:\n"
            "`/setchannel @YourNewChannel`",
            reply_markup=main_menu()
        )
        
# --- هندلر دستور /boost (شبیه ساز) ---
@bot_app.on_message(filters.command("boost") & filters.user(ADMIN_ID))
async def boost_command(client, message):
    try:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            return await message.reply_text("فرمت صحیح: `/boost <تعداد> <لینک_پست>`")
        
        count = int(command_parts[1])
        post_link = command_parts[2]
        
        await message.reply_text(
            f"🚀 **شبیه‌سازی بازدید/ری‌اکشن آغاز شد:**\n\n"
            f"تعداد: {count} \n"
            f"لینک پست: `{post_link}`\n\n"
            f"این شبیه‌سازی در حال حاضر یک فرآیند نمایشی است و نیاز به پیاده‌سازی کامل متدهای API تلگرام برای ری‌اکشن و بازدید واقعی دارد.",
            reply_markup=main_menu()
        )

    except ValueError:
        await message.reply_text("لطفاً یک عدد صحیح برای تعداد وارد کنید.")
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


if __name__ == "__main__":
    print("ربات مدیریت در حال اجرا است. برای استفاده، به ربات خود در تلگرام پیام /start را ارسال کنید.")
    print(f"API ID: {API_ID}, ADMIN ID: {ADMIN_ID}")
    bot_app.run()
