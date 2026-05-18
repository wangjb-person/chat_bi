from typing import Dict, Generator, List

from openai import OpenAI


class LlmClient:
    """OpenAI 兼容协议的大模型客户端（通义千问等）。"""

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def model(self) -> str:
        return self._model

    def complete(self, messages: List[Dict]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content

    def complete_stream(self, messages: List[Dict]) -> Generator[str, None, None]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
