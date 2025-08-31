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
        # Dictionary of server IDs to webhook URLs
        webhooks = {
            # Your main server - replace with your actual webhook URL
            1281605174556626994: "https://discord.com/api/webhooks/1410935185268015186/gGX8ofF1J_hiJkQV1s8Tx-AjUtjS1ubqtbXrEMzGc_NRWLG8ZNb4VBPlN55_boewc2AF",
            # Add friend servers here later:
            1411334276531880049: "https://discord.com/api/webhooks/1411334646150725754/C3UHmPoi79H2dQYjujZWxnmj-07cp4_ztHaDa3wb_IIFtAk24CNWsg7CZK21hTrkyYWX",
            991908158274539681: "https://discord.com/api/webhooks/1345386396600369263/54SNNfhUOaK0oLt6yI2nwlHzNWOnQFFZNRV2HIegGPReYdwIlZ4muqjhzCAArqrSe2xj",
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
        """Create a static crimson neon welcome banner"""
        try:
            # Download avatar
            avatar_response = requests.get(str(member.display_avatar.with_size(512).url))
            avatar_img = Image.open(BytesIO(avatar_response.content)).convert("RGBA")

            # Banner size
            width, height = 800, 400

            # Background: blurred avatar zoom (reduced blur from 25 → 10)
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

            # FONT LOADING - DEBUGGING VERSION
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            ]

            title_font = subtitle_font = None
            font_loaded = False

            for font_path in font_paths:
                try:
                    logger.info(f"Trying font path: {font_path}")
        
                    # Check if file exists
                    if os.path.exists(font_path):
                        logger.info(f"✅ Font exists: {font_path}")
            
                        # Try to load the font
                        title_font = ImageFont.truetype(font_path, 55)  
                        subtitle_font = ImageFont.truetype(font_path, 32)  
            
                        logger.info(f"🎉 SUCCESS: Loaded font: {font_path}")
                        font_loaded = True
                        break
                    else:
                        logger.warning(f"❌ Font does NOT exist: {font_path}")
            
                except Exception as e:
                    logger.error(f"💥 FAILED to load font {font_path}: {e}")
                    continue

            if not font_loaded:
                logger.error("💥 ALL FONT LOADING ATTEMPTS FAILED!")
                try:
                    # Try to create a larger default font
                    title_font = ImageFont.load_default(size=55)
                    subtitle_font = ImageFont.load_default(size=32)
                    logger.warning("⚠️ Using enlarged default font")
                except:
                    # Absolute last resort
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()
                    logger.error("💥 Using tiny default font")

            def draw_neon_text(banner, text, pos, font, base_color=(255, 255, 255), glow_color=(220, 20, 60)):
                draw = ImageDraw.Draw(banner)
                for blur_radius in [10, 6, 3]:
                    glow = Image.new("RGBA", banner.size, (0, 0, 0, 0))
                    glow_draw = ImageDraw.Draw(glow)
                    glow_draw.text(pos, text, font=font, fill=glow_color + (180,))
                    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
                    banner.alpha_composite(glow)
                
                offsets = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
                for offset_x, offset_y in offsets:
                    draw.text((pos[0] + offset_x, pos[1] + offset_y), text, font=font, fill=base_color)  # Slight offset for boldness

            # --- Create final static frame ---
            frame = bg.copy()

            # Paste avatar directly (no glow ring)
            frame.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

            # Neon text
            text_x = 320
            draw_neon_text(frame, "GREETINGS!", (text_x, 118), title_font,
                           base_color=(220, 20, 60), glow_color=(220, 20, 60))

            username = member.display_name
            if len(username) > 28:
                username = username[:25] + "..."
            draw_neon_text(frame, username, (text_x, 190), subtitle_font,
                           base_color=(250, 250, 250), glow_color=(200, 50, 200))

            member_text = f"Member #{len(member.guild.members)}"
            draw_neon_text(frame, member_text, (text_x, 240), subtitle_font,
                           base_color=(180, 180, 180), glow_color=(200, 50, 200))

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
            # Get the webhook URL for this specific server
            webhook_url = await self.get_webhook_for_guild(member.guild.id)
            if not webhook_url:
                logger.warning(f"No webhook configured for server: {member.guild.name}")
                return
                
            import random
            message = random.choice(WELCOME_MESSAGES).format(mention=member.mention)
            embed = {
                "title": "👋 Welcome to the server!",
                "description": message,
                "color": 0xDC143C,  # 🔴 Crimson side panel
                "footer": {
                    "text": f"Joined {datetime.utcnow().strftime('%B %d, %Y')}",
                    "icon_url": str(member.guild.icon.url) if member.guild.icon else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            # Send with the specific webhook URL for this server
            await self.send_welcome_webhook(embed, member, member.mention, webhook_url)
        except Exception as e:
            logger.error(f"Error in on_member_join: {e}")

    async def send_welcome_webhook(self, embed, member, mention_text=None, webhook_url=None):
        """Send webhook with custom webhook URL"""
        # Use provided webhook URL or fall back to default
        if webhook_url is None:
            webhook_url = self.config.webhook_url
            
        try:
            banner_buffer = self.create_welcome_banner(member)
            if banner_buffer:
                banner_buffer.seek(0)
                form_data = aiohttp.FormData()
                form_data.add_field('payload_json', json.dumps({
                    "content": mention_text,  # ← MENTION GOES HERE (outside embed)
                    "embeds": [{**embed, "image": {"url": "attachment://welcome_banner.png"}}]
                }))
                form_data.add_field('file', banner_buffer.read(), filename='welcome_banner.png', content_type='image/png')
                async with self.session.post(webhook_url, data=form_data) as response:  # ← Use the specific webhook URL
                    if response.status in (200, 204):
                        logger.info(f"Welcome message + banner sent for {member.display_name} in {member.guild.name}")
                    else:
                        logger.error(f"Failed to send webhook with banner: {response.status}")
            else:
                # fallback (no banner)
                webhook_data = {
                    "content": mention_text,  # ← MENTION GOES HERE (outside embed)
                    "embeds": [embed]
                }
                async with self.session.post(webhook_url, json=webhook_data) as response:  # ← Use the specific webhook URL
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
        "color": 0xDC143C,  # 🔴 Crimson side panel
        "thumbnail": {"url": str(ctx.author.display_avatar.url)},
        "footer": {
            "text": f"Test • Member #{len(ctx.guild.members)}",
            "icon_url": str(ctx.guild.icon.url) if ctx.guild.icon else None
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    # Get webhook for this server
    webhook_url = await bot.get_webhook_for_guild(ctx.guild.id)
    if not webhook_url:
        webhook_url = bot.config.webhook_url  # Fallback to default
    
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
