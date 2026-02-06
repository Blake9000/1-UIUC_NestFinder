import environ
from pathlib import Path

#This imports key/value pairs from .env
env = environ.Env()


BASE_DIR = Path(__file__).resolve().parent.parent


environ.Env.read_env(BASE_DIR / ".env")