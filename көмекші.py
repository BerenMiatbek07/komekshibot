import asyncio
import logging
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import google.generativeai as genai
from datetime import datetime, timedelta
import time

# ============================================
# ӨЗ ТОКЕНДЕРІҢІЗДІ МЫНА ЖЕРГЕ ЖАЗЫҢЫЗ!!!
TELEGRAM_BOT_TOKEN = "8401050141:AAFd9QDgCW98ZvCg8rETmzA3CzpHoMKvKCA"
GEMINI_API_KEY = "AIzaSyCNdk107ru3tIgbqv5ye9hsGM5Gcr1mn9Q"
# ============================================

# Рұқсат етілген топтар (қосу үшін осында ID қосыңыз)
ALLOWED_CHAT_IDS = [
    -1003143936035,
    # -1001234567890,  # қосымша топ болса осылай қосыңыз
]

# Логтар
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Gemini орнату
genai.configure(api_key=GEMINI_API_KEY)

# Ботты дұрыс инициализациялау
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Пайдаланушылардың контексті және лимитке бақылау
user_contexts = {}
user_last_request = {}  # Соңғы сұрау уақыты
RATE_LIMIT_SECONDS = 2  # 2 секундта бір сұрау

# Экран өшпесін деп фондық цикл
def keep_running():
    """Pydroid 3-те экран өшсе де тоқтамауы үшін"""
    while True:
        time.sleep(60)

async def check_rate_limit(user_id: int) -> bool:
    """Сұрау лимитін тексеру"""
    now = datetime.now()
    if user_id in user_last_request:
        last_time = user_last_request[user_id]
        if (now - last_time).seconds < RATE_LIMIT_SECONDS:
            return False
    user_last_request[user_id] = now
    return True

async def get_gemini_answer(user_id: int, question: str) -> str:
    """Gemini 2.5 Flash моделімен жауап алу"""
    try:
        # Модельді жаңарту - Gemini 2.5 Flash
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",  # ЖАҢА МОДЕЛЬ
            system_instruction="Сен – қазақ тілінде өте ақылды, әзілқой әрі пайдалы көмекші ботсың. Барлық жауапты тек қазақша, түсінікті, қызықты әрі толық жаз. Эмодзилерді орынды қолдан."
        )

        # Контекстті инициализациялау
        if user_id not in user_contexts:
            user_contexts[user_id] = []
        
        # Соңғы 10 хабарламаны тарих ретінде қолдану (токен үнемдеу)
        history = user_contexts[user_id][-10:]

        # Чат сессиясын бастау
        chat = model.start_chat(
            history=history,
            enable_automatic_function_calling=True
        )
        
        # Жауапты алу (асинхронды түрде)
        response = await asyncio.to_thread(
            chat.send_message,
            question,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,  # Креативтілік деңгейі
                max_output_tokens=2048,  # Жауаптың максималды ұзындығы
            )
        )
        
        answer = response.text

        # Контекстті жаңарту (токен шегін бақылау)
        user_contexts[user_id].append({"role": "user", "parts": [question]})
        user_contexts[user_id].append({"role": "model", "parts": [answer]})
        
        # Контекстті тазалау (егер тым ұзақ болса)
        if len(user_contexts[user_id]) > 20:
            user_contexts[user_id] = user_contexts[user_id][-10:]

        return answer

    except genai.types.generation_types.BlockedPromptException as e:
        logger.error(f"Блокталған сұрау: {e}")
        return "⚠️ Сіздің сұрағыңыз қауіпсіздік саясатына сәйкес келмейді. Басқа сұрақпен көріңіз."
    
    except genai.types.generation_types.StopCandidateException as e:
        logger.error(f"Тоқтатылды: {e}")
        return "😔 Жауап жасау барысында тоқтатылды. Сұрағыңызды қайта формулировкаңыз."
    
    except Exception as e:
        logger.error(f"Gemini қатесі: {e}", exc_info=True)
        return "😔 Қазір Gemini қызметі қолжетімсіз. Біраздан соң (30 сек) қайталап көріңізші."

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    """Ботты іске қосу/көмек командасы"""
    if message.chat.type in ['group', 'supergroup'] and message.chat.id not in ALLOWED_CHAT_IDS:
        await message.reply("⛔ Бұл топ рұқсат етілмеген!")
        return

    text = """
<b>🤖 Қазақша Gemini Көмекші Бот v3.5</b>
<i>Модель: Gemini 2.5 Flash ⚡</i>

Мен топтағы кез келген сұраққа <b>қазақша</b> жылдам әрі дәл жауап беремін!

<b>Қолдану:</b>
<code>көмекші бот, су тасқыны қашан бітеді?</code>
<code>көмекші бот, Python-та Telegram бот қалай жасаймын?</code>

Жауап әрқашан қазақша, әдемі әрі толық болады 🚀

<b>Командалар:</b>
/getchatid – осы топтың ID-ын білу үшін
/clear – өз сұхбат тарихын тазалау
    """
    await message.reply(text)

