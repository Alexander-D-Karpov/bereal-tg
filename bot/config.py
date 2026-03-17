import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Config:
    bot_token: str
    data_file: str
    proxy_url: str | None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            data_file=os.getenv("DATA_FILE", "data/bot_data.json"),
            proxy_url=os.getenv("PROXY_URL"),
        )
