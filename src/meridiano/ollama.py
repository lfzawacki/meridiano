# Check ollama is reachable
import os

import requests

OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")


def check_ollama(host: str = OLLAMA_API_BASE) -> bool:
    """Check if the Ollama server is reachable."""
    try:
        response = requests.get(f"{host}/v1/models", timeout=5)
        if response.status_code == 200:
            print("[INFO] Ollama server is reachable.")
            return True
        else:
            print(f"[ERROR] Ollama server returned status code {response.status_code}.")
            return False
    except requests.RequestException as e:
        print(f"[ERROR] Could not connect to Ollama server: {e}")
        return False


if __name__ == "__main__":
    if check_ollama():
        print("Ollama server is up and running.")
    else:
        print("Ollama server is not reachable. Please ensure it is running.")
        exit(1)
    exit(0)
