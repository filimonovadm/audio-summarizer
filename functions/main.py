import os
from firebase_functions import https_fn, options
from firebase_admin import initialize_app
import telebot
import google.generativeai as genai
# Import the bot object AND the handler functions directly
from bot import bot, send_welcome, handle_audio

initialize_app()

# A flag to ensure that services are initialized only once per function instance.
_initialized = False

def initialize_services():
    """Initializes external services like the Gemini API. This function
    is called once per function instance, after the secrets are available."""
    global _initialized
    if not _initialized:
        print("Initializing services...")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY secret not found in environment")
        genai.configure(api_key=api_key)
        _initialized = True
        print("Services initialized.")

@https_fn.on_request(
    secrets=["TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY"],
    memory=options.MemoryOption.GB_2,
    timeout_sec=300
)
def audio_summarizer(req: https_fn.Request) -> https_fn.Response:
    """Firebase Function entry point."""
    # Set the bot token from the environment secrets.
    bot.token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    # Initialize services like Gemini API configuration.
    initialize_services()

    if req.method == "POST":
        try:
            json_string = req.get_data(as_text=True)
            update = telebot.types.Update.de_json(json_string)
            
            # --- Synchronous, manual dispatch logic ---
            if update.message:
                # Check for commands like /start or /help
                if update.message.text and update.message.text.startswith('/'):
                    print(f"--- Manually calling send_welcome for command: {update.message.text} ---")
                    send_welcome(update.message)
                # Check for audio, voice, or document content types
                elif update.message.content_type in ['audio', 'voice', 'document']:
                    print(f"--- Manually calling handle_audio for content_type: {update.message.content_type} ---")
                    handle_audio(update.message)
            
            print("--- Finished manual dispatch. ---")
            return https_fn.Response("ok", status=200)
        except Exception as e:
            print(f"!!! Error processing update: {e}")
            return https_fn.Response("error", status=500)
    else:
        # Handle GET requests, for example, to check if the bot is running.
        return https_fn.Response("Bot is running.", status=200)