import json
import os
import asyncio
import random
import string
from time import time
from collections import deque
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ---------------- CONFIG ----------------
BOT_TOKEN = 
ADMINS_FILE = "admins.json"
SCRIPTS_FILE = "scripts.json"
DEFAULT_OWNER_ID = 2080989762

MESSAGE_LIMIT = 5
WINDOW_SECONDS = 10

# ---------------- ADMIN STORAGE ----------------
def load_admins():
    if not os.path.exists(ADMINS_FILE):
        data = {"owner": DEFAULT_OWNER_ID, "admins": []}
        save_admins(data)
        return data
    try:
        with open(ADMINS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"owner": DEFAULT_OWNER_ID, "admins": []}

def save_admins(admins):
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)

ADMINS = load_admins()
def is_owner(user_id: int) -> bool:
    return user_id == ADMINS.get("owner")
def is_admin(user_id: int) -> bool:
    return is_owner(user_id) or user_id in ADMINS.get("admins", [])

# ---------------- SCRIPT STORAGE ----------------
def load_scripts():
    if not os.path.exists(SCRIPTS_FILE):
        save_scripts({"scripts": []})
        return {"scripts": []}
    try:
        with open(SCRIPTS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"scripts": []}

def save_scripts(data):
    with open(SCRIPTS_FILE, "w") as f:
        json.dump(data, f)

SCRIPTS = load_scripts()
def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
def get_script_by_code(code):
    for s in SCRIPTS.get("scripts", []):
        if s["id"] == code:
            return s
    return None

# ---------------- RATE LIMIT ----------------
_anti_ddos = {}
_ddos_lock = asyncio.Lock()
async def check_rate_limit(user_id: int):
    if is_owner(user_id):
        return True, 0.0
    now = time()
    async with _ddos_lock:
        dq = _anti_ddos.get(user_id)
        if dq is None:
            dq = deque()
            _anti_ddos[user_id] = dq
        while dq and (now - dq[0]) > WINDOW_SECONDS:
            dq.popleft()
        if len(dq) >= MESSAGE_LIMIT:
            retry_after = WINDOW_SECONDS - (now - dq[0])
            return False, max(0.0, retry_after)
        else:
            dq.append(now)
            return True, 0.0

# ---------------- UI ----------------
def back_button_markup(to="script"):
    cb = "script_panel" if to=="script" else "back_admin"
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=cb)]])

def admin_main_markup(is_owner_flag: bool):
    kb = []
    if is_owner_flag:
        kb.append([InlineKeyboardButton("➕ Добавить админ", callback_data="add_admin")])
        kb.append([InlineKeyboardButton("➖ Удалить админ", callback_data="remove_admin")])
    kb.append([InlineKeyboardButton("📋 Список админов", callback_data="list_admins")])
    kb.append([InlineKeyboardButton("📜 Скрипты", callback_data="script_panel")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_admin")])
    return InlineKeyboardMarkup(kb)

def script_main_markup(user_id: int):
    kb = []
    for script in SCRIPTS.get("scripts", []):
        kb.append([InlineKeyboardButton(script["id"], callback_data=f"script_{script['id']}")])
    kb.append([InlineKeyboardButton("➕ Добавить скрипт", callback_data="add_script")])
    if is_owner(user_id):
        kb.append([InlineKeyboardButton("➖ Удалить скрипт", callback_data="remove_script")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="back_admin")])
    return InlineKeyboardMarkup(kb) if kb else None

def script_action_markup(user_id: int, script):
    kb = [[InlineKeyboardButton("🔗 Ссылка", callback_data=f"link_{script['id']}")]]
    if is_owner(user_id) or user_id == script["creator_id"]:
        kb.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{script['id']}")])
    if is_owner(user_id):
        kb.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{script['id']}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="script_panel")])
    return InlineKeyboardMarkup(kb)

# ---------------- SEND SCRIPT ----------------
async def send_script_to_user(update: Update, code: str):
    script = get_script_by_code(code)
    if not script:
        await update.message.reply_text("⚠️ Скрипт не найден")
        return
    text = script.get("text", "")
    photo = script.get("photo", None)
    if photo:
        await update.message.reply_photo(photo=photo, caption=text if text else " ", parse_mode="HTML")
    else:
        await update.message.reply_html(text if text else " ")

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    allowed, retry_after = await check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⚠️ Слишком много запросов. Попробуйте через {int(retry_after)} сек.")
        return
    args = context.args
    if args:
        code = args[0]
        await send_script_to_user(update, code)
        return
    if not is_admin(user_id):
        return await update.message.reply_text("⛔️ Доступ закрыт! Только по ссылке.")
    rank = "👑 Создатель" if is_owner(user_id) else "🛠️ Админ"
    username = user.first_name or (user.username and f"@{user.username}") or "друг"
    await update.message.reply_text(f"❤️ Привет, {username}! ({rank})\nБот приватный 💚")

