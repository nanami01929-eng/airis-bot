import asyncio
import logging
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message,
    ChatPermissions,
    BotCommand,
    BotCommandScopeDefault
)
from aiogram.exceptions import TelegramBadRequest

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация
TOKEN = "8984930047:AAH6lbrA-ROBpkSFszhwlwp5ghV-gYqkMNM"
OWNER_ID = 8470088909  # Твой Telegram ID (защита хозяина)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище варнов в памяти: {chat_id: {user_id: warn_count}}
warnings_storage = {}

# Наборы рандомных ответов для интерактивных действий
ACTION_RESPONSES = {
    "трахнуть": [
        "{actor} утащил(а) {target} в спальню. Дальше история умалчивает... 🔥",
        "{actor} страстно овладел(а) {target}, не оставив ни шанса на сопротивление.",
        "{actor} показал(а) {target}, кто здесь главный по страсти."
    ],
    "выебать": [
        "{actor} преподал(а) {target} жесткий и бескомпромиссный урок анатомии 🔞",
        "{actor} устроил(а) {target} тотальный разнос, так что кровать ходила ходуном.",
        "{actor} стер(ла) {target} в порошок в порыве дикой энергии."
    ],
    "ударить": [
        "{actor} отвесил(а) знатную оплеуху {target}, чтобы тот(та) пришел(а) в себя.",
        "{actor} прописал(а) {target} смачный лещ прямо посреди чата.",
        "{actor} вмазал(а) {target} так, что аж искры из глаз посыпались."
    ],
    "обнять": [
        "{actor} бережно обнял(а) {target}, срочно выделив порцию тепла.",
        "{actor} крепко прижал(а) к себе {target}, укутав заботой.",
        "{actor} заключил(а) {target} в крепкие объятия, чтоб не грустил(а)."
    ]
}


# --- УТИЛИТА ПРОВЕРКИ АДМИНСКИХ ПРАВ ---
async def is_user_admin(message: Message) -> bool:
    if message.chat.type == "private":
        return True  # В личке считаем владельцем
    
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


# --- УСТАНОВКА МЕНЮ КОМАНД ---
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="mute", description="Выдать мут (админам)"),
        BotCommand(command="unmute", description="Снять мут (админам)"),
        BotCommand(command="ban", description="Забанить (админам)"),
        BotCommand(command="unban", description="Разбанить (админам)"),
        BotCommand(command="warn", description="Дать варн 3/3 = кик (админам)"),
        BotCommand(command="unwarn", description="Снять варн (админам)")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


# --- КОМАНДЫ МОДЕРАЦИИ ---

@dp.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject):
    if not await is_user_admin(message):
        await message.reply("Не по чину берешься, дружок. Команда только для админов.")
        return
    
    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение того, кого хочешь замутить (например: /mute 20).")
        return

    target = message.reply_to_message.from_user
    
    minutes = 20
    if command.args:
        try:
            minutes = int(command.args.split()[0])
        except ValueError:
            pass

    until_time = datetime.now() + timedelta(minutes=minutes)

    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_time
        )
        # Исправлено: заменено несуществующее поле на target.full_name
        await message.answer(f"🤐 Пользователь {target.full_name} замучен на {minutes} минут.")
    except TelegramBadRequest as e:
        await message.answer(f"Не удалось выдать мут: {e}")


@dp.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not await is_user_admin(message):
        await message.reply("Команда доступна только администраторам чата.")
        return

    if not message.reply_to_message:
        await message.reply("Ответь этой командой на сообщение пользователя, чтобы вернуть ему голос.")
        return

    target = message.reply_to_message.from_user

    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await message.answer(f"🔊 Мут снят с пользователя {target.full_name}.")
    except TelegramBadRequest as e:
        await message.answer(f"Не удалось снять мут: {e}")


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await is_user_admin(message):
        await message.reply("Команда доступна только администраторам чата.")
        return

    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, которого нужно забанить.")
        return

    target = message.reply_to_message.from_user

    try:
        await message.bot.ban_chat_member(chat_id=message.chat.id, user_id=target.id)
        await message.answer(f"🔨 Пользователь {target.full_name} отправлен в бан.")
    except TelegramBadRequest as e:
        await message.answer(f"Не удалось забанить: {e}")


@dp.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject):
    if not await is_user_admin(message):
        await message.reply("Команда доступна только администраторам чата.")
        return

    if not message.reply_to_message and not command.args:
        await message.reply("Ответь на сообщение или укажи ID пользователя для разбана.")
        return

    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        try:
            target_id = int(command.args.split()[0])
        except ValueError:
            await message.reply("Некорректный ID пользователя.")
            return

    try:
        await message.bot.unban_chat_member(chat_id=message.chat.id, user_id=target_id, only_if_banned=True)
        await message.answer("🔓 Пользователь успешно разбанен.")
    except TelegramBadRequest as e:
        await message.answer(f"Не удалось разбанить: {e}")


@dp.message(Command("warn"))
async def cmd_warn(message: Message):
    if not await is_user_admin(message):
        await message.reply("Команда доступна только администраторам чата.")
        return

    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы выдать предупреждение.")
        return

    chat_id = message.chat.id
    target = message.reply_to_message.from_user
    user_id = target.id

    if chat_id not in warnings_storage:
        warnings_storage[chat_id] = {}
    
    current_warns = warnings_storage[chat_id].get(user_id, 0) + 1
    warnings_storage[chat_id][user_id] = current_warns

    if current_warns >= 3:
        warnings_storage[chat_id][user_id] = 0
        try:
            await message.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await message.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            await message.answer(f"⚠️ У {target.full_name} накопилось 3/3 предупреждений. Автоматический кик совершен!")
        except TelegramBadRequest as e:
            await message.answer(f"Не удалось кикнуть пользователя: {e}")
    else:
        await message.answer(f"⚠️ Предупреждение выдано {target.full_name}. Текущий счетчик: {current_warns}/3.")


@dp.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    if not await is_user_admin(message):
        await message.reply("Команда доступна только администраторам чата.")
        return

    if not message.reply_to_message:
        await message.reply("Ответь на сообщение пользователя, чтобы снять варн.")
        return

    chat_id = message.chat.id
    target = message.reply_to_message.from_user
    user_id = target.id

    if chat_id in warnings_storage and warnings_storage[chat_id].get(user_id, 0) > 0:
        warnings_storage[chat_id][user_id] -= 1
        current_warns = warnings_storage[chat_id][user_id]
        await message.answer(f"✅ С {target.full_name} снят варн. Осталось: {current_warns}/3.")
    else:
        await message.answer("У этого пользователя и так нет активных предупреждений.")


# --- ИНТЕРАКТИВНЫЕ ДЕЙСТВИЯ ПО РЕПЛАЮ (С ЗАЩИТОЙ ХОЗЯИНА) ---

@dp.message(F.reply_to_message)
async def handle_social_actions(message: Message):
    if not message.text:
        return

    text_lower = message.text.strip().lower()
    
    matched_action = None
    for action_key in ACTION_RESPONSES.keys():
        if text_lower.startswith(action_key):
            matched_action = action_key
            break

    if not matched_action:
        return

    target = message.reply_to_message.from_user

    # Защита хозяина: если кто-то пытается применить действие на тебя
    if target.id == OWNER_ID:
        await message.reply("Не могу тронуть своего хозяина! 🛡")
        return

    actor = message.from_user.first_name
    target_name = target.first_name

    template = random.choice(ACTION_RESPONSES[matched_action])
    response_text = template.format(actor=actor, target=target_name)
    await message.answer(response_text)


# --- ЗАПУСК БОТА ---
async def main():
    await set_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
