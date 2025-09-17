import os
import subprocess
import telebot
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Необходимо установить TELEGRAM_BOT_TOKEN и GEMINI_API_KEY в .env файле")

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

if not os.path.exists("downloads"):
    os.makedirs("downloads")
if not os.path.exists("transcripts"):
    os.makedirs("transcripts")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь мне аудиофайл в формате .m4a, и я сделаю краткую выжимку из него с помощью Gemini.")

@bot.message_handler(content_types=['document', 'audio', 'voice'])
def handle_audio(message):
    try:
        if message.document:
            if not message.document.file_name.endswith((".m4a", ".mp3", ".wav")):
                bot.reply_to(message, "Пожалуйста, отправьте аудиофайл с расширением .m4a, .mp3 или .wav")
                return
            file_info = bot.get_file(message.document.file_id)
        elif message.audio:
            file_info = bot.get_file(message.audio.file_id)
        elif message.voice:
            file_info = bot.get_file(message.voice.file_id)
        else:
            return

        bot.reply_to(message, "Аудио получено, начинаю обработку... Это может занять некоторое время.")

        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join("downloads", f"audio_{message.message_id}.m4a")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        whisper_command = [
            "whisper",
            file_path,
            "--model", "small",
            "--language", "ru",
            "--output_dir", "transcripts",
            "--output_format", "txt"
        ]

        base_audio_name = os.path.splitext(os.path.basename(file_path))[0]
        transcript_file_path = os.path.join("transcripts", f"{base_audio_name}.txt")

        subprocess.run(whisper_command, check=True, capture_output=True, text=True)

        with open(transcript_file_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read()

        if not transcript_text.strip():
            bot.reply_to(message, "Не удалось распознать речь в аудиофайле.")
            return

        bot.send_message(message.chat.id, "Текст успешно распознан. Создаю краткий отчет с помощью Gemini...")

        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
        summary_prompt = f"""Сделай краткую выжимку (summary) и выдели основные тезисы из следующего текста:\n\n{transcript_text}"""

        response = model.generate_content(summary_prompt)

        summary_text = response.text

        bot.reply_to(message, f"""**Краткий отчет:**\n\n{summary_text}""" )

    except subprocess.CalledProcessError as e:
        bot.reply_to(message, f"Произошла ошибка при обработке аудио: {e.stderr}")
    except Exception as e:
        bot.reply_to(message, f"Произошла непредвиденная ошибка: {e}")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'transcript_file_path' in locals() and os.path.exists(transcript_file_path):
            os.remove(transcript_file_path)


if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True, timeout=60)
