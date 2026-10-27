from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    database_url: str = "sqlite:///./bodega.db"
    cors_origins: str = "https://bodega.local"
    app_timezone: str = "America/Bogota"
    log_file: str = "./logs/bodega.log"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
