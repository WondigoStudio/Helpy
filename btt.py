import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from aiohttp import web
import re
from flask import Flask
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
  
async def start_web_app():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 5000)
    await site.start()

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("moderation.db", check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER,
        chat_id INTEGER,
        warns INTEGER DEFAULT 0,
        mutes INTEGER DEFAULT 0,
        mute_until TEXT
    )
''')
conn.commit()
async def handle(request):
    return web.Response(text="Бот работает!")


    
def parse_duration(duration: str):
    try:
        if duration.endswith("m"):
            return int(duration[:-1]) * 60
        elif duration.endswith("h"):
            return int(duration[:-1]) * 3600
        elif duration.endswith("d"):
            return int(duration[:-1]) * 86400
    except:
        return None
async def update_user(user_id, chat_id):
    c.execute("SELECT * FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
        conn.commit()

async def unmute_later(context, chat_id, user_id, until):
    delay = (until - datetime.utcnow()).total_seconds()
    await asyncio.sleep(delay)
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True
    )

    await context.bot.restrict_chat_member(chat_id, user_id, permissions)
    c.execute("UPDATE users SET mute_until=NULL WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    conn.commit()

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Используйте /warn в ответ на сообщение пользователя.")
        return

    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    await update_user(user.id, chat_id)

    c.execute("UPDATE users SET warns = warns + 1 WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    conn.commit()

    c.execute("SELECT warns FROM users WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    warns = c.fetchone()[0]
    await update.message.reply_text(f"Предупреждение {user.mention_html()} | Всего: {warns}", parse_mode='HTML')

    if warns >= 2:
        until = datetime.utcnow() + timedelta(hours=24)
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id, user.id, permissions, until_date=until)
        c.execute("UPDATE users SET warns=0, mutes=mutes+1, mute_until=? WHERE user_id=? AND chat_id=?", (until.isoformat(), user.id, chat_id))
        conn.commit()
        await update.message.reply_text(f"{user.mention_html()} замучен на 24 часа за 2 предупреждения.", parse_mode='HTML')
        asyncio.create_task(unmute_later(context, chat_id, user.id, until))
 

async def mut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Используйте /mut в ответ на сообщение: /mut 5m")
        return
    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    duration = context.args[0]
 
    seconds = parse_duration(duration)
    if seconds is None:
        await update.message.reply_text("Неверный формат времени. Примеры: 5m, 2h, 1d")
        return

    until = datetime.utcnow() + timedelta(seconds=seconds)
    permissions = ChatPermissions(can_send_messages=False)
    await context.bot.restrict_chat_member(chat_id, user.id, permissions, until_date=until)
    await update_user(user.id, chat_id)
    c.execute("UPDATE users SET mutes = mutes + 1, mute_until=? WHERE user_id=? AND chat_id=?", (until.isoformat(), user.id, chat_id))
    conn.commit()
    await update.message.reply_text(f"{user.mention_html()} замучен на {duration}.", parse_mode='HTML')
    asyncio.create_task(unmute_later(context, chat_id, user.id, until))

async def unmut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Используйте /unmut в ответ на сообщение пользователя.")
        return

    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True
    )

    await context.bot.restrict_chat_member(chat_id, user.id, permissions)
    c.execute("UPDATE users SET mute_until=NULL WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    conn.commit()
    await update.message.reply_text(f"{user.mention_html()} размучен.", parse_mode='HTML')

async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Используйте /unwarn в ответ на сообщение пользователя.")
        return

    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    c.execute("SELECT warns FROM users WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    warns = c.fetchone()
    if warns and warns[0] > 0:
        c.execute("UPDATE users SET warns = warns - 1 WHERE user_id=? AND chat_id=?", (user.id, chat_id))
        conn.commit()
        await update.message.reply_text(f"Предупреждение снято. Осталось: {warns[0]-1}")
    else:
        await update.message.reply_text("У пользователя нет предупреждений.")

from telegram import User
from telegram.ext import ContextTypes
import re

async def rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # 1. Получить пользователя из ответа или аргументов
    user = None

    # Если это ответ на сообщение — используем его
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user

    # Иначе пробуем извлечь @username или user_id из аргумента команды
    elif context.args:
        arg = context.args[0]

        # Попробуем получить по user_id
        if arg.isdigit():
            try:
                user = await context.bot.get_chat_member(chat_id, int(arg))
                user = user.user
            except:
                await update.message.reply_text("Не удалось найти пользователя по ID.")
                return

        # Попробуем получить по @username
        elif arg.startswith("@"):
            try:
                user = await context.bot.get_chat(arg)
                if not isinstance(user, User):
                    await update.message.reply_text("Пользователь не найден или это не личный аккаунт.")
                    return
            except:
                await update.message.reply_text("Пользователь с таким юзернеймом не найден.")
                return
        else:
            await update.message.reply_text("Неверный формат. Укажите ID или @username.")
            return
    else:
        await update.message.reply_text("Используйте /rep в ответ на сообщение или укажите @username/ID.")
        return

    # Обновление и получение данных
    await update_user(user.id, chat_id)
    c.execute("SELECT warns, mutes, mute_until FROM users WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    result = c.fetchone()
    if not result:
        await update.message.reply_text("Нет информации о пользователе.")
        return

    warns, mutes, mute_until = result
    mute_status = f"Мут до {mute_until}" if mute_until else "Не в муте"

    await update.message.reply_text(
        f"Статистика {user.mention_html()}\n"
        f"Предупреждений: {warns}\n"
        f"Мутов: {mutes}\n"
        f"Состояние: {mute_status}",
        parse_mode='HTML'
    )

    
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Эта команда должна быть ответом на сообщение пользователя.")
        return

    user_to_ban = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id

    try:
        await context.bot.ban_chat_member(chat_id, user_to_ban.id)
        await update.message.delete()
        await update.message.reply_text(f"🚫 Пользователь {user_to_ban.mention_html()} был забанен.", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось забанить пользователя. Причина: {e}")
        
async def admininfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_text = (
        "🛠 <b>Команды администратора:</b>\n\n"
        "⚠️ <b>/warn @user</b> — выдать предупреждение. После 2-х — мут на 24 часа.\n"
        "♻️ <b>/unwarn @user</b> — убрать предупреждение.\n"
        "🔇 <b>/mut @user 5m</b> — замутить пользователя на указанное время (например, 5m, 2h).\n"
        "🔊 <b>/unmut @user</b> — снять мут досрочно.\n"
        "🔨 <b>/ban @user</b> — забанить (удалить) пользователя из группы.\n"
        "📊 <b>/rep @user</b> — посмотреть репутацию пользователя (преды и муты).\n"
        "📋 <b>/admininfo</b> — список всех админ-команд.\n\n"
        "⏳ <i>Автоматически:</i>\n"
        "— После двух /warn пользователь мутится на 24ч.\n"
        "— После 24ч мута — размут и обнуление предупреждений.\n"
    )
    await update.message.reply_text(commands_text, parse_mode="HTML")

async def main():
    await start_web_app()
    app = ApplicationBuilder().token("8093659364:AAGuO6e9QSzTfGlLOmgr57NJqW3a7yrq4Gg").build()
    
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("mut", mut))
    app.add_handler(CommandHandler("unmut", unmut))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("rep", rep))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("admininfo", admininfo))

    print("Бот запущен...")
    asyncio.run(main())
    
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    # Без проверки get_running_loop, просто запускаем
    asyncio.run(main())

