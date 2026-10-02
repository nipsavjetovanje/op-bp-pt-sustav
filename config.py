import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Minimalni .env loader — bez vanjskih ovisnosti."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env()


def _get_secret(key: str, default: str = "") -> str:
    """Na Streamlit Cloudu vrijednost dolazi iz st.secrets (postavlja se u
    sučelju, nikad u kodu/repozitoriju). Lokalno (ova sesija) čita se iz .env."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY", "")
MODEL = _get_secret("ANTHROPIC_MODEL", "claude-sonnet-5-5")
