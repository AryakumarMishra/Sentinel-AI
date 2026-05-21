import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    # Gemini Config
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # GitLab Partner Config
    GITLAB_PRIVATE_TOKEN: str = os.getenv("GITLAB_PRIVATE_TOKEN", "")
    GITLAB_BASE_URL: str = os.getenv("GITLAB_BASE_URL", "https://gitlab.com/api/v4")
    GITLAB_WEBHOOK_SECRET: str = os.getenv("GITLAB_WEBHOOK_SECRET", "super-secret-token")
    
    # Server Config
    ENV: str = os.getenv("ENV", "development") # development / production

    def validate(self):
        """Ensures your agent won't boot up missing critical environment keys."""
        missing_keys = []
        if not self.GOOGLE_API_KEY:
            missing_keys.append("GOOGLE_API_KEY")
        if not self.GITLAB_PRIVATE_TOKEN:
            missing_keys.append("GITLAB_PRIVATE_TOKEN")
            
        if missing_keys:
            raise ValueError(
                f"CRITICAL CONFIG ERROR: Missing environment variables: {', '.join(missing_keys)}. "
                "Please verify your .env file or Cloud Run environment configurations."
            )
        print("Environment settings validated successfully.")

settings = Settings()
