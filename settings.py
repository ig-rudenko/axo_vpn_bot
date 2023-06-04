import pathlib
from os import getenv

TOKEN = getenv("TG_BOT_TOKEN")
BASE_URL = getenv("BASE_URL")
PUBLIC_IP = getenv("PUBLIC_IP")

CERTIFICATE_PATH = getenv("CERTIFICATE_PATH")

WEB_SERVER_HOST = "127.0.0.1"
WEB_SERVER_PORT = 8888

BOT_PATH = f"/webhook/bot/{TOKEN[:23]}"

BASE_DIR = pathlib.Path(__file__).parent

TEMPLATE_DIR = BASE_DIR / "templates"
