import discord
from discord.ext import commands
from discord import File
from discord import app_commands
import aiohttp
import asyncio
import os
import json
import random
from datetime import datetime
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
from dotenv import load_dotenv

# -----------------------
# Load env + logging
# -----------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WelcomeBot')

# -----------------------
# Config
# -----------------------
class Config:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.webhook_url = os.getenv('WEBHOOK_URL', None)

    def validate(self):
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")
        return True

# -----------------------
# Storage paths
# -----------------------
PERSISTENT_PATH = os.getenv("PERSISTENT_STORAGE_PATH", ".")
os.makedirs(PERSISTENT_PATH, exist_ok=True)
WELCOME_FILE = os.path.join(PERSISTENT_PATH, "welcome_messages.json")
SENT_EMBEDS_FILE = os.path.join(PERSISTENT_PATH, "sent_embeds.json")

# -----------------------
# Helper: JSON persistence
# -----------------------
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")

welcome_messages = load_json(WELCOME_FILE, {})
sent_embeds = load_json(SENT_EMBEDS_FILE, {})

# -----------------------
# Multi-guild welcome channels
# -----------------------
WELCOME_CHANNELS = {
    1281605174556626994: 1410934962412195922,  # Guild A -> Channel A (My Server)
    991908158274539681: 991943909565550643,   # Guild B -> Channel B (Enchanted Squad)
}

def get_welcome_channel_id(guild_id: int):
    return WELCOME_CHANNELS.get(guild_id)

# -----------------------
# Default messages
# -----------------------
DEFAULT_MESSAGES = [
   "Welcome! {mention} glad you made it here!",
   "Yo {mention}! Welcome to our server!",
   "Let's gooo! {mention} has joined the gang!",
   "It's so good to have you here {mention}!",
   "Welcome {mention}! Great to have you here!"
]

def get_guild_messages(guild_id: int):
    guild_id_str = str(guild_id)
    if guild_id_str in welcome_messages and welcome_messages[guild_id_str]:
        return welcome_messages[guild_id_str].copy()  # Return a copy to avoid modification
    return DEFAULT_MESSAGES.copy()  # Always return a copy of defaults

# -----------------------
# Bot
# -----------------------
class WelcomeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        # Slash-only bot: use a dummy callable prefix to prevent crashes
        super().__init__(command_prefix=lambda bot, msg: [], intents=intents, help_command=None)
        self.config = Config()
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        try:
            await self.tree.sync()
            logger.info("Slash commands synced.")
        except Exception as e:
            logger.warning(f"Failed to auto-sync slash commands: {e}")
        logger.info("Bot setup complete.")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = WelcomeBot()

