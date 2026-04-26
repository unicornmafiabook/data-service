import os


class EmbeddingService:
    def __init__(self) -> None:
        self.provider = os.getenv("EMBEDDING_PROVIDER", "")
        self.model = os.getenv("EMBEDDING_MODEL", "")
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")

    def is_enabled(self) -> bool:
        return bool(self.provider and self.model and self.api_key)

    def embed_text(self, text: str) -> list[float] | None:
        if not self.is_enabled():
            return None
        return None
