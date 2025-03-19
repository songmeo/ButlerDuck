#!/usr/bin/env python3
# Copyright Song Meo <songmeo@pm.me>

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any
import psycopg2
import os
from dotenv import load_dotenv
import telegram
from telegram import Update, error
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    ExtBot,
    CommandHandler,
)
from handler import photo_handler, store_message, generate_response, help_command
from handler import BOT_NAME, BOT_USER_ID
from logger import logger

load_dotenv()

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]
DB_HOST = os.environ["DB_HOST"]
TOKEN = os.environ["TOKEN"]


async def generate_response_loop(con: psycopg2.connect) -> None:
    while True:
        cur = con.cursor()
        cur.execute("SELECT chat_id FROM user_message")
        chat_ids = cur.fetchall()
        chat_ids = [row[0] for row in chat_ids]
        for chat_id in chat_ids:
            cur.execute(
                """
                SELECT 
                    user_id, message_id, created_at 
                FROM user_message 
                WHERE 
                    chat_id = %s
                ORDER BY 
                    created_at DESC 
                LIMIT 1;
                """,
                (chat_id,),
            )
            last_message = cur.fetchone()
            if last_message:
                user_id, message_id, created_at = last_message
                if user_id != BOT_USER_ID:
                    if (datetime.now(timezone.utc) - created_at) >= timedelta(seconds=5):
                        response = await generate_response(chat_id=chat_id, con=con)
                        bot = telegram.Bot(token=TOKEN)
                        await bot.send_message(chat_id=chat_id, text=response, reply_to_message_id=message_id)

        await asyncio.sleep(1)


def main() -> None:
    application = Application.builder().token(TOKEN).build()

    for _ in range(5):
        try:
            con = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=5432,
            )
            cur = con.cursor()
            logger.info("Connection successful!")
            break  # success! no need to repeat
        except psycopg2.OperationalError as e:
            logger.error("Error while connecting to the database:", e)
            time.sleep(5)
    else:
        logger.error("Can't connect to the database. Abort.")
        exit(1)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tg_user (
            id SERIAL PRIMARY KEY,  -- SERIAL handles auto-incrementing
            tg_id BIGINT NOT NULL UNIQUE,
            name TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO tg_user (tg_id, name)
        VALUES (%s, %s)
        ON CONFLICT (tg_id) DO NOTHING
        """,
        (0, BOT_NAME),
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_image (
            id SERIAL PRIMARY KEY,
            image_path TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_message (
            id SERIAL PRIMARY KEY,  -- SERIAL handles auto-incrementing
            chat_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            message TEXT NOT NULL,
            user_image_id BIGINT NULL,            
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES tg_user(tg_id) ON DELETE CASCADE,
            CONSTRAINT fk_user_image FOREIGN KEY (user_image_id) REFERENCES user_image(id) ON DELETE SET NULL
        )
        """
    )
    con.commit()

    async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        _ = context
        if update.message and update.message.sticker:
            sticker = update.message.sticker
            await update.message.reply_text(f"Nice sticker! It's {sticker.emoji} emoji.")
        else:
            logger.error(f"This update doesn't have any message or sticker.")
            raise Exception("No photo sent.")

    async def error_handler(
        update: object, context: CallbackContext[ExtBot[None], dict[Any, Any], dict[Any, Any], dict[Any, Any]]
    ) -> None:
        if isinstance(context.error, error.Conflict):
            logger.error("Conflict error detected: Another bot instance is likely running.")
            await asyncio.sleep(10)  # Wait before retrying
        else:
            logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    async def text_handler_proxy(update: Update, context: CallbackContext) -> None:
        _ = context
        if update.message is None:
            return

        await store_message(update.message, con)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler_proxy))

    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("help", help_command))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(generate_response_loop(con))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
