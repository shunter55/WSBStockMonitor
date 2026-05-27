from wsb_monitor.client.gemini import GeminiClient
from wsb_monitor.config import GeminiSettings


def create_gemini_client(settings: GeminiSettings) -> GeminiClient:
    return GeminiClient(settings)
