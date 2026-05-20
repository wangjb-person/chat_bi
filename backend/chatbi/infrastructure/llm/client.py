from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI


class LlmClient:
    """OpenAI 兼容协议的大模型客户端（通义千问等）。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.1,
        top_p: float = 0.85,
        top_k: Optional[int] = 10,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._top_k = top_k
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def model(self) -> str:
        return self._model

    def _create_kwargs(self, *, stream: bool = False) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": self._model,
            "temperature": self._temperature,
            "top_p": self._top_p,
        }
        if stream:
            kwargs["stream"] = True
        # top_k 非 OpenAI 标准字段，通义等通过 extra_body 传递
        if self._top_k is not None:
            extra = dict(kwargs.get("extra_body") or {})
            extra["top_k"] = self._top_k
            kwargs["extra_body"] = extra
        return kwargs

    def complete(self, messages: List[Dict]) -> str:
        kwargs = self._create_kwargs()
        kwargs["messages"] = messages
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def complete_stream(self, messages: List[Dict]) -> Generator[str, None, None]:
        kwargs = self._create_kwargs(stream=True)
        kwargs["messages"] = messages
        response = self._client.chat.completions.create(**kwargs)
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
