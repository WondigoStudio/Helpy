import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler

async def start(update, context):
    await update.message.reply_text("Привет!")

async def main():
    app = ApplicationBuilder().token("8093659364:AAEWyrlmCdb5xFqBvlNE8HWBtXl0n9qdpig").build()

    app.add_handler(CommandHandler("start", start))

    # Запускаем polling в уже существующем event loop
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Ждём завершения
    await app.updater.wait()
    await app.stop()
    await app.shutdown()

# Вместо asyncio.run()
if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError as e:
        print(f"RuntimeError: {e}")