async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed, retry_after = await check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⚠️ Слишком много запросов. Подождите {int(retry_after)} сек.")
        return
    if not is_admin(user_id):
        return await update.message.reply_text("⛔️ Вы не админ.")
    await update.message.reply_text("🔧 Админ-панель", reply_markup=admin_main_markup(is_owner(user_id)))

async def script_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    allowed, retry_after = await check_rate_limit(user_id)
    if not allowed:
        await update.message.reply_text(f"⚠️ Слишком много запросов. Подождите {int(retry_after)} сек.")
        return
    if not is_admin(user_id):
        return await update.message.reply_text("⛔️ Вы не админ.")
    kb = script_main_markup(user_id)
    await update.message.reply_text("📜 Скрипты:\nВыберите скрипт или действие:", reply_markup=kb)

# ---------------- CALLBACK HANDLER ----------------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    data = query.data
    if not is_admin(user_id):
        await query.edit_message_text("⛔️ Только админ имеет доступ.")
        return

    if data == "script_panel":
        kb = script_main_markup(user_id)
        await query.edit_message_text("📜 Скрипты:\nВыберите скрипт или действие:", reply_markup=kb)
        return
    if data == "back_admin":
        await query.edit_message_text("🔧 Админ-панель", reply_markup=admin_main_markup(is_owner(user_id)))
        return
    if data.startswith("script_"):
        code = data.split("_",1)[1]
        script = get_script_by_code(code)
        if script:
            kb = script_action_markup(user_id, script)
            await query.edit_message_text(f"📄 Скрипт {code}", reply_markup=kb)
        return
    if data.startswith("link_"):
        code = data.split("_",1)[1]
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={code}"
        await query.edit_message_text(f"Ссылка для пользователей:\n{link}")
        return
    if data.startswith("edit_"):
        code = data.split("_",1)[1]
        script = get_script_by_code(code)
        if script and (is_owner(user_id) or user_id == script["creator_id"]):
            await query.edit_message_text("✍️ Отправьте новый текст и/или фото для скрипта:")
            context.user_data["editing_script"] = code
        return
    if data.startswith("delete_") and is_owner(user_id):
        code = data.split("_",1)[1]
        script = get_script_by_code(code)
        if script:
            SCRIPTS["scripts"].remove(script)
            save_scripts(SCRIPTS)
            await query.edit_message_text(f"🗑 Скрипт {code} удалён")
        return
    if data == "add_script":
        await query.edit_message_text("✍️ Отправьте текст и/или фото для нового скрипта:", reply_markup=back_button_markup())
        context.user_data["awaiting_script"] = "add"
        return

# ---------------- MESSAGE HANDLER ----------------
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    text = update.message.text_html if update.message.text else ""
    photo_id = update.message.photo[-1].file_id if update.message.photo else None

    # Добавление скрипта
    if context.user_data.get("awaiting_script") == "add":
        code = generate_code()
        SCRIPTS.setdefault("scripts", []).append({
            "id": code,
            "text": text,
            "photo": photo_id,
            "creator_id": user_id
        })
        save_scripts(SCRIPTS)
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={code}"
        await update.message.reply_text(f"✅ Скрипт создан!\nСсылка для пользователей:\n{link}")
        context.user_data["awaiting_script"] = None
        return

    # Редактирование скрипта
    editing_code = context.user_data.get("editing_script")
    if editing_code:
        script = get_script_by_code(editing_code)
        if script and (is_owner(user_id) or user_id == script["creator_id"]):
            script["text"] = text
            script["photo"] = photo_id
            save_scripts(SCRIPTS)
            await update.message.reply_text(f"✏️ Скрипт {editing_code} обновлён")
            context.user_data["editing_script"] = None

# ---------------- RUN BOT ----------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel_cmd))
    app.add_handler(CommandHandler("script", script_panel_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))
    print("🤖 Бот запущен.")
    app.run_polling()

if __name__ == "__main__":
    main()

