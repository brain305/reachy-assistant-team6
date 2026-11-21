# 일기 전용 요청: JSON 형식, 대기 시간, 재시도 횟수를 명시한다.

import os

from .prompts import EMPATHY_SYSTEM

EMOTIONS = ["happy", "sad", "curious", "surprised", "comforting", "neutral"]
EMPATHY_SCHEMA = {
    'type': 'object',
    'properties': {
        'answer': {'type': 'string'},
        'emotion': {'type': 'string', 'enum': EMOTIONS},
        'intensity': {'type': 'number', 'minimum': 0, 'maximum': 1},
    },
    'required': ['answer', 'emotion', 'intensity'],
    'additionalProperties': False,
}


class IncompleteResponseError(ValueError):
    # 잘리거나 차단된 응답을 완성된 일기로 저장하지 않는다.
    pass


class GeminiGenerator:
    # 팀 모델 설정을 사용하며 응답에 포함된 실제 토큰 사용량만 집계한다.

    def __init__(self, model=None):
        # 공통 모듈과 같은 .env·모델을 사용한다. 이 시점에는 API를 호출하지 않는다.
        from llm import DEFAULT_MODEL
        self.model = model or DEFAULT_MODEL
        if not os.getenv('GEMINI_API_KEY'):
            raise RuntimeError('.env에 GEMINI_API_KEY를 설정해 주세요.')
        self.last_usage = None
        self.total_usage = dict(input=0, output=0, thinking=0, total=0)
        self.usage_responses = 0

    def __call__(self, prompt, system=None, *, response_schema=None):
        from google import genai
        from google.genai import types

        self.last_usage = None
        options = {'system_instruction': system, 'max_output_tokens': 4096}
        if response_schema is None and system == EMPATHY_SYSTEM:
            response_schema = EMPATHY_SCHEMA
        elif response_schema is not None:
            options["temperature"] = 0
        if response_schema is not None:
            options.update(response_mime_type="application/json", response_json_schema=response_schema)
        with genai.Client(api_key=os.environ['GEMINI_API_KEY'], http_options=types.HttpOptions(
            timeout=45000, retry_options=types.HttpRetryOptions(attempts=1),
        )) as client:
            response = client.models.generate_content(
                model=self.model, contents=prompt, config=types.GenerateContentConfig(**options))
        usage = response.usage_metadata
        if usage is not None and usage.total_token_count is not None:
            self.last_usage = dict(input=usage.prompt_token_count or 0, output=usage.candidates_token_count or 0,
                                   thinking=usage.thoughts_token_count or 0, total=usage.total_token_count)
            self.usage_responses += 1
            for key, count in self.last_usage.items():
                self.total_usage[key] += count
        candidates = response.candidates or []
        # MAX_TOKENS 등 부분 응답은 JSON뿐 아니라 일반 일기도 거부한다.
        if not candidates or candidates[0].finish_reason != 'STOP':
            raise IncompleteResponseError('Gemini response did not complete')
        if not response.text or not response.text.strip():
            raise IncompleteResponseError('Gemini response is empty')
        return response.text


def generate_text(prompt, system=None, *, model=None, response_schema=None):
    # SDK 초기화를 실제 요청 시점까지 미루는 기본 생성 함수다.
    return GeminiGenerator(model)(prompt, system, response_schema=response_schema)