@dp.message(Command("getchatid"))
async def cmd_getid(message: types.Message):
    """Чат ID-ын алу"""
    await message.reply(f"<b>Чат ID:</b> <code>{message.chat.id}</code>")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Пайдаланушы контекстін тазалау"""
    user_id = message.from_user.id
    if user_id in user_contexts:
        user_contexts[user_id].clear()
        await message.reply("✅ Сіздің сұхбат тарихыңыз тазаланды!")
    else:
        await message.reply("ℹ️ Сіздің тарихыңыз бос.")

@dp.message()
async def handle_messages(message: types.Message):
    """Негізгі хабарларды өңдеу"""
    if message.chat.type not in ['group', 'supergroup']:
        return

    if message.chat.id not in ALLOWED_CHAT_IDS:
        return

    text = message.text or ""
    if not text.lower().startswith("көмекші бот"):
        return

    # Rate limit тексеру
    if not await check_rate_limit(message.from_user.id):
        await message.reply("⏳ Тым жылдам! 2 секундтан соң қайта сұраңыз.")
        return

    question = text[10:].strip()
    if len(question) < 3:
        await message.reply("❓ Сұрағыңызды толығырақ жазыңызшы 😊 (кемінде 3 таңба)")
        return

    # "Ойланып жатырмын..." хабарламасы
    thinking_msg = await message.reply("<i>🤔 Gemini 2.5 Flash ойланып жатыр...</i>")

    try:
        answer = await get_gemini_answer(message.from_user.id, question)

        # Ұзын жауапты бөліп жіберу (Telegram лимиті 4096 таңба)
        if len(answer) > 4090:
            await thinking_msg.delete()
            chunks = [answer[i:i+4080] for i in range(0, len(answer), 4080)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.reply(chunk)
                else:
                    await message.answer(chunk)
        else:
            await thinking_msg.edit_text(answer)

    except Exception as e:
        logger.error(f"Хабарды өңдеу қатесі: {e}", exc_info=True)
        await thinking_msg.edit_text("😔 Хабарды жіберу барысында қате шықты. Қайта көріңіз.")

async def main():
    """Басты функция"""
    logger.info("🚀 Бот іске қосылды!")
    logger.info(f"Рұқсат етілген топтар: {ALLOWED_CHAT_IDS}")
    logger.info(f"Модель: Gemini 2.5 Flash")

    # Қате шықса автоматты түрде қайта қосылады
    retry_delay = 10
    while True:
        try:
            await dp.start_polling(bot, skip_updates=True)
        except KeyboardInterrupt:
            logger.info("Бот тоқтатылды!")
            break
        except Exception as e:
            logger.error(f"Қосылым үзілді: {e} — {retry_delay} секундтан соң қайта қосыламын...", exc_info=True)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)  # Экспоненциалды кідіріс, max 5 минут

if __name__ == "__main__":
    # Pydroid 3-те экран өшсе де тоқтамауы үшін
    keep_thread = threading.Thread(target=keep_running, daemon=True)
    keep_thread.start()
    
    # Ботты іске қосу
    asyncio.run(main())