# -----------------------
# Banner generator
# -----------------------
def create_welcome_banner(member: discord.Member):
    try:
        avatar_response = requests.get(str(member.display_avatar.with_size(512).url))
        avatar_img = Image.open(BytesIO(avatar_response.content)).convert("RGBA")

        width, height = 800, 400
        bg = avatar_img.resize((width, height), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(15))
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        bg.paste(overlay, (0, 0), overlay)

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

        font_paths = [
        "fonts/DejaVuSans-Bold.ttf",  # Your local font file
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Keep as backup
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

        title_font = subtitle_font = None
        for fp in font_paths:
            try:
                if os.path.exists(fp):
                    title_font = ImageFont.truetype(fp, 55)
                    subtitle_font = ImageFont.truetype(fp, 32)
                    break
            except Exception:
                continue
        if not title_font:
            title_font = subtitle_font = ImageFont.load_default()

        def draw_neon_text(banner, text, pos, font, base_color=(255,255,255), glow_color=(220,20,60)):
            draw = ImageDraw.Draw(banner)
            for blur_radius in [5]:
                glow = Image.new("RGBA", banner.size, (0,0,0,0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.text(pos, text, font=font, fill=glow_color + (120,))
                glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
                banner.alpha_composite(glow)
                draw.text(pos, text, font=font, fill=base_color)

        frame = bg.copy()
        frame.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)
        text_x = 320
        draw_neon_text(frame, "GREETINGS!", (text_x, 118), title_font, base_color=(220,20,60), glow_color=(220,20,60))
        username = member.display_name
        if len(username) > 28:
            username = username[:25] + "..."
        draw_neon_text(frame, username, (text_x, 190), subtitle_font, base_color=(250,250,250), glow_color=(200,50,200))
        member_text = f"Member #{len(member.guild.members)}"
        draw_neon_text(frame, member_text, (text_x, 240), subtitle_font, base_color=(180,180,180), glow_color=(200,50,200))

        img_buffer = BytesIO()
        frame.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Error creating welcome banner: {e}")
        return None
# -----------------------
# Welcome event
# -----------------------
@bot.event
async def on_member_join(member: discord.Member):
    logger.info(f"on_member_join fired for {member.display_name} in {member.guild.name}")
    try:
        channel_id = get_welcome_channel_id(member.guild.id)
        if not channel_id:
            logger.warning(f"No configured welcome channel for guild {member.guild.id}. Add it to WELCOME_CHANNELS in code.")
            return
        channel = member.guild.get_channel(channel_id)
        if not channel:
            logger.warning(f"Configured welcome channel ID {channel_id} not found in guild.")
            return

        msgs = get_guild_messages(member.guild.id)
        template = random.choice(msgs)
        content_mention = template.format(mention=member.mention, username=member.name, server=member.guild.name)

        embed = discord.Embed(
            title="👋 Welcome to the server!",
            description=content_mention,
            color=0xDC143C,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Joined {datetime.utcnow().strftime('%B %d, %Y')}",
                         icon_url=str(member.guild.icon.url) if member.guild.icon else None)

        banner_buffer = create_welcome_banner(member)
        if banner_buffer:
            banner_buffer.seek(0)
            file = File(banner_buffer, filename="welcome_banner.png")
            embed.set_image(url="attachment://welcome_banner.png")
            await channel.send(content=member.mention, embed=embed, file=file)
        else:
            await channel.send(content=member.mention, embed=embed)

    except Exception as e:
        logger.error(f"Error in on_member_join: {e}")

# -----------------------
# Slash commands: welcome message management
# -----------------------
@bot.tree.command(name="add_welcome", description="Add a welcome message (admin only). Use {mention}, {username}, {server}")
@app_commands.checks.has_permissions(administrator=True)
async def add_welcome(interaction: discord.Interaction, message: str):
    guild_id = str(interaction.guild.id)
    # Get current messages or create empty list if none exist
    current_messages = welcome_messages.get(guild_id, [])
    current_messages.append(message)
    welcome_messages[guild_id] = current_messages
    save_json(WELCOME_FILE, welcome_messages)
    await interaction.response.send_message("✅ Welcome message added.", ephemeral=True)

@bot.tree.command(name="list_welcome", description="List welcome messages for this server")
@app_commands.checks.has_permissions(administrator=True)
async def list_welcome(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    msgs = welcome_messages.get(guild_id, get_guild_messages(interaction.guild.id))
    if not msgs:
        await interaction.response.send_message("No welcome messages set.", ephemeral=True)
        return
    text = "\n".join([f"{i+1}. {m}" for i,m in enumerate(msgs)])
    await interaction.response.send_message(f"📜 Welcome messages:\n{text}", ephemeral=True)

@bot.tree.command(name="remove_welcome", description="Remove a welcome message by index (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def remove_welcome(interaction: discord.Interaction, index: int):
    guild_id = str(interaction.guild.id)
    msgs = welcome_messages.get(guild_id, get_guild_messages(interaction.guild.id))
    if index < 1 or index > len(msgs):
        await interaction.response.send_message("❌ Invalid index.", ephemeral=True)
        return
    removed = msgs.pop(index-1)
    welcome_messages[guild_id] = msgs
    save_json(WELCOME_FILE, welcome_messages)
    await interaction.response.send_message(f"Removed: `{removed}`", ephemeral=True)

@bot.tree.command(name="edit_welcome", description="Edit a welcome message by index (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def edit_welcome(interaction: discord.Interaction, index: int, new_text: str):
    guild_id = str(interaction.guild.id)
    msgs = welcome_messages.get(guild_id, get_guild_messages(interaction.guild.id))
    if index < 1 or index > len(msgs):
        await interaction.response.send_message("❌ Invalid index.", ephemeral=True)
        return
    old = msgs[index-1]
    msgs[index-1] = new_text
    welcome_messages[guild_id] = msgs
    save_json(WELCOME_FILE, welcome_messages)
    await interaction.response.send_message(f"✅ Edited message {index}.\nBefore: `{old}`\nAfter: `{new_text}`", ephemeral=True)

# -----------------------
# Test welcome
# -----------------------
@bot.tree.command(name="test_welcome", description="Send a test welcome message to the configured welcome channel (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def test_welcome(interaction: discord.Interaction, member: discord.Member = None):
    # Defer the response immediately to avoid the timeout
    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        member = member or interaction.user
        guild = interaction.guild
        channel_id = get_welcome_channel_id(guild.id)
        if not channel_id:
            await interaction.followup.send("❌ No welcome channel configured in the code. Add it to WELCOME_CHANNELS variable.", ephemeral=True)
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("❌ Configured welcome channel not found in this server.", ephemeral=True)
            return

        # Use the same flow as on_member_join but with specified member
        msgs = get_guild_messages(guild.id)
        template = random.choice(msgs)
        content_mention = template.format(mention=member.mention, username=member.name, server=guild.name)

        embed = discord.Embed(
            title="👋 Test Welcome",
            description=content_mention,
            color=0xDC143C,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Test • {datetime.utcnow().strftime('%B %d, %Y')}",
                         icon_url=str(guild.icon.url) if guild.icon else None)

        banner_buffer = create_welcome_banner(member)
        if banner_buffer:
            file = File(banner_buffer, filename="welcome_banner.png")
            embed.set_image(url="attachment://welcome_banner.png")
            await channel.send(content=member.mention, embed=embed, file=file)
        else:
            await channel.send(content=member.mention, embed=embed)

        await interaction.followup.send("✅ Test welcome sent.", ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error in test_welcome command: {e}")
        try:
            await interaction.followup.send("❌ Failed to send test welcome. See logs.", ephemeral=True)
        except:
            # If even the followup fails, we can't do much
            pass

# -----------------------
# Create embed modal & helper
# -----------------------

class CreateEmbedModal(discord.ui.Modal, title="Create Image Embeds"):
    # Main embed fields (2 fields)
    title_input = discord.ui.TextInput(label="Title (optional)", style=discord.TextStyle.short, required=False, max_length=256)
    description_input = discord.ui.TextInput(label="Description (optional)", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    
    # Image URLs for multiple embeds - COMBINED INTO 1 FIELD
    images_input = discord.ui.TextInput(
        label="Image URLs (one per line)", 
        style=discord.TextStyle.paragraph, 
        required=False, 
        max_length=2000, 
        placeholder="https://example.com/image1.jpg\nhttps://example.com/image2.jpg\nhttps://example.com/image3.jpg"
    )
    
    # Common fields (2 fields)
    footer_input = discord.ui.TextInput(label="Footer text (optional)", style=discord.TextStyle.short, required=False, max_length=2048)
    extra_content_input = discord.ui.TextInput(label="Message content (optional)", style=discord.TextStyle.paragraph, required=False, max_length=2000)

    def __init__(self, callback_data: dict):
        super().__init__()
        self.callback_data = callback_data

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Parse multiple image URLs from the text area
        image_urls = []
        if self.images_input.value.strip():
            image_urls = [url.strip() for url in self.images_input.value.split('\n') if url.strip()]
        
        data = self.callback_data.copy()
        data.update({
            "title": self.title_input.value.strip(),
            "description": self.description_input.value.strip(),
            "image_urls": image_urls,  # Use the parsed list
            "footer_text": self.footer_input.value.strip(),
            "extra_content": self.extra_content_input.value.strip()
        })
        try:
            await process_create_embed(interaction, data)
        except Exception as e:
            logger.exception("Failed to process embed creation")
            await interaction.followup.send("❌ Failed to create embed. See logs.", ephemeral=True)

            
# -----------------------
# Helper: parse color hex or name (IMPROVED VERSION)
# -----------------------
def parse_color(s: str):
    if not s:
        return 0xDC143C  # Default crimson
    
    s = s.strip().lower()
    
    # Remove # if present
    if s.startswith("#"):
        s = s[1:]
    
    # Try to parse as hex first
    try:
        if len(s) == 6:  # Regular hex
            return int(s, 16)
        elif len(s) == 3:  # Short hex (like fff -> ffffff)
            return int(s[0]*2 + s[1]*2 + s[2]*2, 16)
    except ValueError:
        pass  # Not a hex value, try color names
    
    # Extended color dictionary with common colors
    color_dict = {
        # Basic colors
        "red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
        "yellow": 0xFFFF00, "orange": 0xFFA500, "purple": 0x800080,
        "pink": 0xFFC0CB, "brown": 0xA52A2A, "black": 0x000000,
        "white": 0xFFFFFF, "gray": 0x808080, "grey": 0x808080,
        
        # Discord colors
        "blurple": 0x5865F2, "discord": 0x5865F2,
        "crimson": 0xDC143C, "dark_theme": 0x36393F,
        
        # Additional common colors
        "cyan": 0x00FFFF, "magenta": 0xFF00FF, "lime": 0x00FF00,
        "maroon": 0x800000, "navy": 0x000080, "olive": 0x808000,
        "teal": 0x008080, "silver": 0xC0C0C0, "gold": 0xFFD700,
        "violet": 0xEE82EE, "indigo": 0x4B0082, "coral": 0xFF7F50,
        "turquoise": 0x40E0D0, "salmon": 0xFA8072, "aqua": 0x00FFFF,
        "fuchsia": 0xFF00FF, "khaki": 0xF0E68C, "lavender": 0xE6E6FA,
        "plum": 0xDDA0DD, "orchid": 0xDA70D6, "azure": 0xF0FFFF,
        "beige": 0xF5F5DC, "bisque": 0xFFE4C4, "chocolate": 0xD2691E,
        "cornsilk": 0xFFF8DC, "firebrick": 0xB22222, "gainsboro": 0xDCDCDC,
        "ghostwhite": 0xF8F8FF, "honeydew": 0xF0FFF0, "ivory": 0xFFFFF0,
        "linen": 0xFAF0E6, "mintcream": 0xF5FFFA, "mistyrose": 0xFFE4E1,
        "moccasin": 0xFFE4B5, "oldlace": 0xFDF5E6, "peru": 0xCD853F,
        "seashell": 0xFFF5EE, "sienna": 0xA0522D, "snow": 0xFFFAFA,
        "tan": 0xD2B48C, "thistle": 0xD8BFD8, "tomato": 0xFF6347,
        "wheat": 0xF5DEB3, "whitesmoke": 0xF5F5F5,
        
        # Discord brand colors
        "discord_red": 0xED4245, "discord_green": 0x57F287,
        "discord_yellow": 0xFEE75C, "discord_blurple": 0x5865F2,
        "discord_fuchsia": 0xEB459E, "discord_white": 0xFFFFFF,
        "discord_black": 0x000000, "discord_gray": 0x36393F,
    }
    
    # Try to find the color in the dictionary
    if s in color_dict:
        return color_dict[s]
    
    # Try to parse as RGB tuple (r,g,b)
    if s.startswith("(") and s.endswith(")"):
        try:
            rgb = s[1:-1].split(",")
            if len(rgb) == 3:
                r = int(rgb[0].strip())
                g = int(rgb[1].strip())
                b = int(rgb[2].strip())
                return (r << 16) + (g << 8) + b
        except (ValueError, IndexError):
            pass
    
    # Default to crimson if no valid color found
    return 0xDC143C

# -----------------------
# Helper: build embed from data (and parse fields)
# -----------------------
def build_embed_from_data(data: dict, image_url: str = None):
    color = parse_color(data.get("color"))
    
    embed = discord.Embed(
        title=data.get("title") or None,  # CHANGED THIS LINE
        description=data.get("description") or None,  # CHANGED THIS LINE
        color=color,
        timestamp=datetime.utcnow() if data.get("timestamp_on") else None
    )
    
    # Set image if provided
    
    if image_url:
        embed.set_image(url=image_url)
    
    if data.get("thumbnail_url"):
        embed.set_thumbnail(url=data.get("thumbnail_url"))
    if data.get("author_name"):
        if data.get("author_icon_url"):
            embed.set_author(name=data.get("author_name"), icon_url=data.get("author_icon_url"))
        else:
            embed.set_author(name=data.get("author_name"))
    if data.get("footer_text"):
        if data.get("footer_icon_url"):
            embed.set_footer(text=data.get("footer_text"), icon_url=data.get("footer_icon_url"))
        else:
            embed.set_footer(text=data.get("footer_text"))

    return embed

# -----------------------
# Core processing for embed creation (called from modal)
# -----------------------
async def process_create_embed(interaction: discord.Interaction, data: dict):
    target_channel_id = data.get("target_channel_id")
    if target_channel_id is None:
        await interaction.followup.send("❌ No target channel specified.", ephemeral=True)
        return
    guild = interaction.guild
    target_channel = guild.get_channel(int(target_channel_id))
    if not target_channel:
        await interaction.followup.send("❌ Target channel not found.", ephemeral=True)
        return
    
    # Build embeds
    embeds = []
    image_urls = data.get("image_urls", [])
    
    if image_urls:
        # If we have images, create embeds for each image
        for i, image_url in enumerate(image_urls):
            if i == 0:  # First embed with title/description
                embed = build_embed_from_data(data, image_url)
            else:  # Additional embeds with only images
                embed = discord.Embed(color=parse_color(data.get("color")))
                embed.set_image(url=image_url)
            embeds.append(embed)
    else:
        # If no images, create a single embed with just title/description
        embed = build_embed_from_data(data)
        embeds.append(embed)
    
    # Check if we have any content at all
    has_content = any([
        data.get("title"),
        data.get("description"), 
        data.get("footer_text"),
        image_urls,
        data.get("thumbnail_url"),
        data.get("author_name")
    ])
    
    if not has_content:
        await interaction.followup.send("❌ No content provided. Add at least a title, description, or image.", ephemeral=True)
        return
    
    extra = data.get("extra_content") or None
    preview = data.get("preview", False)

    if preview:
        try:
            dm = await interaction.user.create_dm()
            await dm.send(content=extra or None, embeds=embeds)
            await interaction.followup.send("✅ Preview sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Couldn't DM you (maybe DMs disabled).", ephemeral=True)
        return

    # Send embeds to target channel
    try:
        sent = await target_channel.send(content=extra or None, embeds=embeds)
        sent_embeds[str(sent.id)] = {"guild_id": guild.id, "channel_id": target_channel.id}
        save_json(SENT_EMBEDS_FILE, sent_embeds)
        await interaction.followup.send(f"✅ {len(embeds)} embed(s) sent to {target_channel.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to send messages in the target channel.", ephemeral=True)
    except Exception as e:
        logger.exception("Failed to send embed")
        await interaction.followup.send("❌ Failed to send embed. See logs.", ephemeral=True)

# -----------------------
# Slash: create_embed (opens modal)
# -----------------------
@bot.tree.command(name="create_embed", description="Create and send a custom embed (admin only). Use the modal to add fields.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    channel="Channel to send the embed to",
    color="Color (hex like #ff00aa or name)",
    thumbnail_url="Thumbnail image URL (optional)",
    author_name="Author name (optional)",
    author_icon_url="Author icon URL (optional)",
    footer_icon_url="Footer icon URL (optional)",
    timestamp="Include timestamp",
    preview="Preview in your DMs instead of sending publicly"
)
async def create_embed_cmd(interaction: discord.Interaction,
                           channel: discord.TextChannel,
                           color: str = "#DC143C",
                           thumbnail_url: str = None,
                           image_url: str = None,
                           author_name: str = None,
                           author_icon_url: str = None,
                           footer_icon_url: str = None,
                           timestamp: bool = False,
                           preview: bool = False):
    bad = []
    for name, url in (("thumbnail_url", thumbnail_url), ("image_url", image_url),
                      ("author_icon_url", author_icon_url), ("footer_icon_url", footer_icon_url)):
        if url and not (url.startswith("http://") or url.startswith("https://")):
            bad.append(name)
    if bad:
        await interaction.response.send_message(f"❌ These URLs look invalid: {', '.join(bad)}", ephemeral=True)
        return

    callback_data = {
        "target_channel_id": channel.id,
        "color": color,
        "thumbnail_url": thumbnail_url,
        "image_url": image_url,
        "author_name": author_name,
        "author_icon_url": author_icon_url,
        "footer_icon_url": footer_icon_url,
        "timestamp_on": timestamp,
        "preview": preview
    }
    try:
        await interaction.response.send_modal(CreateEmbedModal(callback_data))
    except Exception as e:
        logger.exception("Failed to open modal")
        await interaction.response.send_message("❌ Failed to open modal. Try again.", ephemeral=True)

# -----------------------
# Edit embed
# -----------------------
@bot.tree.command(name="edit_embed", description="Edit an embed previously sent by the bot (admin only)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    message_id="Message ID of the embed the bot sent", 
    embed_index="Which embed to edit (starts from 1)", 
    new_title="New title (use 'clear' to remove)",
    new_description="New description (use 'clear' to remove)",
    new_footer="New footer text (use 'clear' to remove)",
    new_color="New color (hex like #ff00aa or name)",
    new_image="New image URL (use 'clear' to remove)",
    new_thumbnail="New thumbnail URL (use 'clear' to remove)",
    new_author_name="New author name (use 'clear' to remove)",
    new_author_icon="New author icon URL",
    new_content="New message content (outside embed, use 'clear' to remove)"
)
async def edit_embed(interaction: discord.Interaction, message_id: str, embed_index: int = 1, 
                    new_title: str = None, new_description: str = None, 
                    new_footer: str = None, new_color: str = None,
                    new_image: str = None, new_thumbnail: str = None,
                    new_author_name: str = None, new_author_icon: str = None,
                    new_content: str = None):
    info = sent_embeds.get(str(message_id))
    if not info:
        await interaction.response.send_message("❌ I don't have that message recorded as a sent embed.", ephemeral=True)
        return
    guild_id = info.get("guild_id")
    channel_id = info.get("channel_id")
    if guild_id != interaction.guild.id:
        await interaction.response.send_message("❌ That embed belongs to a different guild.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
        return
    
    if embed_index < 1:
        await interaction.response.send_message("❌ Embed index must be at least 1.", ephemeral=True)
        return
    
    # Validate URLs if provided
    urls_to_validate = {
        "Image URL": new_image,
        "Thumbnail URL": new_thumbnail,
        "Author icon URL": new_author_icon
    }
    
    for url_name, url in urls_to_validate.items():
        if url and url != "clear":
            if not (url.startswith("http://") or url.startswith("https://")):
                await interaction.response.send_message(f"❌ {url_name} must start with http:// or https://", ephemeral=True)
                return
    
    try:
        msg = await channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message("❌ Could not fetch that message (it may have been deleted).", ephemeral=True)
        return
    
    if not msg.embeds:
        await interaction.response.send_message("❌ That message has no embeds.", ephemeral=True)
        return
    
    if embed_index > len(msg.embeds):
        await interaction.response.send_message(f"❌ That message only has {len(msg.embeds)} embed(s).", ephemeral=True)
        return
    
    embed = msg.embeds[embed_index - 1]
    
    # Create a new embed with the updated values
    new_embed = discord.Embed(
        title=new_title if new_title != "clear" else None if new_title is not None else embed.title,
        description=new_description if new_description != "clear" else None if new_description is not None else embed.description,
        color=parse_color(new_color) if new_color is not None else embed.color,
        timestamp=embed.timestamp
    )
    
    # Handle image
    if new_image is not None:
        if new_image == "clear":
            new_embed.set_image(url=None)
        else:
            new_embed.set_image(url=new_image)
    elif embed.image.url:
        new_embed.set_image(url=embed.image.url)
    
    # Handle thumbnail
    if new_thumbnail is not None:
        if new_thumbnail == "clear":
            new_embed.set_thumbnail(url=None)
        else:
            new_embed.set_thumbnail(url=new_thumbnail)
    elif embed.thumbnail.url:
        new_embed.set_thumbnail(url=embed.thumbnail.url)
    
    # Handle author
    if new_author_name is not None:
        if new_author_name == "clear":
            new_embed.set_author(name=None, icon_url=None)
        else:
            author_icon = new_author_icon if new_author_icon is not None else (embed.author.icon_url if embed.author else None)
            new_embed.set_author(name=new_author_name, icon_url=author_icon)
    elif embed.author:
        new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url or None)
    elif new_author_icon is not None:
        # Only icon change requested but no author name exists
        await interaction.response.send_message("❌ Cannot set author icon without author name. Use new_author_name parameter.", ephemeral=True)
        return
    
    # Handle footer
    if new_footer is not None:
        if new_footer == "clear":
            new_embed.set_footer(text=None, icon_url=None)
        else:
            new_embed.set_footer(text=new_footer, icon_url=embed.footer.icon_url if embed.footer else None)
    elif embed.footer:
        new_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url or None)
    
    # Copy fields (since we don't have field editing in this command)
    for field in embed.fields:
        new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
    
    # Create new list of embeds with the modified one
    new_embeds = list(msg.embeds)
    new_embeds[embed_index - 1] = new_embed
    
    # Handle message content
    new_message_content = None
    if new_content is not None:
        new_message_content = None if new_content == "clear" else new_content
    else:
        new_message_content = msg.content
    
    try:
        await msg.edit(content=new_message_content, embeds=new_embeds)
        changes = []
        if new_title is not None:
            changes.append(f"title to '{new_title}'" if new_title != "clear" else "title")
        if new_description is not None:
            changes.append(f"description to '{new_description}'" if new_description != "clear" else "description")
        if new_footer is not None:
            changes.append(f"footer to '{new_footer}'" if new_footer != "clear" else "footer")
        if new_color is not None:
            changes.append(f"color to '{new_color}'")
        if new_image is not None:
            changes.append(f"image to '{new_image}'" if new_image != "clear" else "image")
        if new_thumbnail is not None:
            changes.append(f"thumbnail to '{new_thumbnail}'" if new_thumbnail != "clear" else "thumbnail")
        if new_author_name is not None:
            changes.append(f"author to '{new_author_name}'" if new_author_name != "clear" else "author")
        if new_content is not None:
            changes.append(f"content to '{new_content}'" if new_content != "clear" else "content")
        
        change_text = ", ".join(changes) if changes else "nothing (no changes specified)"
        await interaction.response.send_message(f"✅ Edited embed #{embed_index}: {change_text}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing permission to edit that message.", ephemeral=True)
    except Exception as e:
        logger.exception("Failed to edit embed")
        await interaction.response.send_message("❌ Failed to edit embed. See logs.", ephemeral=True)

# DM 

@bot.tree.command(name="dm", description="Send a DM to a member (admin only)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    member="The member to DM",
    message="The plain text message (optional)",
    title="Embed title (optional)",
    description="Embed description (optional)",
    image_url="Image URL for embed (optional)",
    color="Embed color (optional)"
)
async def dm_combined(interaction: discord.Interaction, member: discord.Member, 
                     message: str = None, title: str = None, 
                     description: str = None, image_url: str = None, color: str = None):
    try:
        if not message and not title and not description and not image_url:
            await interaction.response.send_message("❌ Need either a message, embed content, or image", ephemeral=True)
            return
        
        # Validate image URL if provided
        if image_url and image_url != "clear":
            if not (image_url.startswith("http://") or image_url.startswith("https://")):
                await interaction.response.send_message("❌ Image URL must start with http:// or https://", ephemeral=True)
                return
            
        if title or description or image_url:
            # Send embed (with optional text and image)
            embed = discord.Embed(
                title=title or None,
                description=description or None,
                color=parse_color(color),
                timestamp=datetime.utcnow()
            )
            
            # Add image if provided
            if image_url and image_url != "clear":
                embed.set_image(url=image_url)
                
            embed.set_footer(text=f"From {interaction.guild.name}")
            await member.send(content=message, embed=embed)
        else:
            # Send plain text only
            await member.send(message)
            
        await interaction.response.send_message(f"✅ DM sent to {member.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot send DM (user has DMs disabled or blocked the bot)", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to send DM: {e}")
        await interaction.response.send_message("❌ Failed to send DM. See logs.", ephemeral=True)

# Help

@bot.tree.command(name="help", description="Show help guide for using this bot")
@app_commands.checks.has_permissions(administrator=True)
async def help_command(interaction: discord.Interaction):
    """Display a comprehensive help guide for all bot commands"""
    
    help_embed = discord.Embed(
        title="🗿 Enchanted Man Guide",
        description="Here's how to use all the features of mine:",
        color=0xDC143C
    )
    
    # Welcome Commands
    help_embed.add_field(
        name="🎉 Welcome Message Commands",
        value=(
            "`/add_welcome [message]` - Add a custom welcome message\n"
            "`/list_welcome` - View all welcome messages for this server\n"
            "`/remove_welcome [index]` - Remove a welcome message by number\n"
            "`/edit_welcome [index] [new_text]` - Edit a welcome message\n"
            "`/test_welcome` - Test the welcome message\n"
            "**Placeholders:** `{mention}`, `{username}`, `{server}`"
        ),
        inline=False
    )
    
    # Embed Creation Commands
    help_embed.add_field(
        name="🖼️ Embed Creation Commands",
        value=(
            "`/create_embed` - Create and send custom embeds with images\n"
            "**Features:** Multiple images, titles, descriptions, footer, author\n"
            "**Modal fields:** Title, Description, Image URLs (one per line), Footer, Message content"
        ),
        inline=False
    )
    
    # Embed Editing Commands
    help_embed.add_field(
        name="✏️ Embed Editing Commands",
        value=(
            "`/edit_embed [message_id] [embed_index]` - Edit existing embeds\n"
            "**Editable fields:** Title, Description, Footer, Color, Image, Thumbnail, Author, Message content\n"
            "**Special:** Use `clear` to remove any field\n"
            "**Example:** `/edit_embed message_id:123 embed_index:1 new_title:\"New Title\" new_image:clear`"
        ),
        inline=False
    )
    
    # DM Commands
    help_embed.add_field(
        name="📨 DM Commands",
        value=(
            "`/dm [member]` - Send messages or embeds to members\n"
            "**Options:** Plain text, embed title, embed description, images/GIFs\n"
            "**Examples:**\n"
            "• `/dm member:@User message:\"Hello!\"` - Plain text\n"
            "• `/dm member:@User title:\"News\" description:\"Update!\"` - Embed only\n"
            "• `/dm member:@User image_url:\"https://example.com/image.gif\"` - Just GIF/image\n"
            "• Mix and match any combination!"
        ),
        inline=False
    )
    
    # Color Guide
    help_embed.add_field(
        name="🎨 Color Options",
        value=(
            "**Hex codes:** `#FF0000`, `FF0000`, `#F00`, `F00`\n"
            "**Color names:** `red`, `yellow`, `blue`, `green`, `orange`, `purple`, `pink`\n"
            "**Discord colors:** `blurple`, `discord_red`, `discord_green`\n"
            "**RGB tuples:** `(255,0,0)`, `(100,200,50)`\n"
            "**Over 100+ color names supported!**"
        ),
        inline=False
    )
    
    # Media Guide
    help_embed.add_field(
        name="🖼️ Media Support",
        value=(
            "**Images:** JPEG, PNG, WebP\n"
            "**GIFs:** Animated GIFs fully supported in embeds\n"
            "**URLs must start with:** `http://` or `https://`\n"
            "**Multiple images:** Enter one URL per line\n"
            "**Max per message:** 10 images (Discord limit)"
        ),
        inline=False
    )
    
    # Mention Guide
    help_embed.add_field(
        name="📍 How to Mention Users/Roles",
        value=(
            "**In message content and embed text:** Use raw format (`<@USER_ID>` or `<@&ROLE_ID>`)\n"
            "**Get IDs:** Enable Developer Mode → Right-click → Copy ID\n"
            "**Note:** Regular @mentions work in message content only"
        ),
        inline=False
    )
    
    # Usage Tips
    help_embed.add_field(
        name="💡 Pro Tips",
        value=(
            "• Use `clear` to remove fields in `/edit_embed`\n"
            "• GIFs work automatically in image URLs\n"
            "• All commands are admin-only for security\n"
            "• Mix text and embeds in `/dm` for rich messages\n"
            "• Test welcome messages with `/test_welcome`"
        ),
        inline=False
    )
    
    help_embed.set_footer(text="Need more help? Contact the server administrators.")
    
    await interaction.response.send_message(embed=help_embed, ephemeral=True)

# -----------------------
# Run
# -----------------------
def main():
    try:
        bot.config.validate()
    except Exception as e:
        logger.error(f"Configuration invalid: {e}")
        return

    token = bot.config.bot_token
    bot.run(token)

if __name__ == "__main__":
    main()











