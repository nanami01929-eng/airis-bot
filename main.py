import asyncio
import os
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from google import genai
from aiohttp import web

BOT_TOKEN = "8984930047:AAGUyPlgAh9pip_fnCMtCTgxNvzgkTL35Ks"
GEMINI_KEY = "AQ.Ab8RN6Kq2jUa2zXWsFmZuIpw6hNPVGp7oICTY-PJ-Vf9wHIsPg"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_KEY)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def parse_time(time_str: str) -> timedelta:
    """Парсит время вида 10m, 2h, 1d в timedelta"""
    if not time_str:
        return timedelta(minutes=10)
    match = re.match(r"^(\d+)([mhd])$", time_str.lower())
    if not match:
        return timedelta(minutes=10)
    val, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        return timedelta(minutes=val)
    elif unit == "h":
        return timedelta(hours=val)
    elif unit == "d":
        return timedelta(days=val)
    return timedelta(minutes=10)

async def is_admin(message: types.Message, user_id: int) -> bool:
    """Проверка прав админа"""
    if message.chat.type in ["private"]:
        return False
    member = await bot.get_chat_member(message.chat.id, user_id)
    return member.status in ["administrator", "creator"]

# --- КОМАНДЫ МОДЕРАЦИИ ---

@dp.message(Command("mute"))
async def mute_user(message: types.Message, command: CommandObject):
    if not await is_admin(message, message.from_user.id):
        await message.reply("У тебя нет прав админа!")
        return
    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение нарушителя!")
        return

    duration = parse_time(command.args)
    until_date = datetime.now() + duration
    target_user = message.reply_to_message.from_user

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await message.reply(f"🤐 Пользователь {target_user.full_name} отправлен в мут на {command.args or '10m'}.")
    except Exception as e:
        await message.reply(f"Не удалось замутить (проверь права бота): {e}")

@dp.message(Command("unmute"))
async def unmute_user(message: types.Message):
    if not await is_admin(message, message.from_user.id):
        return
    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение пользователя!")
        return

    target_user = message.reply_to_message.from_user
    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=types.ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await message.reply(f"🔊 Мут с пользователя {target_user.full_name} снят.")
    except Exception as e:
        await message.reply(f"Ошибка при снятии мута: {e}")

@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    if not await is_admin(message, message.from_user.id):
        await message.reply("Эта команда доступна только админам.")
        return
    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение нарушителя!")
        return

    target_user = message.reply_to_message.from_user
    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(f"🚫 Пользователь {target_user.full_name} забанен.")
    except Exception as e:
        await message.reply(f"Не удалось забанить: {e}")

@dp.message(Command("kick"))
async def kick_user(message: types.Message):
    if not await is_admin(message, message.from_user.id):
        return
    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение!")
        return

    target_user = message.reply_to_message.from_user
    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(f"👢 Пользователь {target_user.full_name} кикнут из группы.")
    except Exception as e:
        await message.reply(f"Ошибка при кике: {e}")

# --- ОБРАБОТКА ОБЩЕНИЯ (GEMINI 3.6 FLASH) ---

@dp.message()
async def chat_handler(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        bot_obj = await bot.get_me()
        is_mentioned = bot_obj.username in (message.text or "")
        is_named = "айрис" in (message.text or "").lower()
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_obj.id

        if not (is_mentioned or is_named or is_reply_to_bot):
            return

    try:
        response = ai_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=f"Ты — Айрис, дружелюбная и умная девушка-помощник. Сообщение: {message.text}"
        )
        await message.reply(response.text)
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
async def handle(request):
    return web.Response(text="Bot is running!")

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- НАСТРОЙКА ВЕБХУКА ДЛЯ RENDER ---
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"https://airis-bot.onrender.com{WEBHOOK_PATH}"


async def on_startup(app: web.Application):
  # Устанавливаем вебхук в Telegram при старте
  await bot.set_webhook(WEBHOOK_URL)


def main():
  app = web.Application()

  # Регистрируем обработчик входящих запросов от Telegram
  webhook_requests_handler = SimpleRequestHandler(
      dispatcher=dp,
      bot=bot,
  )
  webhook_requests_handler.register(app, path=WEBHOOK_PATH)

  # Настраиваем приложение
  setup_application(app, dp, bot=bot)
  app.on_startup.append(on_startup)

  # Запускаем веб-сервер на порту, который требует Render
  port = int(os.environ.get("PORT", 10000))
  web.run_app(app, host="0.0.0.0", port=port)


if name == "main":
  main()
