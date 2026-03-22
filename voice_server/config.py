import os
from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    # --- Groq ---
    GROQ_API_KEY: SecretStr

    # --- Local service URLs ---

    # Kokoro TTS: neosun100/kokoro-tts Docker image
    # docker run --gpus all -p 8300:8300 neosun100/kokoro-tts
    KOKORO_WS_URL: str = "ws://localhost:8300/ws/tts"
    KOKORO_VOICE: str = "af_heart"  # change to preferred Kokoro voice ID

    # --- Django internal callback (FastAPI -> Django when session ends) ---
    DJANGO_CALLBACK_URL: str = "http://localhost:8000/mock-interview/end/"
    DJANGO_INTERNAL_SECRET: str = "change-this-to-something-strong"

    class Config:
        env_file = ".env"


settings = Settings()
