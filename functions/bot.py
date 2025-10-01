import os
import telebot
import google.generativeai as genai
import logging

# Note that 'whisper' is NOT imported here at the top level.

# Configure logging to standard output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialize the bot with a dummy token. The real token will be set at runtime.
bot = telebot.TeleBot("123:DUMMY_TOKEN")

# Global variables for models to ensure they are loaded only once
whisper_model = None
generative_model = None

def get_whisper_model():
    """Initializes and returns the Whisper model, loading it only once."""
    global whisper_model
    if whisper_model is None:
        # Lazy import whisper here, inside the function.
        import whisper
        print("Загрузка модели Whisper... Это может занять некоторое время.")
        # Using the tiny model to ensure successful deployment.
        # This can be changed to 'base' or 'medium' later.
        whisper_model = whisper.load_model("tiny")
        print("Модель Whisper загружена.")
    return whisper_model

def get_generative_model():
    """Initializes and returns the Gemini model, loading it only once."""
    global generative_model
    if generative_model is None:
        print("Инициализация модели Gemini...")
        generative_model = genai.GenerativeModel('gemini-1.0-pro-latest')
        print("Модель Gemini инициализирована.")
    return generative_model

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user = message.from_user
    logging.info(f"User {user.id} ({user.username}) started the bot. Name: {user.first_name} {user.last_name}")
    bot.reply_to(message, "Привет! Отправь мне аудиофайл, и я сделаю краткую выжимку из него с помощью Gemini.")

@bot.message_handler(content_types=['document', 'audio', 'voice'])
def handle_audio(message):
    user = message.from_user
    logging.info(f"User {user.id} ({user.username}) sent a file. Name: {user.first_name} {user.last_name}")
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
        # Write to the /tmp directory, which is writable in serverless environments.
        file_path = f"/tmp/audio_{message.message_id}.{file_ext}"
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        # Lazily load the model on first use
        transcriber = get_whisper_model()
        result = transcriber.transcribe(file_path, fp16=False, language="ru")
        transcript_text = result['text']

        if not transcript_text.strip():
            bot.reply_to(message, "Не удалось распознать речь в аудиофайле.")
            return

        bot.send_message(message.chat.id, "Текст обработан, создаю краткий отчет...")
        
        # Lazily load the model on first use
        model = get_generative_model()

        correction_prompt = f'''Исправь грамматические и орфографические ошибки в следующем тексте, который был получен после автоматического распознавания речи. Восстанови логику и смысл, если они нарушены. Не добавляй ничего нового, только исправляй существующий текст. Вот текст:

{transcript_text}'''
        correction_response = model.generate_content(correction_prompt)
        corrected_text = correction_response.text

        summary_prompt = f'''Сделай краткую выжимку (summary) и выдели основные тезисы из следующего текста:

{corrected_text}'''
        summary_response = model.generate_content(summary_prompt)
        summary_text = summary_response.text

        bot.reply_to(message, f'''**Краткий отчет:**

{summary_text}''')

    except Exception as e:
        logging.error(f"Error processing file for user {user.id}: {e}")
        bot.reply_to(message, f"Произошла непредвиденная ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
