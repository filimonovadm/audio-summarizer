import os
import telebot
import google.generativeai as genai
import whisper
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

print("Загрузка модели Whisper... Это может занять некоторое время.")
whisper_model = whisper.load_model("base")
print("Модель Whisper загружена.")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне аудиофайл, и я сделаю краткую выжимку из него с помощью Gemini.")

@bot.message_handler(content_types=['document', 'audio', 'voice'])
def handle_audio(message):
    file_path = None
    try:
        if message.document:
            if not message.document.file_name.endswith((".m4a", ".mp3", ".wav", ".ogg")):
                bot.reply_to(message, "Пожалуйста, отправьте аудиофайл с расширением .m4a, .mp3, .wav или .ogg")
                return
            file_info = bot.get_file(message.document.file_id)
        elif message.audio:
            file_info = bot.get_file(message.audio.file_id)
        elif message.voice:
            file_info = bot.get_file(message.voice.file_id)
        else:
            return

        duration = None
        if message.audio:
            duration = message.audio.duration
        elif message.voice:
            duration = message.voice.duration

        processing_message = "Аудио получено, начинаю обработку..."
        if duration:
            estimated_seconds = duration * 2
            minutes = estimated_seconds // 60
            seconds = estimated_seconds % 60
            processing_message += f" Примерное время ожидания: {minutes} мин. {seconds} сек."

        bot.reply_to(message, processing_message)

        downloaded_file = bot.download_file(file_info.file_path)
        file_ext = file_info.file_path.split('.')[-1]
        file_path = f"audio_{message.message_id}.{file_ext}"
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        result = whisper_model.transcribe(file_path, fp16=False, language="ru")
        transcript_text = result['text']

        if not transcript_text.strip():
            bot.reply_to(message, "Не удалось распознать речь в аудиофайле.")
            return

        bot.send_message(message.chat.id, "Текст обработан, создаю краткий отчет...")
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

        correction_prompt = f"""Исправь грамматические и орфографические ошибки в следующем тексте, который был получен после автоматического распознавания речи. Восстанови логику и смысл, если они нарушены. Не добавляй ничего нового, только исправляй существующий текст. Вот текст:

{transcript_text}"""
        correction_response = model.generate_content(correction_prompt)
        corrected_text = correction_response.text

        summary_prompt = f"""Сделай краткую выжимку (summary) и выдели основные тезисы из следующего текста:

{corrected_text}"""
        summary_response = model.generate_content(summary_prompt)
        summary_text = summary_response.text

        bot.reply_to(message, f"""**Краткий отчет:**

{summary_text}""" )

    except Exception as e:
        bot.reply_to(message, f"Произошла непредвиденная ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True, timeout=60)
