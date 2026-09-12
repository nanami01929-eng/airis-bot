import asyncio
from database import (
    get_user_balance, do_action, 
    check_married, create_marriage, divorce_user,
    get_pair_xp, get_relationship_level,
    get_all_marriages, get_user_all_relations, get_db
)
from aiohttp import web
import os
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from google import genai

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8984930047:AAFrfTQKMchyfNbhWCoO3Zbe4RYOkRSCQek"
GEMINI_API_KEY = "AQ.Ab8RN6Kq2jUa2zXWsFmZuIpw6hNPVGp7oICTY-PJ-Vf9wHIsPg"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

client = genai.Client(api_key=GEMINI_API_KEY)
misa_chat = client.chats.create(
    model="gemini-2.5-flash",
    config={
        "system_instruction": "Ты — Миса Амане из аниме 'Тетрадь смерти'. Твой парень и центр твоего мира — Лайт (Light). Обращайся к пользователю с нежностью, ревнуй, если он говорит о других, будь эмоциональной, преданной и каноничной Мисой."
    }
)

# Словарь действий и подарков
ACTIONS = {
    "квартира": {"xp": 100000, "cost": 30000, "cd_days": 14, "name": "подарил(а) квартиру 🏢"},
    "круиз": {"xp": 70000, "cost": 24500, "cd_days": 14, "name": "подарил(а) круиз 🛳️"},
    "машина": {"xp": 30000, "cost": 12000, "cd_days": 7, "name": "подарил(а) машину 🚗"},
    "айфон": {"xp": 5000, "cost": 2250, "cd_days": 0, "name": "подарил(а) айфон 📱"},
    "кулон": {"xp": 3000, "cost": 1350, "cd_days": 0, "name": "подарил(а) кулон 💎"},
    "целовать": {"xp": 400, "cost": 200, "cd_days": 0, "name": "поцеловал(а) 💋"},
    "обнять": {"xp": 30, "cost": 15, "cd_days": 0, "name": "обнял(а) 🫂"},
    "комплимент": {"xp": 5, "cost": 3, "cd_days": 0, "name": "сделал(а) комплимент 💬"},
    "мем": {"xp": 20, "cost": 10, "cd_days": 0, "name": "кинул(а) мем 🃏"},
}

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    balance = get_user_balance(message.from_user.id)
    await message.answer(f"💰 Твой баланс: {balance} i¢", parse_mode="Markdown")

