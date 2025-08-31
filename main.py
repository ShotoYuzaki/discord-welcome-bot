import discord
from discord.ext import commands
from discord import File
import aiohttp
import asyncio
import os
import json
from datetime import datetime
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
from dotenv import load_dotenv

# Load the secret token from the .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WelcomeBot')

# Bot configuration
class Config:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        
    def validate(self):
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")
        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL environment variable is required")
        return True

# Custom welcome messages
WELCOME_MESSAGES = [
   "Welcome! Glad you made it here!",
   "Yo! Welcome to our server!",
   "LET'S GOOO! Has joined the gang!",
   "It's so good to have you here!",
   "Welcome! Great to have you here!"
]

class WelcomeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        super().__init__(
            command_prefix='!wb_',
            intents=intents,
            help_command=None
        )
        
        self.config = Config()
        self.session = None
        
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        logger.info("Bot is starting up...")

    async def get_webhook_for_guild(self, guild_id):
        """Get webhook URL for a specific server"""
        webhooks = {
            1281605174556626994: "https://discord.com/api/webhooks/1410935185268015186/gGX8ofF1J_hiJkQV1s8Tx-AjUtjS1ubqtbXrEMzGc_NRWLG8ZNb4VBPlN55_boewc2AF",
            1411334276531880049: "https://discord.com/api/webhooks/1411334646150725754/C3UHmPoi79H2dQYjujZWxnmj-07cp4_ztHaDa3wb_IIFtAk24CNWsg7CZK21hTrkyYWX",
        }
        return webhooks.get(guild_id)

    async def on_ready(self):
        logger.info(f'{self.user} has landed!')
        logger.info(f'Connected to {len(self.guilds)} server(s)')
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for new members 👀"
            )
        )

    def create_welcome_banner(self, member):
        """Create a static crimson welcome banner (no glow)"""
        try:
            # Download avatar
            avatar_response = requests.get(str(member.display_avatar.with_size(512).url))
            avatar_img = Image.open(BytesIO(avatar_response.content)).convert("RGBA")

            # Banner size
            width, height = 800, 400

            # Background: blurred avatar zoom
            bg = avatar_img.resize((width, height), Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(10))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
            bg.paste(overlay, (0, 0), overlay)

            # Foreground avatar (circle)
            avatar_size = 200
            avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)

            circular_avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
            circular_avatar.paste(avatar_img, (0, 0))
            circular_avatar.putalpha(mask)

            avatar_x = 80
            avatar_y = (height - avatar_size) // 2

            # FONT LOADING
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            ]

            title_font = subtitle_font = None
            font_loaded = False

            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        title_font = ImageFont.truetype(font_path, 80)   # Bigger title
                        subtitle_font = ImageFont.truetype(font_path, 45) # Bigger subtitle
                        font_loaded = True
                        break
                except Exception:
                    continue

            if not font_loaded:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()

            def draw_clean_text(banner, text, pos, font, fill=(255, 255, 255)):
                draw = ImageDraw.Draw(banner)
                draw.text(pos, text, font=font, fill=fill)

            # --- Create final static frame ---
            frame = bg.copy()

            # Paste avatar
            frame.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

            # Title (sharp crimson red, no glow)
            text_x = 320
            draw_clean_text(frame, "GREETINGS!", (text_x, 90), title_font, fill=(255, 0, 60))

            # Username (white)
            username = member.display_name
            if len(username) > 15:
                username = username[:12] + "..."
            draw_clean_text(frame, username, (text_x, 170), subtitle_font, fill=(255, 255, 255))

            # Member number (greyish)
            member_text = f"Member #{len(member.guild.members)}"
            draw_clean_text(frame, member_text, (text_x, 220), subtitle_font, fill=(200, 200, 200))

            # Save PNG
            img_buffer = BytesIO()
            frame.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            return img_buffer

        except Exception as e:
            logger.error(f"Error creating welcome banner: {e}")
            return None

    async def on_member_join(self, member):
        logger.info(f"on_member_join fired for {member.display_name} in {member.guild.name}")
        try:
            webhook_url = await self.get_webhook_for_guild(member.guild.id)
            if not webhook_url:
                logger.warning(f"No webhook configured for server: {member.guild.name}")
                return
                
            import random
            message = random.choice(WELCOME_MESSAGES).format(mention=member.mention)
            embed = {
                "title": "👋 Welcome to the server!",
                "description": message,
                "color": 0xDC143C,
                "footer": {
                    "text": f"Joined {datetime.utcnow().strftime('%B %d, %Y')}",
                    "icon_url": str(member.guild.icon.url) if member.guild.icon else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.send_welcome_webhook(embed, member, member.mention, webhook_url)
        except Exception as e:
            logger.error(f"Error in on_member_join: {e}")

    async def send_welcome_webhook(self, embed, member, mention_text=None, webhook_url=None):
        if webhook_url is None:
            webhook_url = self.config.webhook_url
            
        try:
            banner_buffer = self.create_welcome_banner(member)
            if banner_buffer:
                banner_buffer.seek(0)
                form_data = aiohttp.FormData()
                form_data.add_field('payload_json', json.dumps({
                    "content": mention_text,
                    "embeds": [{**embed, "image": {"url": "attachment://welcome_banner.png"}}]
                }))
                form_data.add_field('file', banner_buffer.read(), filename='welcome_banner.png', content_type='image/png')
                async with self.session.post(webhook_url, data=form_data) as response:
                    if response.status in (200, 204):
                        logger.info(f"Welcome message + banner sent for {member.display_name} in {member.guild.name}")
                    else:
                        logger.error(f"Failed to send webhook with banner: {response.status}")
            else:
                webhook_data = {
                    "content": mention_text,
                    "embeds": [embed]
                }
                async with self.session.post(webhook_url, json=webhook_data) as response:
                    if response.status in (200, 204):
                        logger.info(f"Welcome message (no banner) sent for {member.display_name} in {member.guild.name}")
                    else:
                        logger.error(f"Failed to send webhook: {response.status}")
        except Exception as e:
            logger.error(f"Error sending webhook: {e}")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

# ✅ Test command
@commands.command(name='test_welcome')
@commands.has_permissions(administrator=True)
async def test_welcome(ctx):
    bot = ctx.bot
    logger.info("!wb_test_welcome command triggered")
    embed = {
        "title": "Test Welcome Message",
        "description": "This is a test!",
        "color": 0xDC143C,
        "thumbnail": {"url": str(ctx.author.display_avatar.url)},
        "footer": {
            "text": f"Test • Member #{len(ctx.guild.members)}",
            "icon_url": str(ctx.guild.icon.url) if ctx.guild.icon else None
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    webhook_url = await bot.get_webhook_for_guild(ctx.guild.id)
    if not webhook_url:
        webhook_url = bot.config.webhook_url  
    
    await bot.send_welcome_webhook(embed, ctx.author, ctx.author.mention, webhook_url)
    await ctx.message.delete()

def main():
    bot = WelcomeBot()
    try:
        bot.config.validate()
        bot.add_command(test_welcome)
        bot.run(bot.config.bot_token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
