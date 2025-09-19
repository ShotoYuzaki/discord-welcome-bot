import discord
from discord.ext import commands
from discord import File, app_commands
import aiohttp
import asyncio
import os
import sqlite3
import json
from datetime import datetime
import logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from io import BytesIO
from dotenv import load_dotenv
import random


# ensure persistent storage path (Railway)
import os
PERSISTENT_STORAGE_PATH = os.getenv('PERSISTENT_STORAGE_PATH')
if PERSISTENT_STORAGE_PATH:
        os.makedirs(PERSISTENT_STORAGE_PATH, exist_ok=True)


# ===========================
# Load environment variables
# ===========================
load_dotenv()


# ===========================
# Set up logging
# ===========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WelcomeBot')


# ===========================
# Bot configuration
# ===========================
class Config:
        def __init__(self):
            self.bot_token = os.getenv('BOT_TOKEN')
            
        def validate(self):
            if not self.bot_token:
                raise ValueError("BOT_TOKEN environment variable is required")
            return True


# ===========================
# SQLite setup
# ===========================
DB_FILE = os.path.join(PERSISTENT_STORAGE_PATH if PERSISTENT_STORAGE_PATH else ".", "bot_data.db")


def init_db():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Table for welcome messages
        c.execute("""CREATE TABLE IF NOT EXISTS welcome_messages (
                        guild_id INTEGER,
                        message TEXT
                    )""")
        # Table for custom embeds
        c.execute("""CREATE TABLE IF NOT EXISTS embeds (
                        message_id INTEGER PRIMARY KEY,
                        channel_id INTEGER,
                        guild_id INTEGER,
                        data TEXT
                    )""")
        conn.commit()
        conn.close()


init_db()


# ===========================
# Default Welcome Messages
# ===========================
DEFAULT_WELCOME_MESSAGES = [
   "Welcome! {mention} glad you made it here!",
   "Yo {mention}! Welcome to our server!",
   "Let's gooo! {mention} has joined the gang!",
   "It's so good to have you here {mention}!",
   "Welcome {mention}! Great to have you here!"
]


# ===========================
# Hardcoded welcome channel
# ===========================
WELCOME_CHANNEL_ID = 123456789012345678  # 👈 replace with your actual channel ID


# ===========================
# Helpers for JSON persistence (legacy support if present)
# ===========================
def load_json(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}