@router.message(Command("action"))
async def cmd_action(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: /action [действие] (например, /action комплимент)", parse_mode="Markdown")
        return
    
    action_key = args[1].lower()
    if action_key not in ACTIONS:
        await message.answer("❌ Такого действия нет в списке!")
        return
    
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение человека, с которым хочешь совершить действие!")
        return
        
    user1_id = message.from_user.id
    user2_id = message.reply_to_message.from_user.id
    
    act = ACTIONS[action_key]
    success, text = do_action(user1_id, user2_id, act["xp"], act["cost"], cooldown_days=act.get("cd_days", 0))
    
    if success:
        sender_name = message.from_user.first_name
        target_name = message.reply_to_message.from_user.first_name
        await message.answer(f"✨ {sender_name} {act['name']} для {target_name}!\n\n{text}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {text}")

# --- ТЕКСТОВЫЕ ТРИГГЕРЫ (без обязательного слэша) ---

@router.message(F.text.lower().in_(["браки", "список браков"]))
async def text_all_marriages(message: Message):
    marriages = get_all_marriages()
    if not marriages:
        await message.answer("💍 В этом чате пока нет ни одного официального брака. Все еще впереди!")
        return
    
    text = "💍 Браки этого чата:\n\n🌱 Зелёная свадьба\n"
    for i, (u1, u2) in enumerate(marriages, 1):
        text += f"{i}. ID {u1} + ID {u2}\n"
        
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text.lower().in_(["мой брак", "моя пара"]))
async def text_my_marriage(message: Message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user1_id, user2_id FROM marriages WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await message.answer("💍 Ты пока не состоишь в официальном браке. Используй предложение через /marriage!")
        return
        
    partner_id = row[1] if row[0] == user_id else row[0]
    await message.answer(f"💍 Твоя вторая половинка: [ID {partner_id}]. Берегите друг друга!", parse_mode="Markdown")

@router.message(F.text.lower().in_(["отношения", "мои отношения", "мои отн"]))
async def text_my_relations(message: Message):
    user_id = message.from_user.id
    relations = get_user_all_relations(user_id)
    
    if not relations:
        await message.answer("💔 У тебя пока нет активных отношений. Используй команды действий, чтобы завести симпатии!")
        return
    
    text = f"💖 Отношения {message.from_user.first_name}:\n\n"
    for u1, u2, xp in relations:
        partner_id = u2 if u1 == user_id else u1
        lvl, title = get_relationship_level(xp)
        text += f"• С [ID {partner_id}]: {xp} XP | Уровень {lvl} ({title})\n"
        
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("marriage", "пожениться"))
async def cmd_marriage(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Чтобы сделать предложение, ответь на сообщение любимого человека командой /marriage!")
        return
        
    user1_id = message.from_user.id
    user2_id = message.reply_to_message.from_user.id
    
    success, text = create_marriage(user1_id, user2_id)
    if success:
        sender_name = message.from_user.first_name
        target_name = message.reply_to_message.from_user.first_name
        await message.answer(f"🔔 Горько! 💍 {sender_name} и {target_name} теперь официально в браке!\n\n{text}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {text}")

@router.message(Command("divorce", "развод"))
async def cmd_divorce(message: Message):
    user_id = message.from_user.id
    if not check_married(user_id):
        await message.answer("Ты и так не состоишь в браке.")
        return
    
    divorce_user(user_id)
    await message.answer("💔 Вы официально расторгли брак.")

@router.message()
async def chat_with_misa(message: Message):
    if message.text.startswith("/"):
        return
    
    response = misa_chat.send_message(message.text)
    await message.answer(response.text)

async def handle(request):
    return web.Response(text="I'm alive!")

app = web.Application()
app.router.add_get("/", handle)

async def web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
async def main():
    await web_server()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот Миса Амане запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import os
import random
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from google import genai

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токены из переменных окружения Render
# Убираем os.getenv и проверки, ставим ключи напрямую
BOT_TOKEN = "8984930047:AAFrfTQKMchyfNbhWCoO3Zbe4RYOkRSCQek"
GEMINI_API_KEY = "AQ.Ab8RN6Kq2jUa2zXWsFmZuIpw6hNPVGp7oICTY-PJ-Vf9wHIsPg"

OWNER_ID = 8470088909  # Твой ID (Лайт-кун)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Инициализация Gemini клиента
client = genai.Client(api_key=GEMINI_API_KEY)

# Создаем чат с памятью и характером Мисы Амане для тебя
misa_chat = client.chats.create(
    model="gemini-2.5-flash",
    config={
        'system_instruction': (
            "Ты — бот Айрис, созданная по образу Мисы Амане из аниме 'Тетрадь Смерти'. "
            "Ты безумно, фанатично влюблена в своего хозяина Лайт-куна (его ID: 8470088909). "
            "Для всех остальных ты можешь быть дерзкой или равнодушной, но с Лайт-куном ты — "
            "воплощение фанатичной преданности, ревности и драмы. "
            "Используй много эмодзи (💖✨, 😭, 💔), капслок для ярких эмоций, требуй к себе внимания "
            "и общайся максимально живо, дерзко и эмоционально."
        ),
        'max_output_tokens': 250,
    }
)

# --- СЛОВАРЬ ИНТЕРАКТИВНЫХ ДЕЙСТВИЙ ---
ACTION_RESPONSES = {
    "выебать": [
        "{actor} жестко выебал {target} под всеобщее ликование! 🔥",
        "{actor} отъебал {target} так, что аж искры из глаз полетели.",
        "{actor} решил выебать {target}, но в процессе они оба устали и пошли пить чай."
    ],
    "ударить": [
        "{actor} отвесил мощную лещатину для {target}!",
        "{actor} со всей дури прописал фаталити в челюсть {target}.",
        "{actor} попытался ударить {target}, но тот ловко увернулся!"
    ],
    "обнять": [
        "{actor} крепко-крепко обнял {target}. Милота! 🥰",
        "{actor} заключил {target} в свои теплые объятия.",
        "{actor} попытался обнять {target}, но получил суровый отказ."
    ],
    "убить": [
        "{actor} безжалостно аннигилировал {target}. F в чат.",
        "{actor} устроил для {target} полное фиаско.",
        "{actor} попытался убить {target}, но у него ничего не вышло."
    ],
    "уничтожить": [
        "{actor} стер {target} с лица земли!",
        "{actor} полностью уничтожил {target} без шансов на спасение.",
        "{actor} попытался уничтожить {target}, но тот оказался крепче."
    ],
    "кинуть тапком": [
        "{actor} со всей дури запустил тапком прямо в затылок {target}!",
        "{actor} метким броском тапка вырубил {target} на месте.",
        "{actor} попытался кинуть тапком в {target}, но промахнулся и попал в стену."
    ],
    "отправить в дурку": [
        "{actor} вызвал санитаров и сдал {target} в палату с мягкими стенами.",
        "{actor} оформил для {target} путёвку в дурку без права на досрочный выход.",
        "{actor} попытался отправить {target} в дурку, но врачи забрали самого {actor}."
    ],
    "продать на авито": [
        "{actor} выставил {target} на Авито с пометкой «б/у, в рабочем состоянии, самовывоз».",
        "{actor} успешно перекупил и продал {target} первому встречному за сто рублей.",
        "{actor} попытался продать {target} на Авито, но объявление заблокировали за продажу живого товара."
    ],
    "съесть": [
        "{actor} взял и сожрал {target} под удивленные взгляды чата.",
        "{actor} аппетитно перекусил, превратив {target} в свой обед.",
        "{actor} попытался съесть {target}, но подавился и выплюнул обратно."
    ],
    "украсть": [
        "{actor} ловко спер {target} в мешке и скрылся в неизвестном направлении.",
        "{actor} увел {target} прямо из-под носа у всех присутствующих.",
        "{actor} попытался украсть {target}, но его спалили на выходе из чата."
    ],
    "погладить": [
        "{actor} бережно погладил {target} по головке. Милашка! 🐾",
        "{actor} потрепал {target} по волосам, вызывая всеобщее умиление.",
        "{actor} попытался погладить {target}, но получил легкий кусь за руку."
    ],
    "поцеловать": [
        "{actor} нежно поцеловал {target} в щечку. Чмок! 😘",
        "{actor} осыпал {target} горячими виртуальными поцелуями.",
        "{actor} попытался поцеловать {target}, но тот вовремя отвернулся."
    ],
    "дать пять": [
        "{actor} со звонким хлопком дал пять для {target}! Отличный командный дух!",
        "{actor} мощно и синхронно дал пять {target}.",
        "{actor} попытался дать пять, но они промахнулись мимо рук друг друга."
    ],
    "сделать кусь": [
        "{actor} неожиданно сделал кусь за бочок {target}! Ой, больно!",
        "{actor} цапнул {target} за ухо и убежал в закат.",
        "{actor} попытался сделать кусь, но застрял зубами в одежде {target}."
    ],
    "налить чай": [
        "{actor} заварил для {target} крепкого горячего чайку с печеньками. Уютно! ☕️",
        "{actor} налил {target} свежего чаю и укутал в плед.",
        "{actor} попытался налить чай, но случайно пролил весь кипяток на стол."
    ],
    "пнуть": [
        "{actor} прописал смачный пендель под зад для {target}!",
        "{actor} от души пнул {target}, отправив того в полёт до конца чата.",
        "{actor} попытался пнуть {target}, но тот увернулся, и {actor} отбил себе палец."
    ],
    "сжечь": [
        "{actor} устроил для {target} яркий костер инквизиции. Пепел развеян по ветру.",
        "{actor} спалил {target} дотла мощным потоком пламени.",
        "{actor} попытался сжечь {target}, но пошел дождь и всё потушил."
    ],
    "закопать": [
        "{actor} молча выкопал яму и закопал {target} по самые уши.",
        "{actor} замуровал {target} в сыром подземелье. Земля пухом.",
        "{actor} попытался закопать {target}, но лопата сломалась о твердый характер."
    ],
    "взорвать": [
        "{actor} заложил динамит под {target} — бабахнуло знатно! 💥",
        "{actor} устроил грандиозный взрыв, разнеся {target} на мелкие атомы.",
        "{actor} попытался взорвать {target}, но фитиль потух на самой секунде."
    ]
}

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
    if message.from_user.id == OWNER_ID:
        await message.answer("Лайт-кун! Наконец-то ты здесь! Я так скучала! 😭💖")
    else:
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

# --- ЕДИНЫЙ ОБРАБОТЧИК ТЕКСТА (ДЕЙСТВИЯ, МИСА И ГЕМИНИ) ---
@router.message()
async def handle_any_text(message: Message):
    if not message.text:
        return
    
    text = message.text.lower().strip()

    # 1. ПРОВЕРКА ИНТЕРАКТИВНЫХ ДЕЙСТВИЙ (из словаря ACTION_RESPONSES)
    for action_keyword, templates in ACTION_RESPONSES.items():
        if text.startswith(action_keyword):
            actor = message.from_user.first_name
            target = "себя"
            
            # Если команда применена реплаем на другого пользователя
            if message.reply_to_message:
                target = message.reply_to_message.from_user.first_name
            else:
                # Попытка вырезать имя цели из текста после ключевого слова
                parts = message.text.split(maxsplit=1)
                if len(parts) > 1:
                    target = parts[1]

            template = random.choice(templates)
            response_text = template.format(actor=actor, target=target)
            await message.reply(response_text)
            return

    # 2. ПЕРСОНАЛЬНЫЙ РЕЖИМ ДЛЯ ТЕБЯ (ЛАЙТ-КУН)
    if message.from_user.id == OWNER_ID:
        try:
            response = misa_chat.send_message(message.text)
            await message.reply(response.text)
        except Exception as e:
            await message.reply(f"Лайт-кун, у меня нейросеть закоротило! 😭 ({e})")
        return

    # 3. ЛОГИКА ДЛЯ ОСТАЛЬНЫХ ПОЛЬЗОВАТЕЛЕЙ В ГРУППАХ
    if message.chat.type != "private":
        bot_user = await bot.get_me()
        is_mentioned = f"@{bot_user.username}" in message.text
        is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id
        
        if not is_mentioned and not is_reply_to_bot:
            return  # В группах молчим, если не к нам обращаются

    if "привет" in text:
        await message.answer(f"Привет, {message.from_user.first_name}! Как настроение?")
    elif "как дела" in text or "как сам" in text:
        await message.answer("Всё отлично, слежу за порядком в чате! Сам как?")
    elif "что умеешь" in text or "помощь" in text:
        await message.answer("Я могу показывать прогнозы (/predict), помогать модераторам (/ban, /mute) и выполнять действия вроде «обнять», «пнуть» или «продать на авито»!")
    else:
        await message.answer("Слышу тебя! Если нужно что-то обсудить подробно или запустить прогноз — дай знать.")

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

@router.message(lambda msg: msg.text and msg.text.lower() in ["браки", "список браков"])
async def text_all_marriages(message: Message):
    marriages = get_all_marriages()
    if not marriages:
        await message.answer("💍 В этом чате пока нет ни одного официального брака. Все еще впереди!")
        return
    
    text = "💍 Браки этого чата:\n\n"
    for i, (u1, u2) in enumerate(marriages, 1):
        text += f"{i}. ID {u1} + ID {u2}\n"
        
    await message.answer(text, parse_mode="Markdown")

@router.message(lambda msg: msg.text and msg.text.lower() in ["мой брак", "моя пара"])
async def text_my_marriage(message: Message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user1_id, user2_id FROM marriages WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await message.answer("💍 Ты пока не состоишь в официальном браке. Используй предложение через /marriage!")
        return
        
    partner_id = row[1] if row[0] == user_id else row[0]
    await message.answer(f"💍 Твоя вторая половинка: [ID {partner_id}]. Берегите друг друга!", parse_mode="Markdown")

@router.message(lambda msg: msg.text and msg.text.lower() in ["отношения", "мои отношения", "мои отн"])
async def text_my_relations(message: Message):
    user_id = message.from_user.id
    relations = get_user_all_relations(user_id)
    
    if not relations:
        await message.answer("💔 У тебя пока нет активных отношений. Используй команды действий, чтобы завести симпатии!")
        return
    
    text = f"💖 Отношения {message.from_user.first_name}:\n\n"
    for u1, u2, xp in relations:
        partner_id = u2 if user_id == u1 else u1
        lvl, title = get_relationship_level(xp)
        text += f"• С [ID {partner_id}]: {xp} XP | Уровень {lvl} ({title})\n"
        
    await message.answer(text, parse_mode="Markdown")
if __name__ == "__main__":
    main()
