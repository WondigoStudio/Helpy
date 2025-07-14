import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler


# Функция обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я Helpy бот.")


# Функция обработки команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши /start чтобы начать.")


# Главная асинхронная функция
async def main():
    # Инициализируем приложение с токеном
    app = ApplicationBuilder().token("8093659364:AAEWyrlmCdb5xFqBvlNE8HWBtXl0n9qdpig").build()

    # Регистрируем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Запускаем бота
    await app.run_polling()


# Точка входа
if __name__ == "__main__":
    asyncio.run(main())
