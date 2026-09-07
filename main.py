import os
import random
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токен из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в переменных окружения!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ПРАВ АДМИНА ---
async def is_user_admin(message: Message) -> bool:
    if message.chat.type == "private":
        return True
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in ["creator", "administrator"]:
            return True
    except Exception as e:
        logging.error(f"Ошибка при проверке прав админа: {e}")
    return False

# --- МИНИ-ПРОГНОЗЫ ---
PREDICTIONS = [
    "сегодня звезды шепчут: завари чаёк и отдыхай.",
    "жди прилива сил... который быстро пройдет.",
    "главный враг сегодня — залипание в телефон до ночи.",
    "отличный день, чтобы отменить планы и лечь спать пораньше.",
    "кто-то попытается тебя обмануть, и это будешь ты перед сном («ещё одну серию»).",
    "фортуна на твоей стороне!",
    "отличный момент для классных идей.",
    "сегодня всё получится легко и быстро."
]

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Airis на связи. Мониторю чат и помогаю с порядком.")

@router.message(Command("predict"))
async def cmd_predict(message: Message):
    prediction = random.choice(PREDICTIONS)
    user_name = message.from_user.first_name
    await message.reply(f"🔮 {user_name}, прогноз на сегодня: {prediction}")

# --- МОДЕРАЦИЯ (МУТ, БАН) ---

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await is_user_admin(message):
        await message.reply("⛔️ Эту команду могут использовать только администраторы чата!")
        return
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать ответом на сообщение пользователя, которого нужно забанить!")
        return
    user_to_ban = message.reply_to_message.from_user
    try:
        await message.chat.ban(user_to_ban.id)
        await message.reply(f"🔨 Пользователь {user_to_ban.full_name} заблокирован.")
    except Exception as e:
        await message.reply(f"❌ Не удалось забанить пользователя. Ошибка: {e}")

@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if not await is_user_admin(message):
        await message.reply("⛔️ Эту команду могут использовать только администраторы чата!")
        return
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать ответом на сообщение пользователя!")
        return
    user_to_mute = message.reply_to_message.from_user
    try:
        from aiogram.types import ChatPermissions
        permissions = ChatPermissions(can_send_messages=False)
        await message.chat.restrict(user_to_mute.id, permissions=permissions)
        await message.reply(f"🔇 Пользователь {user_to_mute.full_name} отправлен в мут.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not await is_user_admin(message):
        await message.reply("⛔️ Эту команду могут использовать только администраторы чата!")
        return
    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте на сообщение пользователя, чтобы снять мут.")
        return
    user_to_unmute = message.reply_to_message.from_user
    try:
        from aiogram.types import ChatPermissions
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await message.chat.restrict(user_to_unmute.id, permissions=permissions)
        await message.reply(f"🔊 С пользователя {user_to_unmute.full_name} сняты ограничения.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# --- ЕДИНЫЙ ОБРАБОТЧИК ТЕКСТА ---
@router.message()
async def handle_any_text(message: Message):
    if not message.text:
        return
    
    text = message.text.lower()
    print(f"ПОЛУЧЕН ТЕКСТ: {text}")
    
    if "привет" in text:
        await message.answer(f"Привет, {message.from_user.first_name}! Как настроение?")
    elif len(message.text) > 100 or "подробно" in text or "расскажи" in text:
        await message.answer("Ты попросил(а) подробный ответ. Все системы активны, модерация на страже порядка!")
    else:
        pass

# --- НАСТРОЙКА ВЕБХУКОВ ДЛЯ RENDER ---
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"https://airis-bot.onrender.com{WEBHOOK_PATH}"

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

def main():
    dp.include_router(router)
    dp.startup.register(on_startup)

    app = web.Application()
    
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    setup_application(app, dp, bot=bot)
    
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
