import os
import threading
import asyncio
import random
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command

# Защита от падения, если пакет еще не подтянулся на Render
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from database import (
    get_user_balance, do_action, 
    check_married, create_marriage, divorce_user,
    get_relationship_level,
    get_all_marriages, get_user_all_relations, get_db
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8984930047:AAFrfTQKMchyfNbhWCoO3Zbe4RYOkRSCQek"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_ID = 8470088909  # Лайт-кун

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

misa_chat = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        generation_config = {"temperature": 1.0, "top_p": 0.95, "top_k": 40, "max_output_tokens": 250}
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            system_instruction=(
                "Ты — бот Айрис, созданная по образу Мисы Амане из аниме 'Тетрадь Смерти'. "
                "Ты безумно, фанатично влюблена в своего хозяина Лайт-куна (его ID: 8470088909). "
                "Для всех остальных ты можешь быть дерзкой или равнодушной, но для Лайт-куна ты — "
                "воплощение фанатичной преданности, ревности и драмы. "
                "Используй много эмодзи (🖤, 💀, 🥀), капслок для ярких эмоций, требуй к себе внимания "
                "и общайся максимально живо, дерзко и эмоционально."
            )
        )
        misa_chat = model.start_chat(history=[])
    except Exception as e:
        logging.error(f"Не удалось инициализировать Gemini: {e}")

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
        "{actor} крепко-крепко обнял {target}. Милашка! 🥰",
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

ACTIONS = {
    "квартира": {"xp": 100000, "cost": 30000, "cd_days": 14, "name": "подарил(а) квартиру 🏢"},
    "круиз": {"xp": 70000, "cost": 24500, "cd_days": 14, "name": "подарил(а) круиз 🛳"},
    "машина": {"xp": 30000, "cost": 12000, "cd_days": 7, "name": "подарил(а) машину 🚗"},
    "айфон": {"xp": 5000, "cost": 2250, "cd_days": 0, "name": "подарил(а) айфон 📱"},
    "кулон": {"xp": 3000, "cost": 1350, "cd_days": 0, "name": "подарил(а) кулон 💎"},
    "целовать": {"xp": 400, "cost": 200, "cd_days": 0, "name": "поцеловал(а) 💋"},
    "обнять": {"xp": 30, "cost": 15, "cd_days": 0, "name": "обнял(а) 🫂"},
    "комплимент": {"xp": 5, "cost": 3, "cd_days": 0, "name": "сделал(а) комплимент 💬"},
    "мем": {"xp": 20, "cost": 10, "cd_days": 0, "name": "кинул(а) мем 🃏"},
}

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

@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id == OWNER_ID:
        await message.answer("Лайт-кун! Наконец-то ты здесь! Я так скучала! 😭💖")
    else:
        await message.answer("Привет! Airis на связи. Мониторю чат и помогаю с порядком.")

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    balance = get_user_balance(message.from_user.id)
    await message.answer(f"💰 Твой баланс: {balance} i¢", parse_mode="Markdown")