def save_json(path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.exception("Failed to save JSON: %s", e)


# Legacy files names (if your original used these)
WELCOME_FILE = os.path.join(PERSISTENT_STORAGE_PATH if PERSISTENT_STORAGE_PATH else ".", "welcome_messages.json")
SENT_EMBEDS_FILE = os.path.join(PERSISTENT_STORAGE_PATH if PERSISTENT_STORAGE_PATH else ".", "sent_embeds.json")


# Load legacy structures if present
welcome_messages = load_json(WELCOME_FILE) if os.path.exists(WELCOME_FILE) else {}
sent_embeds = load_json(SENT_EMBEDS_FILE) if os.path.exists(SENT_EMBEDS_FILE) else {}


# ===========================
# Utility functions for guild messages (compat with original structure)
# ===========================
def get_guild_messages(guild_id: int):
        guild_id_str = str(guild_id)
        if guild_id_str in welcome_messages and welcome_messages[guild_id_str]:
            return welcome_messages[guild_id_str].copy()  # Return a copy to avoid modification
        # If not in JSON legacy, try DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT message FROM welcome_messages WHERE guild_id=?", (guild_id,))
        rows = c.fetchall()
        conn.close()
        if rows:
            return [r[0] for r in rows]
        return DEFAULT_WELCOME_MESSAGES.copy()  # Always return a copy of defaults


def get_welcome_channel_id(guild_id: int):
        # In this cleaned version we expect a hardcoded channel id or the WELCOME_CHANNEL_ID constant
        # If you had per-guild mappings in JSON, check them
        return WELCOME_CHANNEL_ID


# ===========================
# Helper to parse colors
# ===========================
def parse_color(color_str):
        if not color_str:
            return 0xDC143C
        try:
            if isinstance(color_str, int):
                return color_str
            cs = color_str.strip()
            if cs.startswith("#"):
                cs = cs[1:]
            return int(cs, 16)
        except:
            # fallback
            return 0xDC143C


# ===========================
# Main Bot Class
# ===========================
class WelcomeBot(commands.Bot):
        def __init__(self):
            intents = discord.Intents.default()
            intents.members = True
            intents.guilds = True
            intents.message_content = True
            super().__init__(
                command_prefix='!wb_',  # unused since we use slash commands
                intents=intents,
                help_command=None
            )
            self.config = Config()
            self.session = None


        async def setup_hook(self):
            self.session = aiohttp.ClientSession()
            logger.info("Bot is starting up...")
            try:
                await self.tree.sync()
            except Exception as e:
                logger.warning(f"Failed to auto-sync slash commands: {e}")
            logger.info("Bot setup complete.")


        async def on_ready(self):
            logger.info(f'{self.user} has landed!')
            logger.info(f'Connected to {len(self.guilds)} server(s)')
            
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="for new members 👀"
                )
            )


        # ===========================
        # Welcome Banner Generator
        # ===========================
        def create_welcome_banner(self, member):
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
                font_loaded = False
                for font_path in font_paths:
                    try:
                        if os.path.exists(font_path):
                            title_font = ImageFont.truetype(font_path, 55)
                            subtitle_font = ImageFont.truetype(font_path, 32)
                            font_loaded = True
                            break
                    except:
                        continue


                if not font_loaded:
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()


                def draw_neon_text(banner, text, pos, font, base_color=(255, 255, 255), glow_color=(220, 20, 60)):
                    draw = ImageDraw.Draw(banner)
                    for blur_radius in [10, 6, 3]:
                        glow = Image.new("RGBA", banner.size, (0, 0, 0, 0))
                        glow_draw = ImageDraw.Draw(glow)
                        glow_draw.text(pos, text, font=font, fill=glow_color + (180,))
                        glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
                        banner.alpha_composite(glow)
                    offsets = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
                    for ox, oy in offsets:
                        draw.text((pos[0] + ox, pos[1] + oy), text, font=font, fill=base_color)


                frame = bg.copy()
                frame.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)
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


                img_buffer = BytesIO()
                frame.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                return img_buffer
            except Exception as e:
                logger.error(f"Error creating welcome banner: {e}")
                return None


        # ===========================
        # Event: Member Join
        # ===========================
        async def on_member_join(self, member):
            logger.info(f"on_member_join fired for {member.display_name} in {member.guild.name}")
            try:
                # load custom or default welcome messages
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT message FROM welcome_messages WHERE guild_id=?", (member.guild.id,))
                rows = c.fetchall()
                conn.close()
                messages = [r[0] for r in rows] if rows else DEFAULT_WELCOME_MESSAGES


                message = random.choice(messages).format(mention=member.mention)


                channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
                if not channel:
                    logger.warning("Welcome channel not found. Please set WELCOME_CHANNEL_ID correctly.")
                    return


                banner_buffer = self.create_welcome_banner(member)
                file = discord.File(banner_buffer, filename="welcome_banner.png") if banner_buffer else None


                embed = discord.Embed(
                    title="👋 Welcome to the server!",
                    description=message,
                    color=0xDC143C,
                    timestamp=datetime.utcnow()
                )
                if member.guild.icon:
                    embed.set_footer(text=f"Joined {datetime.utcnow().strftime('%B %d, %Y')}",
                                     icon_url=member.guild.icon.url)
                else:
                    embed.set_footer(text=f"Joined {datetime.utcnow().strftime('%B %d, %Y')}")
                if file:
                    embed.set_image(url="attachment://welcome_banner.png")


                await channel.send(content=member.mention, embed=embed, file=file if file else None)
            except Exception as e:
                logger.error(f"Error in on_member_join: {e}")


        async def close(self):
            # restored close function placeholder
            if hasattr(self, "session") and self.session:
                try:
                    await self.session.close()
                except:
                    pass
            return


# ===========================
# Slash Commands
# ===========================
bot = WelcomeBot()


