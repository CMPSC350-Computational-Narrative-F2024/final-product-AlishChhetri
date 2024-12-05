import os
from dotenv import dotenv_values

CONFIG = dotenv_values("../.env")

OPEN_AI_KEY = CONFIG.get("KEY") or os.environ.get("OPENAI_API_KEY")
OPEN_AI_ORG = CONFIG.get("ORG") or os.environ.get("OPENAI_ORG")

if not OPEN_AI_KEY or not OPEN_AI_ORG:
    raise ValueError("API Key or Organization key is missing!")