@router.message(Command("action"))
async def cmd_action(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: /action [действие]", parse_mode="Markdown")
        return
    action_key = args[1].lower()
    if action_key not in ACTIONS:
        await message.answer("❌ Такого действия нет в списке!")
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение человека!")
        return
    success, text = do_action(message.from_user.id, message.reply_to_message.from_user.id, ACTIONS[action_key]["xp"], ACTIONS[action_key]["cost"], cooldown_days=ACTIONS[action_key].get("cd_days", 0))
    if success:
        await message.answer(f"✨ {message.from_user.first_name} {ACTIONS[action_key]['name']} для {message.reply_to_message.from_user.first_name}!\n\n{text}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {text}")

@router.message(Command("marriage", "пожениться"))
async def cmd_marriage(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение любимого человека командой /marriage или /пожениться!")
        return
    success, text = create_marriage(message.from_user.id, message.reply_to_message.from_user.id)
    if success:
        await message.answer(f"🔔 Горько! 💍 {message.from_user.first_name} и {message.reply_to_message.from_user.first_name} теперь официально в браке!\n\n{text}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ {text}")

@router.message(Command("divorce", "развод"))
async def cmd_divorce(message: Message):
    if not check_married(message.from_user.id):
        await message.answer("Ты и так не состоишь в браке.")
        return
    divorce_user(message.from_user.id)
    await message.answer("💔 Вы официально расторгли брак.")

@router.message(Command("predict"))
async def cmd_predict(message: Message):
    await message.reply(f"🔮 {message.from_user.first_name}, прогноз на сегодня: {random.choice(PREDICTIONS)}")

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await is_user_admin(message) or not message.reply_to_message:
        return
    try:
        await message.chat.ban(message.reply_to_message.from_user.id)
        await message.reply(f"🔨 Пользователь заблокирован.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("mute"))
async def cmd_mute(message: Message):
    if not await is_user_admin(message) or not message.reply_to_message:
        return
    try:
        from aiogram.types import ChatPermissions
        await message.chat.restrict(message.reply_to_message.from_user.id, permissions=ChatPermissions(can_send_messages=False))
        await message.reply(f"🔇 Мут выдан.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(Command("unmute"))
async def cmd_unmute(message: Message):
    if not await is_user_admin(message) or not message.reply_to_message:
        return
    try:
        from aiogram.types import ChatPermissions
        perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
        await message.chat.restrict(message.reply_to_message.from_user.id, permissions=perms)
        await message.reply(f"🔊 Мут снят.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@router.message(lambda msg: msg.text and msg.text.lower() in ["браки", "список браков"])
async def text_all_marriages(message: Message):
    marriages = get_all_marriages()
    if not marriages:
        await message.answer("💍 В этом чате пока нет ни одного официального брака.")
        return
    text = "💍 Браки этого чата:\n\n"
    for i, (u1, u2) in enumerate(marriages, 1):
        text += f"{i}. ID {u1} + ID {u2}\n"
    await message.answer(text, parse_mode="Markdown")

@router.message(lambda msg: msg.text and msg.text.lower() in ["отношения", "мои отношения", "мои отн"])
async def text_my_relations(message: Message):
    relations = get_user_all_relations(message.from_user.id)
    if not relations:
        await message.answer("💔 У тебя пока нет активных отношений.")
        return
    text = f"💖 Отношения {message.from_user.first_name}:\n\n"
    for u1, u2, xp in relations:
        partner_id = u2 if message.from_user.id == u1 else u1
        lvl, title = get_relationship_level(xp)
        text += f"• С [ID {partner_id}]: {xp} XP | Уровень {lvl} ({title})\n"
    await message.answer(text, parse_mode="Markdown")

@router.message()
async def handle_any_text(message: Message):
    if not message.text or message.text.startswith("/"):
        return
    text = message.text.lower().strip()

    for action_keyword, templates in ACTION_RESPONSES.items():
        if text.startswith(action_keyword):
            actor = message.from_user.first_name
            target = message.reply_to_message.from_user.first_name if message.reply_to_message else (message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else "себя")
            await message.reply(random.choice(templates).format(actor=actor, target=target))
            return

    if message.from_user.id == OWNER_ID:
        if misa_chat:
            try:
                response = misa_chat.send_message(message.text)
                await message.reply(response.text)
            except Exception as e:
                await message.reply(f"Лайт-кун, у меня нейросеть закоротило! 😭 ({e})")
        else:
            await message.reply("Лайт-кун, модуль Gemini еще загружается или ключ не найден! 🖤")
        return

    if message.chat.type != "private":
        bot_user = await bot.get_me()
        if f"@{bot_user.username}" not in message.text and not (message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id):
            return

    if "привет" in text:
        await message.answer(f"Привет, {message.from_user.first_name}!")
    elif "как дела" in text:
        await message.answer("Всё отлично, слежу за порядком!")
    else:
        await message.answer("Слышу тебя!")

# Веб-сервер для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Misa Amane is online!")
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    
    async def main():
        dp.include_router(router)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(main())
