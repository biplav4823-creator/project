import requests
from .config import OLLAMA_URL, OLLAMA_MODEL

def ask_ollama(prompt, system=None):
    messages = []

    if system:
        messages.append({"role": "system", "content": system})

    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]
