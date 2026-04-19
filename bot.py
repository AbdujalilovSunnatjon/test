import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import PollAnswer

import config
from quiz_parser import get_shuffled_questions, load_questions

logging.basicConfig(level=logging.INFO)

if not config.BOT_TOKEN:
    raise ValueError("Пожалуйста, укажите BOT_TOKEN в файле config.py или .env")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Хранилище сессий пользователей и маппинг poll_id -> user_id
user_sessions = {}
polls_map = {}

async def send_question(user_id: int, chat_id: int):
    session = user_sessions.get(user_id)
    if not session:
        return

    q_idx = session["current_index"]
    questions = session["questions"]

    if q_idx >= len(questions):
        await send_results(chat_id, session)
        del user_sessions[user_id]
        return

    question_data = questions[q_idx]
    
    # В Telegram длина вопроса ограничена 300 символами
    q_text = f"[{q_idx + 1}/{len(questions)}] {question_data['question']}"
    if len(q_text) > 300:
        q_text = q_text[:297] + "..."
        
    # В Telegram длина одного варианта ограничена 100 символами
    options = []
    for opt in question_data["options"]:
        if len(opt) > 100:
            options.append(opt[:97] + "...")
        else:
            options.append(opt)
            
    # Отправка Native Quiz Poll
    # is_anonymous=False обязателен для получения ответов пользователей в боте
    try:
        msg = await bot.send_poll(
            chat_id=chat_id,
            question=q_text,
            options=options,
            type="quiz",
            correct_option_id=question_data["correct_index"],
            is_anonymous=False,
            open_period=config.QUESTION_TIMER_SECONDS if config.QUESTION_TIMER_SECONDS > 0 else None
        )
        
        # Связываем poll_id с user_id для обработки ответа
        polls_map[msg.poll.id] = user_id
        session["current_message_id"] = msg.message_id
        session["current_poll_id"] = msg.poll.id
        
        # Если есть таймер, запускаем фоновую задачу для переключения вопроса,
        # если пользователь так и не ответил за отведенное время
        if config.QUESTION_TIMER_SECONDS > 0:
            if session.get("timer_task"):
                session["timer_task"].cancel()
            
            task = asyncio.create_task(timer_worker(user_id, chat_id, q_idx, msg.poll.id))
            session["timer_task"] = task
            
    except Exception as e:
        logging.error(f"Error sending poll: {e}")
        await bot.send_message(chat_id, f"Xatolik yuz berdi: {e}")


async def timer_worker(user_id: int, chat_id: int, question_index: int, poll_id: str):
    try:
        await asyncio.sleep(config.QUESTION_TIMER_SECONDS + 1)
        
        session = user_sessions.get(user_id)
        if session and session["current_index"] == question_index and session.get("current_poll_id") == poll_id:
            # Время вышло, пользователь не ответил. Сам опрос закроется автоматически Telegram'ом (open_period).
            await bot.send_message(chat_id, "⏳ <b>Vaqt tugadi!</b> Keyingi savolga o'tamiz.", parse_mode="HTML")
            
            # Переключаем на следующий
            session["current_index"] += 1
            await send_question(user_id, chat_id)

    except asyncio.CancelledError:
        pass


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    try:
        if config.SHUFFLE_QUESTIONS:
            questions = get_shuffled_questions("tests.txt")
        else:
            questions = load_questions("tests.txt")
    except Exception as e:
        logging.error(f"Error loading questions: {e}")
        await message.answer("Xatolik! Savollarni yuklab bo'lmadi.")
        return

    if not questions:
        await message.answer("Savollar fayli (tests.txt) bo'sh yoki noto'g'ri o'qildi.")
        return

    if user_sessions.get(user_id) and user_sessions[user_id].get("timer_task"):
        user_sessions[user_id]["timer_task"].cancel()

    user_sessions[user_id] = {
        "questions": questions,
        "current_index": 0,
        "correct_count": 0,
        "current_message_id": None,
        "current_poll_id": None,
        "timer_task": None
    }
    
    await message.answer(f"👋 Salom! Quiz (test) ga xush kelibsiz.\nJami savollar soni: {len(questions)}\nTestni istalgan vaqtda to'xtatish uchun /stop darcha bosing.\n\nBoshlaymizmi?")
    await asyncio.sleep(1)
    await send_question(user_id, message.chat.id)


@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session:
        await message.answer("Hozirda faol test yo'q. Boshlash uchun /start ni bosing.")
        return
        
    if session.get("timer_task"):
        session["timer_task"].cancel()
        session["timer_task"] = None
        
    await message.answer("🛑 Test to'xtatildi.")
    await send_results(message.chat.id, session)
    del user_sessions[user_id]


@dp.poll_answer()
async def poll_answer_handler(poll_answer: PollAnswer):
    user_id = poll_answer.user.id
    poll_id = poll_answer.poll_id
    
    mapped_user_id = polls_map.get(poll_id)
    if not mapped_user_id or mapped_user_id != user_id:
        return
        
    session = user_sessions.get(user_id)
    if not session or session.get("current_poll_id") != poll_id:
        return
        
    if session.get("timer_task"):
        session["timer_task"].cancel()
        session["timer_task"] = None

    q_idx = session["current_index"]
    questions = session["questions"]
    question_data = questions[q_idx]
    
    # Проверяем правильность ответа
    if len(poll_answer.option_ids) > 0:
        selected_option = poll_answer.option_ids[0]
        if selected_option == question_data["correct_index"]:
            session["correct_count"] += 1
            
    # Переход к следующему вопросу
    session["current_index"] += 1
    
    # Небольшая пауза, чтобы пользователь увидел "зеленую галочку" в самом Telegram опросчике
    await asyncio.sleep(2)
    # Отправляем следующий вопрос в приватный чат
    await send_question(user_id, user_id)


async def send_results(chat_id: int, session: dict):
    total = len(session["questions"])
    answered = session["current_index"]
    correct = session["correct_count"]
    
    text = (
        f"🏆 <b>Test yakunlandi!</b>\n\n"
        f"📝 Jami savollar: <b>{total}</b>\n"
        f"✅ Kiritilgan javoblar: <b>{answered}</b>\n"
        f"🎯 To'g'ri javoblar: <b>{correct}</b>\n"
    )
    
    percent = (correct / answered) * 100 if answered > 0 else 0
    if percent >= 80:
        text += "\n🌟 Ajoyib natija! Siz bu mavzuni yaxshi tushunasiz."
    elif percent >= 50:
        text += "\n👍 Yaxshi natija, lekin hali o'rganadigan narsalar bor."
    else:
        text += "\n📚 Ko'proq o'qish va tayyorlanish kerak."
        
    text += "\n\nYana qatnashish uchun /start ni bosing."
    
    await bot.send_message(chat_id, text, parse_mode="HTML")

if __name__ == "__main__":
    async def main():
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
        
    asyncio.run(main())