# /help command
@bot.tree.command(name="help", description="Show help information about the bot")
async def help_command(interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Welcome Bot Help",
            description="Here are the available commands:",
            color=0x5865F2
        )
        embed.add_field(name="/help", value="Show this message", inline=False)
        embed.add_field(name="/add_welcome_message", value="Add a custom welcome message", inline=False)
        embed.add_field(name="/list_welcome_messages", value="List all welcome messages", inline=False)
        embed.add_field(name="/create_embed", value="Create and send a custom embed", inline=False)
        embed.add_field(name="/edit_embed", value="Edit an embed the bot has sent", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Quick help
@bot.tree.command(name="quickhelp", description="Short help summary")
async def quick_help(interaction: discord.Interaction):
        """Short help summary"""
        quick_help = """
**🤖 Quick Commands:**
• `/add_welcome` - Add welcome message
• `/create_embed` - Create image embeds  
• `/edit_embed` - Edit existing embeds
• `/help` - Full detailed guide


**🔧 Admin only:** Welcome commands and embed creation
"""
        await interaction.response.send_message(quick_help, ephemeral=True)


# /add_welcome (legacy name preserved)
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


# Modal and embed builders (recreated from original content)
class CreateEmbedModal(discord.ui.Modal, title="Create Embed"):
        title_input = discord.ui.TextInput(label="Title (optional)", style=discord.TextStyle.short, required=False, max_length=256)
        description_input = discord.ui.TextInput(label="Description (optional)", style=discord.TextStyle.paragraph, required=False, max_length=4096)
        images_input = discord.ui.TextInput(label="Image URLs (one per line)", style=discord.TextStyle.paragraph, required=False, max_length=2000)
        footer_input = discord.ui.TextInput(label="Footer text (optional)", style=discord.TextStyle.short, required=False, max_length=2048)
        extra_input = discord.ui.TextInput(label="Message content (optional)", style=discord.TextStyle.paragraph, required=False, max_length=2000)


        def __init__(self, callback_data: dict):
            super().__init__()
            self.callback_data = callback_data


        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            image_urls = []
            if self.images_input.value.strip():
                image_urls = [url.strip() for url in self.images_input.value.split('\n') if url.strip()]
            
            data = self.callback_data.copy()
            data.update({
                "title": self.title_input.value.strip() or None,
                "description": self.description_input.value.strip() or None,
                "image_urls": image_urls,
                "footer_text": self.footer_input.value.strip() or None,
                "extra_content": self.extra_input.value.strip() or None
            })


            await process_create_embed(interaction, data)


# Helper to build embed from data (keeps original fields behavior)
def build_embed_from_data(data: dict, image_url: str = None):
        color = parse_color(data.get("color"))
        embed = discord.Embed(
            title=data.get("title"),
            description=data.get("description") or None,
            color=color,
            timestamp=datetime.utcnow() if data.get("timestamp_on") else None
        )
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


# Core processing for embed creation (called from modal)
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
    
        embeds = []
        image_urls = data.get("image_urls", [])
    
        if image_urls:
            for i, image_url in enumerate(image_urls):
                if i == 0:
                    embed = build_embed_from_data(data, image_url)
                else:
                    embed = discord.Embed(color=parse_color(data.get("color")))
                    embed.set_image(url=image_url)
                embeds.append(embed)
        else:
            embed = build_embed_from_data(data)
            embeds.append(embed)
    
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
# Slash: create_embed (initial)
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
            try:
                await interaction.followup.send("❌ Failed to open modal. Try again.", ephemeral=True)
            except:
                try:
                    await interaction.response.send_message("❌ Failed to open modal. Try again.", ephemeral=True)
                except:
                    pass


# -----------------------
# Edit embed (admin-only)
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
    
        try:
            mid = int(message_id)
        except:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return


        try:
            msg = await channel.fetch_message(mid)
        except:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
            return


        if not msg.embeds:
            await interaction.response.send_message("❌ That message has no embeds.", ephemeral=True)
            return
    
        if embed_index > len(msg.embeds):
            await interaction.response.send_message(f"❌ That message only has {len(msg.embeds)} embed(s).", ephemeral=True)
            return
    
        embed = msg.embeds[embed_index - 1]
    
        new_embed = discord.Embed(
            title=new_title if new_title != "clear" else None if new_title is not None else embed.title,
            description=new_description if new_description != "clear" else None if new_description is not None else embed.description,
            color=parse_color(new_color) if new_color is not None else (embed.color.value if isinstance(embed.color, discord.Color) else embed.color),
            timestamp=embed.timestamp
        )
    
        # Handle image
        try:
            if new_image is not None:
                if new_image == "clear":
                    pass
                else:
                    new_embed.set_image(url=new_image)
            elif embed.image and getattr(embed.image, "url", None):
                new_embed.set_image(url=embed.image.url)
        except:
            pass
    
        # Handle thumbnail
        try:
            if new_thumbnail is not None:
                if new_thumbnail == "clear":
                    pass
                else:
                    new_embed.set_thumbnail(url=new_thumbnail)
            elif embed.thumbnail and getattr(embed.thumbnail, "url", None):
                new_embed.set_thumbnail(url=embed.thumbnail.url)
        except:
            pass
    
        # Handle author
        if new_author_name is not None:
            if new_author_name == "clear":
                pass
            else:
                author_icon = new_author_icon if new_author_icon is not None else (embed.author.icon_url if embed.author else None)
                new_embed.set_author(name=new_author_name, icon_url=author_icon)
        elif embed.author:
            new_embed.set_author(name=embed.author.name, icon_url=embed.author.icon_url or None)
        elif new_author_icon is not None:
            await interaction.response.send_message("❌ Cannot set author icon without author name. Use new_author_name parameter.", ephemeral=True)
            return
    
        # Handle footer
        if new_footer is not None:
            if new_footer == "clear":
                pass
            else:
                new_embed.set_footer(text=new_footer, icon_url=embed.footer.icon_url if embed.footer else None)
        elif embed.footer:
            new_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url or None)
    
        # Copy fields
        for field in embed.fields:
            new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
    
        new_embeds = list(msg.embeds)
        new_embeds[embed_index - 1] = new_embed
    
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


