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
    #991908158274539681: 991943909565550643,   # Guild B -> Channel B (Enchanted Squad)
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
    msgs = welcome_messages.get(str(guild_id))
    if not msgs:
        return DEFAULT_MESSAGES.copy()
    return msgs

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
        bg = bg.filter(ImageFilter.GaussianBlur(10))
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
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
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
            for blur_radius in [10,6,3]:
                glow = Image.new("RGBA", banner.size, (0,0,0,0))
                glow_draw = ImageDraw.Draw(glow)
                glow_draw.text(pos, text, font=font, fill=glow_color + (180,))
                glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
                banner.alpha_composite(glow)
            offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1)]
            for ox,oy in offsets:
                draw.text((pos[0]+ox,pos[1]+oy), text, font=font, fill=base_color)

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
    welcome_messages.setdefault(guild_id, get_guild_messages(interaction.guild.id))
    welcome_messages[guild_id].append(message)
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
    await interaction.response.send_message(f"🗑 Removed: `{removed}`", ephemeral=True)

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
    member = member or interaction.user
    guild = interaction.guild
    channel_id = get_welcome_channel_id(guild.id)
    if not channel_id:
        await interaction.response.send_message("❌ No welcome channel configured in the code. Add it to WELCOME_CHANNELS variable.", ephemeral=True)
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("❌ Configured welcome channel not found in this server.", ephemeral=True)
        return

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

    await interaction.response.send_message("✅ Test welcome sent.", ephemeral=True)

# -----------------------
# Create embed modal & helper
# -----------------------

class CreateEmbedModal(discord.ui.Modal, title="Create Embed"):
    title_input = discord.ui.TextInput(label="Title (optional)", style=discord.TextStyle.short, required=False, max_length=256)
    description_input = discord.ui.TextInput(label="Description (optional)", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    footer_input = discord.ui.TextInput(label="Footer (optional)", style=discord.TextStyle.short, required=False, max_length=2048)
    extra_content_input = discord.ui.TextInput(label="Extra content (optional)", style=discord.TextStyle.paragraph, required=False, max_length=2000)
    fields_input = discord.ui.TextInput(
        label="Fields (name|value|inline)", style=discord.TextStyle.paragraph, required=False, max_length=2000
    )

    def __init__(self, callback_data: dict):
        super().__init__()
        self.callback_data = callback_data

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = self.callback_data.copy()
        data.update({
            "title": self.title_input.value.strip(),
            "description": self.description_input.value.strip(),
            "footer_text": self.footer_input.value.strip(),
            "extra_content": self.extra_content_input.value.strip(),
            "fields_raw": self.fields_input.value.strip()
        })
        # process creation
        try:
            await process_create_embed(interaction, data)
        except Exception as e:
            logger.exception("Failed to process embed creation")
            await interaction.followup.send("❌ Failed to create embed. See logs.", ephemeral=True)

            
# -----------------------
# Helper: parse color hex or name
# -----------------------
def parse_color(s: str):
    if not s:
        return 0xDC143C
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    try:
        return int(s, 16)
    except Exception:
        names = {"red":0xFF0000, "green":0x00FF00, "blue":0x0000FF, "crimson":0xDC143C}
        return names.get(s.lower(), 0xDC143C)

# -----------------------
# Helper: build embed from data (and parse fields)
# -----------------------
def build_embed_from_data(data: dict):
    color = parse_color(data.get("color"))
    embed = discord.Embed(
        title=data.get("title") or discord.Embed.Empty,
        description=data.get("description") or discord.Embed.Empty,
        color=color,
        timestamp=datetime.utcnow() if data.get("timestamp_on") else None
    )
    if data.get("thumbnail_url"):
        embed.set_thumbnail(url=data.get("thumbnail_url"))
    if data.get("image_url"):
        embed.set_image(url=data.get("image_url"))
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

    fields_raw = data.get("fields_raw") or ""
    if fields_raw:
        lines = [l.strip() for l in fields_raw.splitlines() if l.strip()]
        for i, line in enumerate(lines[:10]):
            parts = line.split("|")
            if len(parts) >= 2:
                name = parts[0].strip()[:256]
                value = parts[1].strip()[:1024]
                inline = False
                if len(parts) >= 3:
                    inline = parts[2].strip().lower() in ("true","1","yes","y")
                embed.add_field(name=name, value=value, inline=inline)
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
    embed = build_embed_from_data(data)
    extra = data.get("extra_content") or None
    preview = data.get("preview", False)

    if preview:
        try:
            dm = await interaction.user.create_dm()
            await dm.send(content=extra or None, embed=embed)
            await interaction.followup.send("✅ Preview sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Couldn't DM you (maybe DMs disabled).", ephemeral=True)
        return

    try:
        sent = await target_channel.send(content=extra or None, embed=embed)
        sent_embeds[str(sent.id)] = {"guild_id": guild.id, "channel_id": target_channel.id}
        save_json(SENT_EMBEDS_FILE, sent_embeds)
        await interaction.followup.send(f"✅ Embed sent to {target_channel.mention}", ephemeral=True)
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
    image_url="Main image URL (optional)",
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
@app_commands.describe(message_id="Message ID of the embed the bot sent", new_title="New title (optional)", new_description="New description (optional)")
async def edit_embed(interaction: discord.Interaction, message_id: str, new_title: str = None, new_description: str = None):
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
    try:
        msg = await channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message("❌ Could not fetch that message (it may have been deleted).", ephemeral=True)
        return
    if not msg.embeds:
        await interaction.response.send_message("❌ That message has no embed.", ephemeral=True)
        return
    embed = msg.embeds[0]
    if new_title is not None:
        embed.title = new_title
    if new_description is not None:
        embed.description = new_description
    try:
        await msg.edit(embed=embed)
        await interaction.response.send_message("✅ Edited the embed.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Missing permission to edit that message.", ephemeral=True)
    except Exception as e:
        logger.exception("Failed to edit embed")
        await interaction.response.send_message("❌ Failed to edit embed. See logs.", ephemeral=True)

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




