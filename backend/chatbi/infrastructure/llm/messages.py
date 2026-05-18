from typing import Dict


def system_message(content: str) -> Dict[str, str]:
    return {"role": "system", "content": content}


def user_message(content: str) -> Dict[str, str]:
    return {"role": "user", "content": content}


def assistant_message(content: str) -> Dict[str, str]:
    return {"role": "assistant", "content": content}
