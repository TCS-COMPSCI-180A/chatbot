from pydantic import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Chatbot Backend"
    VERSION: str = "0.1.0"
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
