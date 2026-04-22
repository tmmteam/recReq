import asyncio
import sqlite3
import os
import logging
import random
import re
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pyrogram import Client, filters
from pyrogram.errors import SessionPasswordNeeded, UserAlreadyParticipant, FloodWait
from pyromod import listen

logging.getLogger("pyrogram").setLevel(logging.ERROR)

# --- CONFIG ---
API_ID = 20247726
API_HASH = "2a2654fa036e1ec6b98216d85d9fa38c"
BOT_TOKEN = "8633171716:AAFZ6tPmfjoDeaVZvkHtygNyPBsVVO77wss"
OWNER_ID = 1161241513  # 🔥 APNA TELEGRAM USER ID DALO

# --- SESSION CLEAN ---
if os.path.exists("MasterBot.session"):
    os.remove("MasterBot.session")

bot = Client("MasterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE ---
db = sqlite3.connect("accounts.db", check_same_thread=False)
cursor = db.cursor()

# Users table (accounts)
cursor.execute("CREATE TABLE IF NOT EXISTS users (phone TEXT PRIMARY KEY, session TEXT, name TEXT)")
# Access table (user permissions)
cursor.execute("CREATE TABLE IF NOT EXISTS access (user_id INTEGER PRIMARY KEY, expiry_date TEXT)")
db.commit()

def get_all_accounts():
    cursor.execute("SELECT session FROM users")
    return [x[0] for x in cursor.fetchall()]

def delete_account(session):
    cursor.execute("DELETE FROM users WHERE session=?", (session,))
    db.commit()

# --- ACCESS MANAGEMENT ---
def check_access(user_id):
    """Check if user has access to premium features"""
    cursor.execute("SELECT expiry_date FROM access WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        return False
    
    expiry_date = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry_date:
        # Access expired, remove from database
        cursor.execute("DELETE FROM access WHERE user_id=?", (user_id,))
        db.commit()
        return False
    
    return True

def give_access(user_id, days):
    """Give access to user for specified days"""
    expiry_date = datetime.now() + timedelta(days=days)
    expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("INSERT OR REPLACE INTO access VALUES (?, ?)", (user_id, expiry_str))
    db.commit()
    return expiry_date

def remove_access(user_id):
    """Remove user's access"""
    cursor.execute("DELETE FROM access WHERE user_id=?", (user_id,))
    db.commit()

def get_access_info(user_id):
    """Get user's access information"""
    cursor.execute("SELECT expiry_date FROM access WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if result:
        expiry = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        remaining = (expiry - datetime.now()).days
        return expiry, remaining
    return None, None

# --- OWNER COMMANDS ---
@bot.on_message(filters.command("access") & filters.user(OWNER_ID))
async def give_user_access(client, message):
    """Give access to a user (Owner only)"""
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ **Usage:** `/access <days> <user_id>`\nExample: `/access 2 123456789`")
            return
        
        days = int(parts[1])
        user_id = int(parts[2])
        
        expiry = give_access(user_id, days)
        
        # Try to notify the user
        try:
            await bot.send_message(
                user_id,
                f"✅ **Access Granted!**\n\n"
                f"🎉 You have been given access for **{days} days**!\n"
                f"⏰ Expires on: `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
                f"📌 **Features available:**\n"
                f"• REACTION - Auto react on posts\n"
                f"• REQUEST - Auto join request links\n"
                f"• /add - Add accounts"
            )
        except:
            pass
        
        await message.reply(f"✅ Access given to `{user_id}` for **{days} days**!\nExpires: `{expiry}`")
        
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@bot.on_message(filters.command("removeaccess") & filters.user(OWNER_ID))
async def remove_user_access(client, message):
    """Remove user's access (Owner only)"""
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.reply("❌ **Usage:** `/removeaccess <user_id>`")
            return
        
        user_id = int(parts[1])
        remove_access(user_id)
        
        await message.reply(f"✅ Access removed for user `{user_id}`")
        
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@bot.on_message(filters.command("users") & filters.user(OWNER_ID))
async def list_users(client, message):
    """List all users with access (Owner only)"""
    cursor.execute("SELECT user_id, expiry_date FROM access ORDER BY expiry_date DESC")
    users = cursor.fetchall()
    
    if not users:
        await message.reply("📭 No users have access right now.")
        return
    
    text = "**👥 Users with Access:**\n\n"
    for user_id, expiry in users:
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
        remaining = (expiry_date - datetime.now()).days
        text += f"• `{user_id}` - Expires in {remaining} days\n"
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_accounts = cursor.fetchone()[0]
    text += f"\n📱 Total accounts in bot: {total_accounts}"
    
    await message.reply(text)

@bot.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def bot_stats(client, message):
    """Show bot statistics (Owner only)"""
    cursor.execute("SELECT COUNT(*) FROM users")
    total_accounts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM access")
    total_users = cursor.fetchone()[0]
    
    await message.reply(
        f"**📊 Bot Statistics:**\n\n"
        f"👥 Users with access: `{total_users}`\n"
        f"📱 Total accounts: `{total_accounts}`\n"
        f"👑 Owner: `{OWNER_ID}`\n\n"
        f"⚙️ Features: REACTION, REQUEST"
    )

# --- ADD ACCOUNT (Public) ---
@bot.on_message(filters.command("add"))
async def add(client, message):
    try:
        phone = (await bot.ask(message.chat.id, "📱 **Number (+91...):**")).text

        temp = Client("temp", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await temp.connect()

        code = await temp.send_code(phone)
        otp = (await bot.ask(message.chat.id, "📩 **OTP:**")).text

        try:
            await temp.sign_in(phone, code.phone_code_hash, otp)
        except SessionPasswordNeeded:
            pw = await bot.ask(message.chat.id, "🔐 **2FA Password:**")
            await temp.check_password(pw.text)

        session = await temp.export_session_string()
        me = await temp.get_me()

        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (phone, session, me.first_name))
        db.commit()

        await temp.disconnect()
        await message.reply(f"✅ **Added:** {me.first_name}\n📱 Phone: `{phone}`")

    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

# --- START COMMAND (With Access Check) ---
@bot.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    
    # Check if user has access
    has_access = check_access(user_id)
    
    if user_id == OWNER_ID:
        # Owner sees everything
        kb = ReplyKeyboardMarkup(
            [
                ["REACTION", "REQUEST"],
                ["/add", "/stats"],
                ["/users", "/removeaccess"]
            ],
            resize_keyboard=True
        )
        await message.reply(
            "👑 **Owner Mode Active!**\n\n"
            "📌 **Commands:**\n"
            "• REACTION - Auto react on posts\n"
            "• REQUEST - Auto join requests\n"
            "• /add - Add new account\n"
            "• /users - List users with access\n"
            "• /stats - Bot statistics\n"
            "• /removeaccess - Remove user access",
            reply_markup=kb
        )
        
    elif has_access:
        # Premium user sees all features
        expiry, remaining = get_access_info(user_id)
        kb = ReplyKeyboardMarkup(
            [
                ["REACTION", "REQUEST"],
                ["/add"]
            ],
            resize_keyboard=True
        )
        await message.reply(
            f"✅ **Premium Access Active!**\n\n"
            f"⏰ Access expires in: **{remaining} days**\n\n"
            f"📌 **Available Commands:**\n"
            f"• REACTION - Auto react on posts\n"
            f"• REQUEST - Auto join requests\n"
            f"• /add - Add new account",
            reply_markup=kb
        )
    else:
        # Normal user - only /add
        kb = ReplyKeyboardMarkup(
            [["/add"]],
            resize_keyboard=True
        )
        await message.reply(
            "⚠️ **Limited Access Mode**\n\n"
            "You only have permission to add accounts.\n\n"
            "Contact owner for premium access to use:\n"
            "• REACTION\n"
            "• REQUEST",
            reply_markup=kb
        )

# --- FEATURE CHECK DECORATOR ---
def require_access(func):
    """Decorator to check if user has access"""
    async def wrapper(client, message):
        user_id = message.from_user.id
        
        # Owner always has access
        if user_id == OWNER_ID:
            return await func(client, message)
        
        # Check if user has access
        if check_access(user_id):
            return await func(client, message)
        else:
            await message.reply(
                "❌ **Access Denied!**\n\n"
                "You don't have permission to use this feature.\n"
                "Contact owner to get access.\n\n"
                "✅ You can still use `/add` to add accounts."
            )
            return None
    return wrapper

# ==================== REACTION FEATURE ====================
@bot.on_message(filters.regex("^REACTION$"))
@require_access
async def reaction_feature(client, message):
    sessions = get_all_accounts()
    
    if not sessions:
        return await message.reply("❌ Koi account nahi hai! Pehle /add use karo.")
    
    # Step 1: Get channel invite link
    ch_link_msg = await bot.ask(message.chat.id, "🔗 **Channel invite link bhejo:**")
    ch_link = ch_link_msg.text.strip()
    
    # Step 2: Get post link
    post_link_msg = await bot.ask(message.chat.id, "📝 **Post link bhejo jispe reaction dena hai:**")
    post_link = post_link_msg.text.strip()
    
    # Extract message ID
    try:
        msg_id = int(post_link.split("/")[-1])
    except:
        return await message.reply("❌ Invalid post link!")
    
    # Step 3: Ask which reaction to give
    kb = ReplyKeyboardMarkup(
        [["👍🏻 LIKE", "❤️ LOVE", "🔥 FIRE"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.reply("🎯 **Kaunsa reaction dena hai?**", reply_markup=kb)
    
    try:
        reaction_choice = await bot.ask(message.chat.id, "Choose reaction:", timeout=30)
        reaction_text = reaction_choice.text
    except:
        return await message.reply("❌ Timeout! Try again.")
    
    # Map reaction to emoji
    reaction_map = {
        "👍🏻 LIKE": "👍",
        "❤️ LOVE": "❤️",
        "🔥 FIRE": "🔥"
    }
    
    reaction_emoji = reaction_map.get(reaction_text, "👍")
    
    await message.reply(f"✅ Reaction mode active: **{reaction_emoji}**\n🔄 Processing all accounts...")
    
    # Process all accounts
    success_count = 0
    failed_count = 0
    
    for i, session in enumerate(sessions, start=1):
        acc = None
        try:
            acc = Client(f"user{i}", session_string=session, api_id=API_ID, api_hash=API_HASH)
            await acc.start()
            print(f"\n🔹 Account {i} - Processing reaction...")
            
            # Join channel
            try:
                await acc.join_chat(ch_link)
                print(f"✅ Joined channel")
            except UserAlreadyParticipant:
                print(f"⚠️ Already in channel")
            except Exception as e:
                print(f"❌ Join error: {e}")
                failed_count += 1
                continue
            
            # Get chat
            try:
                chat = await acc.get_chat(ch_link)
                chat_id = chat.id
            except Exception as e:
                print(f"❌ Chat resolve error: {e}")
                failed_count += 1
                continue
            
            # Add reaction to message
            try:
                await acc.send_reaction(
                    chat_id=chat_id,
                    message_id=msg_id,
                    emoji=reaction_emoji
                )
                print(f"✅ Reacted with {reaction_emoji}")
                success_count += 1
                await asyncio.sleep(0.5)
                
            except FloodWait as e:
                print(f"⚠️ Flood wait {e.value}s")
                await asyncio.sleep(e.value)
                try:
                    await acc.send_reaction(chat_id, msg_id, reaction_emoji)
                    success_count += 1
                except:
                    failed_count += 1
                    
            except Exception as e:
                print(f"❌ Reaction error: {e}")
                failed_count += 1
                
        except Exception as e:
            print(f"❌ Account error: {e}")
            failed_count += 1
        finally:
            if acc:
                try:
                    await acc.stop()
                except:
                    pass
        
        await asyncio.sleep(1)
    
    result = f"""
✅ **Reaction Task Complete!**

📊 **Results:**
• ✅ Success: {success_count} accounts
• ❌ Failed: {failed_count} accounts
• 📱 Total: {len(sessions)} accounts

🎯 **Reaction:** {reaction_emoji}
📝 **Post:** {post_link}
"""
    await message.reply(result)


# ==================== REQUEST FEATURE ====================
@bot.on_message(filters.regex("^REQUEST$"))
@require_access
async def request_feature(client, message):
    sessions = get_all_accounts()
    
    if not sessions:
        return await message.reply("❌ Koi account nahi hai! Pehle /add use karo.")
    
    # Get request link
    request_link_msg = await bot.ask(
        message.chat.id, 
        "🔗 **Request link bhejo:**\n(Example: https://t.me/+xxxxxxx)"
    )
    request_link = request_link_msg.text.strip()
    
    await message.reply("✅ **Processing join requests...**\n⏳ This may take a few minutes...")
    
    success_count = 0
    failed_count = 0
    
    for i, session in enumerate(sessions, start=1):
        acc = None
        try:
            acc = Client(f"user{i}", session_string=session, api_id=API_ID, api_hash=API_HASH)
            await acc.start()
            print(f"\n🔹 Account {i} - Sending join request...")
            
            try:
                # Try to join with request
                await acc.join_chat(request_link)
                print(f"✅ Join request sent")
                success_count += 1
                
            except UserAlreadyParticipant:
                print(f"⚠️ Already member")
                success_count += 1
                
            except Exception as e:
                print(f"❌ Request error: {e}")
                failed_count += 1
                
        except Exception as e:
            print(f"❌ Account error: {e}")
            failed_count += 1
        finally:
            if acc:
                try:
                    await acc.stop()
                except:
                    pass
        
        await asyncio.sleep(2)
    
    result = f"""
✅ **Request Task Complete!**

📊 **Results:**
• ✅ Success: {success_count} accounts
• ❌ Failed: {failed_count} accounts
• 📱 Total: {len(sessions)} accounts

🔗 **Link:** {request_link}
"""
    await message.reply(result)


print("🚀 Bot Started!")
print(f"👑 Owner ID: {OWNER_ID}")
print("📌 Features: REACTION, REQUEST, /add")
bot.run()
