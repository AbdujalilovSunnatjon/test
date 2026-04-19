import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SHUFFLE_QUESTIONS = os.getenv("SHUFFLE_QUESTIONS", "True").lower() in ("true", "1", "yes")
QUESTION_TIMER_SECONDS = int(os.getenv("QUESTION_TIMER_SECONDS", 90))
