from telegram.ext import ApplicationBuilder, CommandHandler

async def start(update, context):
    await update.message.reply_text("Привет!")

async def main():
    app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()
    
    app.add_handler(CommandHandler("start", start))
    
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