# Help Command (comprehensive)
@bot.tree.command(name="help_guide", description="Show help guide for using this bot")
async def help_guide_command(interaction: discord.Interaction):
        help_embed = discord.Embed(
            title="🤖 Enchanted Man Help Guide",
            description="Here's how to use all the features of this bot:",
            color=0xDC143C
        )
        help_embed.add_field(
            name="🎉 Welcome Message Commands",
            value=(
                "`/add_welcome [message]` - Add a custom welcome message\n"
                "`/list_welcome` - View all welcome messages for this server\n"
                "`/remove_welcome [index]` - Remove a welcome message by number\n"
                "`/edit_welcome [index] [new_text]` - Edit a welcome message\n"
                "`/test_welcome` - Test the welcome message (admin only)\n"
                "**Placeholders:** `{mention}`, `{username}`, `{server}`"
            ),
            inline=False
        )
        help_embed.add_field(
            name="🖼️ Embed Creation Commands",
            value=(
                "`/create_embed` - Create and send custom embeds with images\n"
                "**Features:** Multiple images, titles, descriptions, footer, author\n"
                "**Modal fields:** Title, Description, Image URLs (one per line), Footer, Message content"
            ),
            inline=False
        )
        help_embed.add_field(
            name="✏️ Embed Editing Commands",
            value=(
                "`/edit_embed [message_id] [embed_index]` - Edit existing embeds\n"
                "**Editable fields:** Title, Description, Footer, Color, Image, Thumbnail, Author, Message content\n"
                "**Special:** Use `clear` to remove any field\n"
            ),
            inline=False
        )
        help_embed.add_field(
            name="📍 How to Mention Users/Roles",
            value=(
                "**In message content and embed text:** Use raw format (`<@USER_ID>` or `<@&ROLE_ID>`)\n"
                "**Get IDs:** Enable Developer Mode → Right-click → Copy ID"
            ),
            inline=False
        )
        help_embed.add_field(
            name="🖼️ Image Requirements",
            value=(
                "**Supported:** JPEG, PNG, GIF, WebP\n"
                "**URLs must start with:** `http://` or `https://`\n"
                "**Multiple images:** Enter one URL per line in the image field\n"
                "**Max images per message:** 10 (Discord limit)"
            ),
            inline=False
        )
        help_embed.set_footer(text="Need more help? Contact the server administrators")
        await interaction.response.send_message(embed=help_embed, ephemeral=True)


# Optional: quickhelp alias
@bot.tree.command(name="quick_help", description="Short help summary")
async def quick_help_alias(interaction: discord.Interaction):
        quick_help = """
**🤖 Quick Commands:**
• `/add_welcome` - Add welcome message
• `/create_embed` - Create image embeds  
• `/edit_embed` - Edit existing embeds
• `/help_guide` - Full detailed guide


**🔧 Admin only:** Welcome commands and embed creation
"""
        await interaction.response.send_message(quick_help, ephemeral=True)


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

