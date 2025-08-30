import os
from dotenv import load_dotenv

load_dotenv()
print("BOT_TOKEN:", os.getenv('BOT_TOKEN'))
print("WEBHOOK_URL:", os.getenv('WEBHOOK_URL'))
print("GUILD_ID:", os.getenv('GUILD_ID'))
