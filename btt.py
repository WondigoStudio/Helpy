import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import sqlite3
import asyncio

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Подключение к базе данных
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

# --- Вспомогательные функции ---
async def update_user(user_id, chat_id):
    c.execute("SELECT * FROM users WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, chat_id, warns, mutes) VALUES (?, ?, 0, 0)", (user_id, chat_id))
        conn.commit()

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

async def unmute_later(context: ContextTypes.DEFAULT_TYPE, chat_id, user_id, until):
    delay = (until - datetime.utcnow()).total_seconds()
    await asyncio.sleep(delay)
    permissions = ChatPermissions(can_send_messages=True)
    await context.bot.restrict_chat_member(chat_id, user_id, permissions)
    c.execute("UPDATE users SET mute_until=NULL WHERE user_id=? AND chat_id=?", (user_id, chat_id))
    conn.commit()

# --- Команды ---
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
    permissions = ChatPermissions(can_send_messages=True)
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

async def rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Используйте /rep в ответ на сообщение пользователя.")
        return

    user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    await update_user(user.id, chat_id)
    c.execute("SELECT warns, mutes, mute_until FROM users WHERE user_id=? AND chat_id=?", (user.id, chat_id))
    warns, mutes, mute_until = c.fetchone()
    mute_status = "Мут до " + mute_until if mute_until else "Не в муте"
    await update.message.reply_text(
        f"Статистика {user.mention_html()}\nПредупреждений: {warns}\nМутов: {mutes}\nСостояние: {mute_status}",
        parse_mode='HTML')

async def admininfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_text = (
        "🛠 <b>Команды администратора:</b>\n\n"
        "⚠️ <b>/warn</b> — выдать предупреждение. После 2-х — мут на 24 часа.\n"
        "♻️ <b>/unwarn</b> — убрать предупреждение.\n"
        "🔇 <b>/mut 5m</b> — замутить пользователя на указанное время (например, 5m, 2h).\n"
        "🔊 <b>/unmut</b> — снять мут досрочно.\n"
        "🔨 <b>/ban</b> — забанить (удалить) пользователя из группы.\n"
        "📊 <b>/rep</b> — посмотреть репутацию пользователя (преды и муты).\n"
        "📋 <b>/admininfo</b> — список всех админ-команд.\n\n"
        "⏳ <i>Автоматически:</i>\n"
        "— После двух /warn пользователь мутится на 24ч.\n"
        "— После 24ч мута — размут и обнуление предупреждений.\n"
    )
    await update.message.reply_text(commands_text, parse_mode="HTML")

# --- Основная функция ---
async def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("mut", mut))
    app.add_handler(CommandHandler("unmut", unmut))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("rep", rep))
    app.add_handler(CommandHandler("admininfo", admininfo))

    print("✅ Бот запущен...")
    await app.run_polling()

# Запуск
if __name__ == "__main__":
    asyncio.run(main())
