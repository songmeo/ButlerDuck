#!/usr/bin/env python3
# Copyright Song Meo <songmeo@pm.me>

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import os
from db import con
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
from handler import store_message, generate_response, help_command
from handler import BOT_NAME, BOT_USER_ID
import logging

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.environ["TOKEN"]


async def send_reminder_loop() -> None:
    # TODO FIXME add logging for single iteration failure and total loop failure.
    while True:
        cur = con.cursor()
        cur.execute(
            "SELECT chat_id, action, deadline FROM user_reminder WHERE deadline <= %s AND is_notified = %s",
            (
                datetime.now().isoformat(),
                False,
            ),
        )
        reminders = cur.fetchall()
        for r in reminders:
            chat_id, action, deadline = r
            bot = telegram.Bot(token=TOKEN)

            # This is a simplified solution; in the future, we should ask the LLM to process reminder events.
            # In response, the LLM can invoke another tool, like message a specific user (doesn't have to be
            # the user that created the reminder), or do this and that.
            message = f"This is a reminder to {action} at {deadline}."

            cur.execute(
                """
                INSERT INTO user_message (chat_id, user_id, message)
                VALUES (%s, %s, %s)
                """,
                (chat_id, BOT_USER_ID, message),
            )

            await bot.send_message(chat_id=chat_id, text=message)
            cur.execute("UPDATE user_reminder SET is_notified = TRUE WHERE action = %s", (action,))
            con.commit()

        await asyncio.sleep(60)


async def generate_response_loop() -> None:
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
    cur = con.cursor()

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
            message TEXT NULL,
            user_image_id BIGINT NULL, 
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES tg_user(tg_id) ON DELETE CASCADE,
            CONSTRAINT fk_user_image FOREIGN KEY (user_image_id) REFERENCES user_image(id) ON DELETE SET NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_reminder (
            id SERIAL PRIMARY KEY,  -- SERIAL handles auto-incrementing
            chat_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            deadline TIMESTAMPTZ NOT NULL,
            is_notified BOOLEAN DEFAULT FALSE
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

    async def message_handler_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        assert update.message is not None

        await store_message(update.message, context.bot, con)

    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, message_handler_proxy))

    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))

    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("help", help_command))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(generate_response_loop())
    loop.create_task(send_reminder_loop())

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
