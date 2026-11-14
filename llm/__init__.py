import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from .prompts import REACHY_SYSTEM
load_dotenv()  # .env 의 GEMINI_API_KEY 읽기


def get_llm(question: str, model: str = "gemini-3.8-flash") -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(model=model, contents=question, config = types.GenerateContentConfig(system_instruction=REACHY_SYSTEM))
    return response.text
