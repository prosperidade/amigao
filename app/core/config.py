from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Amigão do Meio Ambiente"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # DATABASE
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "amigao_db"
    POSTGRES_PORT: str = "5432"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # REDIS
    REDIS_URL: str = "redis://localhost:6379/0"
    REALTIME_EVENTS_CHANNEL: str = "amigao_events"
    
    # STORAGE (MinIO)
    MINIO_SERVER: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    
    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # EMAIL / SMTP (Mailtrap defaults for dev)
    SMTP_TLS: bool = True
    SMTP_PORT: int = 587
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@amigao.com"
    EMAILS_FROM_NAME: str = "Amigão do Meio Ambiente"
    CLIENT_PORTAL_URL: str = "http://localhost:3000/dashboard"
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://172.31.32.1:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = Settings()
