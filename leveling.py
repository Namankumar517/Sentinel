# Fixed leveling.py — only changed app_commands.group usage to a Group attribute on the Cog
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import random
from json.decoder import JSONDecodeError
from typing import Dict, List, Any, Optional, Union, Literal, cast

# --- New Imports for Image Generation ---
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
import functools
import asyncio
# ----------------------------------------

# ------------------------------------------------------
# 📁 File Path Setup
# ------------------------------------------------------
LEVELS_FILE = "data/levels.json"
CONFIG_FILE = "data/level_config.json"
FONTS_DIR = "fonts" # Folder for custom fonts (optional)

# Ensure data folder exists
os.makedirs("data", exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True) # Ensure fonts folder exists

# Helper function to load JSON data with error handling
def load_data(file_path):
    """Loads JSON data safely, returning {} on error or empty file."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                # Reset file pointer to the beginning for json.load
                f.seek(0)
                return json.load(f)
        except JSONDecodeError:
            print(f"[ERROR] JSONDecodeError in {file_path}. File may be corrupted. Overwriting with empty data.")
            with open(file_path, "w") as f:
                json.dump({}, f)
            return {}
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred while loading {file_path}: {e}")
            return {}
    return {}

# Helper function to save JSON data
def save_data(file_path, data):
    """Saves JSON data."""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred while saving {file_path}: {e}")

# Helper to get guild/user data
def get_user_data(guild_id: int, user_id: int) -> Dict[str, Union[int, datetime.datetime]]:
    levels = load_data(LEVELS_FILE)
    guild_id_str = str(guild_id)
    user_id_str = str(user_id)
    
    if guild_id_str not in levels:
        levels[guild_id_str] = {}

    if user_id_str not in levels[guild_id_str]:
        levels[guild_id_str][user_id_str] = {
            "xp": 0,
            "level": 0,
            "last_message": datetime.datetime.min.isoformat(),
            "total_xp": 0
        }
    
    # Convert ISO string back to datetime object for internal use
    last_message_str = levels[guild_id_str][user_id_str]["last_message"]
    levels[guild_id_str][user_id_str]["last_message"] = datetime.datetime.fromisoformat(last_message_str)
    
    return levels[guild_id_str][user_id_str]

def update_user_data(guild_id: int, user_id: int, data: Dict[str, Any]):
    levels = load_data(LEVELS_FILE)
    guild_id_str = str(guild_id)
    user_id_str = str(user_id)

    if guild_id_str not in levels:
        levels[guild_id_str] = {}

    if user_id_str not in levels[guild_id_str]:
        levels[guild_id_str][user_id_str] = {
            "xp": 0,
            "level": 0,
            "last_message": datetime.datetime.min.isoformat(),
            "total_xp": 0
        }

    # Convert datetime object back to ISO string for saving
    if "last_message" in data and isinstance(data["last_message"], datetime.datetime):
        data["last_message"] = data["last_message"].isoformat()

    levels[guild_id_str][user_id_str].update(data)
    save_data(LEVELS_FILE, levels)

# Helper to get guild config
DEFAULT_CONFIG = {
    "xp_cooldown": 60, # seconds
    "xp_min": 15,
    "xp_max": 25,
    "level_up_message_enabled": True,
    "level_up_channel": None,
    "ignore_channels": [],
    "level_roles": {}, # {level: role_id}
    "rank_card_background": None, # URL
    "rank_card_text_color": "#FFFFFF"
}

def get_guild_config(guild_id: int) -> Dict[str, Any]:
    config = load_data(CONFIG_FILE)
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = DEFAULT_CONFIG.copy()
        save_data(CONFIG_FILE, config)
    return config[guild_id_str]

def update_guild_config(guild_id: int, updates: Dict[str, Any]):
    config = load_data(CONFIG_FILE)
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = DEFAULT_CONFIG.copy()
    
    config[guild_id_str].update(updates)
    save_data(CONFIG_FILE, config)


# Formula: XP needed for next level
def get_xp_needed(level: int) -> int:
    return 5 * (level**2) + (50 * level) + 100

# Formula: Total XP required for a given level
def get_total_xp_required(level: int) -> int:
    # A simple summation of XP needed for all previous levels
    total_xp = 0
    for l in range(1, level + 1):
        total_xp += get_xp_needed(l - 1)
    return total_xp

# Formula: Calculate level from total XP
def get_level_info(total_xp: int) -> Dict[str, int]:
    level = 0
    xp_at_current_level = 0
    
    # We start checking from level 0 (XP needed to reach level 1)
    temp_xp = total_xp
    
    while True:
        xp_to_next_level = get_xp_needed(level)
        if temp_xp >= xp_to_next_level:
            temp_xp -= xp_to_next_level
            level += 1
        else:
            xp_at_current_level = temp_xp
            xp_needed_for_next = xp_to_next_level
            break
            
    return {
        "level": level,
        "xp": xp_at_current_level,
        "xp_needed": xp_needed_for_next
    }

# ------------------------------------------------------
# 🎨 Rank Card Generator
# ------------------------------------------------------
@functools.lru_cache(maxsize=32)
def get_font(size: int, font_name: str = "Roboto-Bold.ttf"):
    """Safely loads a font, using a default if the specified one is not found."""
    try:
        # Check for a specific custom font first
        custom_font_path = os.path.join(FONTS_DIR, font_name)
        if os.path.exists(custom_font_path):
            return ImageFont.truetype(custom_font_path, size)
    except Exception:
        pass # Fall through to default if custom fails

    # Fallback to a system font or default font if custom font isn't available
    try:
        return ImageFont.truetype("arial.ttf", size) # Common system font
    except:
        return ImageFont.load_default() # PIL default

async def _fetch_image(session: aiohttp.ClientSession, url: str) -> Optional[io.BytesIO]:
    """Asynchronously fetches an image from a URL."""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return io.BytesIO(await response.read())
            return None
    except Exception:
        return None

async def _generate_rank_card(
    user: discord.Member,
    current_xp: int,
    level: int,
    total_xp: int,
    xp_needed: int,
    rank: int,
    background_url: Optional[str],
    text_color: str
) -> Optional[io.BytesIO]:
    """
    Generates the rank card image with a custom background and colors.
    This is run in a separate thread to avoid blocking the bot.
    """
    
    async with aiohttp.ClientSession() as session:
        # --- Asynchronous Fetching ---
        avatar_size = 180
        avatar_url = str(user.display_avatar.with_size(avatar_size).url)
        avatar_data_task = asyncio.create_task(_fetch_image(session, avatar_url))
        
        background_data_task = None
        if background_url:
            background_data_task = asyncio.create_task(_fetch_image(session, background_url))
            
        avatar_data = await avatar_data_task
        background_data = await background_data_task if background_data_task else None
        
    def sync_generate(avatar_data: Optional[io.BytesIO], background_data: Optional[io.BytesIO]):
        try:
            # --- Setup ---
            card_width, card_height = 900, 250
            avatar_size = 180
            padding = 30
            
            # Convert hex color to RGB tuple
            try:
                text_color_rgb = tuple(int(text_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            except:
                text_color_rgb = (255, 255, 255) # Default to white if invalid hex

            # --- Base Image (Default Background or Custom) ---
            if background_data:
                bg_img = Image.open(background_data).convert("RGBA")
                # Resize and crop the background image to fit the card
                base_img = ImageOps.fit(bg_img, (card_width, card_height), method=Image.Resampling.LANCZOS).convert("RGBA")
                
                # Apply a dark overlay for better text readability
                overlay = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 150)) # Black, 60% opacity
                base_img.paste(overlay, (0, 0), overlay)
            else:
                # Default dark theme background
                base_img = Image.new('RGBA', (card_width, card_height), (44, 47, 51, 255)) 

            # Create a drawing context
            draw = ImageDraw.Draw(base_img)

            # --- Fonts ---
            font_large = get_font(40)
            font_medium = get_font(30)
            font_small = get_font(20)

            # --- XP Bar Calculation ---
            bar_width = card_width - (avatar_size + 3 * padding) - 100 
            bar_height = 30
            bar_x = avatar_size + 2 * padding
            bar_y = card_height - 2 * padding - bar_height
            
            # Calculate progress
            progress = current_xp / xp_needed if xp_needed > 0 else 0
            progress_width = int(bar_width * progress)

            # --- Draw XP Bar (Background) ---
            draw.rounded_rectangle(
                (bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), 
                radius=bar_height // 2, 
                fill=(32, 34, 37, 255) # Dark gray for background
            )

            # --- Draw XP Bar (Progress) ---
            # Using a distinct color for progress (Discord Blurple: 88, 101, 242)
            if progress_width > 0:
                draw.rounded_rectangle(
                    (bar_x, bar_y, bar_x + progress_width, bar_y + bar_height), 
                    radius=bar_height // 2, 
                    fill=(88, 101, 242, 255)
                )

            # --- Text: Username, Discriminator, Rank, Level ---
            
            # Username and Tag
            username_text = str(user.display_name)
            draw.text((bar_x, padding), username_text, font=font_large, fill=text_color_rgb)

            # Level
            level_text = f"LEVEL {level}"
            level_x = card_width - padding - draw.textlength(level_text, font=font_large)
            draw.text((level_x, padding), level_text, font=font_large, fill=text_color_rgb)
            
            # Rank
            rank_text = f"RANK #{rank}"
            # Positioning rank text just below level text and aligned to the right
            rank_x = card_width - padding - draw.textlength(rank_text, font=font_medium)
            draw.text((rank_x, padding + 50), rank_text, font=font_medium, fill=(180, 180, 180)) # Gray

            # XP numbers
            xp_text = f"{current_xp:,} / {xp_needed:,} XP"
            draw.text((bar_x, bar_y - 30), xp_text, font=font_small, fill=text_color_rgb)

            # Total XP
            total_xp_text = f"Total XP: {total_xp:,}"
            total_xp_x = bar_x
            draw.text((total_xp_x, bar_y + bar_height + 5), total_xp_text, font=font_small, fill=(180, 180, 180))


            # --- Avatar Handling ---
            if avatar_data:
                avatar_img = Image.open(avatar_data).convert("RGBA")
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

                # Create a circular mask
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

                # Apply the mask
                avatar_img.putalpha(mask)

                # Paste the avatar
                avatar_x = padding
                avatar_y = (card_height - avatar_size) // 2
                base_img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)


            # --- Finalize Image ---
            final_buffer = io.BytesIO()
            base_img.save(final_buffer, format="PNG")
            final_buffer.seek(0)
            return final_buffer
        
        except Exception as e:
            print(f"Error generating rank card: {e}")
            return None

    # --- Run image generation synchronously in a thread pool ---
    buffer = await asyncio.to_thread(sync_generate, avatar_data, background_data)
    return buffer

# ------------------------------------------------------
# 🤖 Cog Implementation
# ------------------------------------------------------

class Leveling(commands.Cog):
    # Create slash group properly as a class attribute (discord.py 2.6.4 compatible)
    levelsettings = app_commands.Group(
        name="levelsettings",
        description="Configure the leveling system for this server"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load data on init
        self.levels = load_data(LEVELS_FILE)
        self.config = load_data(CONFIG_FILE)

    def premium_embed(self, title, description, color=discord.Color.dark_green()):
        """Consistent embed generator."""
        embed = discord.Embed(
            title=f"⭐ {title}", 
            description=description, 
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Premium Leveling System")
        return embed
    
    # --- Unified Response Sender ---
    async def _send_response(self, source: Union[commands.Context, discord.Interaction], embed: discord.Embed, file: Optional[discord.File] = None, ephemeral: bool = False):
        if isinstance(source, commands.Context):
            await source.reply(embed=embed, file=file)
        elif source.response.is_done():
            await source.followup.send(embed=embed, file=file, ephemeral=ephemeral)
        else:
            await source.response.send_message(embed=embed, file=file, ephemeral=ephemeral)

    # ------------------------------------------------------
    # 👂 Message Listener (XP Gain)
    # ------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        
        # Check if message is a command (to avoid double processing)
        # Using a simple prefix check is often unreliable, but necessary if self.bot.process_commands is used outside this listener.
        # Assuming single-character prefix '!'
        if message.content.startswith('!'): 
             return

        config = get_guild_config(guild_id)
        
        # Check ignored channels
        if message.channel.id in config.get("ignore_channels", []):
            return

        user_data = get_user_data(guild_id, user_id)
        last_message_time = user_data["last_message"] # This is a datetime object now
        cooldown = config.get("xp_cooldown", 60)
        
        # Check cooldown
        if (discord.utils.utcnow() - last_message_time).total_seconds() < cooldown:
            return

        # Grant XP
        xp_gain = random.randint(config.get("xp_min", 15), config.get("xp_max", 25))
        
        old_level = user_data["level"]
        user_data["xp"] += xp_gain
        user_data["total_xp"] += xp_gain
        user_data["last_message"] = discord.utils.utcnow() # Update last message time

        # Level up check
        xp_needed = get_xp_needed(user_data["level"])
        leveled_up = False
        
        while user_data["xp"] >= xp_needed:
            user_data["xp"] -= xp_needed
            user_data["level"] += 1
            xp_needed = get_xp_needed(user_data["level"])
            leveled_up = True
        
        # Save updated data
        update_user_data(guild_id, user_id, user_data)
        
        # --- Level Up Handling ---
        if leveled_up:
            new_level = user_data["level"]
            
            # Send level up message
            if config.get("level_up_message_enabled"):
                channel_id = config.get("level_up_channel", message.channel.id)
                target_channel = self.bot.get_channel(channel_id) or message.channel
                
                embed = self.premium_embed(
                    "🎉 Level Up!", 
                    f"Congratulations {message.author.mention}! You leveled up to **Level {new_level}**!"
                )
                try:
                    await target_channel.send(embed=embed)
                except discord.Forbidden:
                    pass # Cannot send message to channel

            # Grant level roles
            level_roles = config.get("level_roles", {})
            for level, role_id in level_roles.items():
                try:
                    level_int = int(level)
                    role_id_int = int(role_id)
                    
                    if new_level >= level_int and old_level < level_int:
                        role = message.guild.get_role(role_id_int)
                        if role and message.guild.me.top_role > role:
                            try:
                                await message.author.add_roles(role)
                            except discord.Forbidden:
                                print(f"Cannot grant role {role.name} due to permissions.")
                            except discord.HTTPException:
                                print(f"Failed to grant role {role.name}.")
                except ValueError:
                    continue # Skip invalid config entries

    # ------------------------------------------------------
    # 📈 Rank Command (Unified)
    # ------------------------------------------------------
    async def _handle_rank(self, source: Union[commands.Context, discord.Interaction], member: discord.Member):
        if not member.guild:
            # Only happens if the command is used outside a guild, which shouldn't happen for these commands
            await self._send_response(source, self.premium_embed("Error", "❌ This command must be used in a server.", discord.Color.red()), ephemeral=True)
            return

        # Defer interaction for slash commands since image generation takes time
        if isinstance(source, discord.Interaction) and not source.response.is_done():
            await source.response.defer()

        guild_id = member.guild.id
        user_data = get_user_data(guild_id, member.id)
        config = get_guild_config(guild_id)

        # Calculate rank
        guild_levels = load_data(LEVELS_FILE).get(str(guild_id), {})
        # Filter out users with 0 total_xp and sort by total_xp descending
        sorted_users = sorted(
            [
                (user_id, data['total_xp']) 
                for user_id, data in guild_levels.items() if data.get('total_xp', 0) > 0
            ], 
            key=lambda item: item[1], 
            reverse=True
        )
        
        rank = next((i + 1 for i, (uid, xp) in enumerate(sorted_users) if int(uid) == member.id), len(sorted_users) + 1)
        
        # Prepare data for card generation
        level = user_data["level"]
        current_xp = user_data["xp"]
        total_xp = user_data["total_xp"]
        xp_needed = get_xp_needed(level)
        
        # Generate the card
        file_buffer = await _generate_rank_card(
            user=member,
            current_xp=current_xp,
            level=level,
            total_xp=total_xp,
            xp_needed=xp_needed,
            rank=rank,
            background_url=config.get("rank_card_background"),
            text_color=config.get("rank_card_text_color")
        )

        if not file_buffer:
            await self._send_response(source, self.premium_embed("Error", "❌ Failed to generate rank card image. Check bot permissions or internal error log.", discord.Color.red()), ephemeral=True)
            return

        file = discord.File(file_buffer, filename="rank_card.png")
        embed = self.premium_embed(
            f"{member.display_name}'s Rank",
            f"**Level:** {level} | **XP:** {current_xp}/{xp_needed} | **Rank:** #{rank}/{len(sorted_users)}"
        )
        embed.set_image(url="attachment://rank_card.png")
        
        # Use ephemeral for slash commands, normal reply for prefix
        ephemeral = isinstance(source, discord.Interaction)

        await self._send_response(source, embed, file, ephemeral=ephemeral)

    # --- PREFIX COMMAND ---
    @commands.command(name="rank", description="View your or another member's rank card")
    async def rank_prefix(self, ctx: commands.Context, member: Optional[discord.Member]):
        member = member or ctx.author
        # Ensure member is discord.Member for type hint consistency
        await self._handle_rank(ctx, member)

    # --- SLASH COMMAND ---
    @app_commands.command(name="rank", description="View your or another member's rank card")
    @app_commands.describe(member="The member whose rank you want to check.")
    async def rank_slash(self, interaction: discord.Interaction, member: Optional[discord.Member]):
        member = member or interaction.user
        member = cast(discord.Member, member) 
        await self._handle_rank(interaction, member)

    # ------------------------------------------------------
    # 🏆 Leaderboard Command (Unified)
    # ------------------------------------------------------
    async def _handle_leaderboard(self, source: Union[commands.Context, discord.Interaction]):
        if not source.guild:
            await self._send_response(source, self.premium_embed("Error", "❌ This command must be used in a server.", discord.Color.red()), ephemeral=True)
            return
        
        # Defer interaction for slash commands
        if isinstance(source, discord.Interaction) and not source.response.is_done():
            await source.response.defer(ephemeral=True)
            
        guild_id = source.guild.id
        guild_levels = load_data(LEVELS_FILE).get(str(guild_id), {})

        # Filter and sort users by total_xp
        sorted_users = sorted(
            [
                (uid, data['total_xp']) 
                for uid, data in guild_levels.items() if data.get('total_xp', 0) > 0
            ], 
            key=lambda item: item[1], 
            reverse=True
        )

        if not sorted_users:
            await self._send_response(source, self.premium_embed("Leaderboard", "The leaderboard is empty. Start chatting to gain XP!"), ephemeral=True)
            return

        top_10 = sorted_users[:10]
        
        leaderboard_text = []
        for i, (user_id_str, total_xp) in enumerate(top_10):
            user = source.guild.get_member(int(user_id_str))
            
            # Fetch level info based on total_xp
            level_info = get_level_info(total_xp)
            
            name = user.display_name if user else f"User ID: {user_id_str}"
            
            # Add emojis for top ranks
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i + 1, "🏅")
            
            leaderboard_text.append(
                f"{rank_emoji} **#{i+1}:** {name} - Level **{level_info['level']}** ({total_xp:,} XP)"
            )
        
        embed = self.premium_embed(
            "👑 Server Leaderboard (Top 10)",
            "\n".join(leaderboard_text)
        )
        
        # Find user's rank (if they are in the guild and have XP)
        user_id = source.author.id if isinstance(source, commands.Context) else source.user.id
        user_rank = next((i + 1 for i, (uid, xp) in enumerate(sorted_users) if int(uid) == user_id), None)
        
        if user_rank is not None:
            embed.set_footer(text=f"Your Rank: #{user_rank} | Total Ranked Users: {len(sorted_users)}")
        else:
            embed.set_footer(text=f"Total Ranked Users: {len(sorted_users)}")

        await self._send_response(source, embed, ephemeral=True)

    # --- PREFIX COMMAND ---
    @commands.command(name="leaderboard", description="View the server's XP leaderboard")
    async def leaderboard_prefix(self, ctx: commands.Context):
        await self._handle_leaderboard(ctx)

    # --- SLASH COMMAND ---
    @app_commands.command(name="leaderboard", description="View the server's XP leaderboard")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await self._handle_leaderboard(interaction)


    # ------------------------------------------------------
    # ⚙️ Level Settings (Prefix Group) & Unified Handler
    # ------------------------------------------------------
    @commands.group(name="levelsettings", description="Configure the leveling system for this server", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def levelsettings_prefix(self, ctx: commands.Context):
        config = get_guild_config(ctx.guild.id)
        
        # Display current settings
        role_mentions = "\n".join([
            f"Level **{lvl}**: <@&{rid}>"
            for lvl, rid in config['level_roles'].items()
        ]) or "None"
        
        ignore_channel_mentions = "\n".join([
            f"<#{cid}>"
            for cid in config['ignore_channels']
        ]) or "None"
        
        embed = self.premium_embed(
            "Server Leveling Configuration",
            "Use the subcommands (`!levelsettings <command>...`) to update settings."
            "---"
        )
        
        embed.add_field(name="XP Gain", value=f"Min/Max: `{config['xp_min']}-{config['xp_max']}` XP\nCooldown: `{config['xp_cooldown']}` seconds", inline=True)
        embed.add_field(name="Level Up Message", value=f"Enabled: `{config['level_up_message_enabled']}`\nChannel: <#{config['level_up_channel']}>" if config['level_up_channel'] else f"Enabled: `{config['level_up_message_enabled']}`\nChannel: `Current Channel`", inline=True)
        embed.add_field(name="Level Roles", value=role_mentions, inline=False)
        embed.add_field(name="Ignored Channels", value=ignore_channel_mentions, inline=False)
        embed.add_field(name="Rank Card", value=f"Background: {'Configured' if config['rank_card_background'] else 'Default'}\nText Color: `{config['rank_card_text_color']}`", inline=False)
        
        await ctx.reply(embed=embed)


    # --- Unified Settings Handler for Subcommands ---
    async def _handle_level_setting(self, source: Union[commands.Context, discord.Interaction], key: str, value: Any):
        if not source.guild:
             await self._send_response(source, self.premium_embed("Error", "❌ This command must be used in a server.", discord.Color.red()), ephemeral=True)
             return
             
        # Defer interaction for slash commands
        if isinstance(source, discord.Interaction) and not source.response.is_done():
            await source.response.defer(ephemeral=True)
             
        guild_id = source.guild.id
        config = get_guild_config(guild_id)
        updates = {}
        message = ""

        if key == "setrole":
            try:
                level = int(value[0])
                role = value[1] # discord.Role 
                
                if not role or not isinstance(role, discord.Role):
                    await self._send_response(source, self.premium_embed("Error", "❌ Invalid role or level provided."), ephemeral=True)
                    return
                
                config["level_roles"][str(level)] = role.id
                updates["level_roles"] = config["level_roles"]
                message = f"Level **{level}** now grants the {role.mention} role."
            except (ValueError, IndexError):
                await self._send_response(source, self.premium_embed("Error", "❌ Usage: `!levelsettings setrole <level> <role>`"), ephemeral=True)
                return

        elif key == "clearrole":
            try:
                level = str(value)
                if level in config["level_roles"]:
                    del config["level_roles"][level]
                    updates["level_roles"] = config["level_roles"]
                    message = f"Cleared level role for level **{level}**."
                else:
                    await self._send_response(source, self.premium_embed("Error", f"❌ No level role configured for level **{level}**."), ephemeral=True)
                    return
            except ValueError:
                await self._send_response(source, self.premium_embed("Error", "❌ Level must be a number."), ephemeral=True)
                return

        elif key == "ignorechannel":
            channel = value # discord.TextChannel
            if not channel or not isinstance(channel, discord.TextChannel):
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid channel provided."), ephemeral=True)
                return

            if channel.id in config["ignore_channels"]:
                config["ignore_channels"].remove(channel.id)
                message = f"Removed {channel.mention} from ignored channels. XP will now be gained here."
            else:
                config["ignore_channels"].append(channel.id)
                message = f"Added {channel.mention} to ignored channels. XP will not be gained here."
            updates["ignore_channels"] = config["ignore_channels"]

        elif key == "xpconfig":
            try:
                min_xp, max_xp = value
                min_xp = int(min_xp)
                max_xp = int(max_xp)
                if not (1 <= min_xp <= max_xp <= 100):
                    await self._send_response(source, self.premium_embed("Error", "❌ Min and Max XP must be between 1 and 100, and Min must be <= Max."), ephemeral=True)
                    return
                updates["xp_min"] = min_xp
                updates["xp_max"] = max_xp
                message = f"XP per message set to **{min_xp}-{max_xp}**."
            except (ValueError, IndexError):
                await self._send_response(source, self.premium_embed("Error", "❌ Usage: `!levelsettings xpconfig <min_xp> <max_xp>` (must be numbers)"), ephemeral=True)
                return
                
        elif key == "rankcardconfig":
            try:
                bg_url, text_color = value
                if not (bg_url.startswith("http") or bg_url.lower() == 'default'):
                    await self._send_response(source, self.premium_embed("Error", "❌ Background URL must be a valid URL or 'default'."), ephemeral=True)
                    return
                
                # Simple hex color validation (must start with # and be 7 chars long)
                if not (text_color.startswith("#") and len(text_color) == 7 and all(c in '0123456789abcdefABCDEF#' for c in text_color)):
                    await self._send_response(source, self.premium_embed("Error", "❌ Text color must be a valid 6-digit hex code (e.g., `#FFFFFF`)."), ephemeral=True)
                    return
                
                updates["rank_card_background"] = bg_url if bg_url.lower() != 'default' else None
                updates["rank_card_text_color"] = text_color
                message = "Rank card background and text color updated."
            except (ValueError, IndexError):
                await self._send_response(source, self.premium_embed("Error", "❌ Usage: `!levelsettings rankcardconfig <bg_url or 'default'> <#hex_color>`"), ephemeral=True)
                return

        elif key == "messagechannel":
            channel = value # discord.TextChannel
            if not channel or not isinstance(channel, discord.TextChannel):
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid channel provided."), ephemeral=True)
                return
            
            updates["level_up_channel"] = channel.id
            message = f"Level up messages will now be sent in {channel.mention}."

        elif key == "togglemessage":
            state = value # bool 
            updates["level_up_message_enabled"] = state
            message = f"Level up messages are now **{'enabled' if state else 'disabled'}**."

        elif key == "cooldown":
            try:
                cooldown_seconds = int(value)
                if not (5 <= cooldown_seconds <= 300):
                    await self._send_response(source, self.premium_embed("Error", "❌ Cooldown must be between 5 and 300 seconds."), ephemeral=True)
                    return
                updates["xp_cooldown"] = cooldown_seconds
                message = f"XP cooldown set to **{cooldown_seconds}** seconds."
            except ValueError:
                await self._send_response(source, self.premium_embed("Error", "❌ Cooldown must be a number."), ephemeral=True)
                return

        
        if updates:
            update_guild_config(guild_id, updates)
            embed = self.premium_embed("Configuration Updated", f"✅ {message}", discord.Color.blue())
            await self._send_response(source, embed, ephemeral=True)
        else:
            # Should not happen if a command hits this handler, but serves as a catch-all
            await self._send_response(source, self.premium_embed("Error", "❌ An unexpected error occurred during configuration update."), ephemeral=True)


    # --- Prefix Subcommands ---
    @levelsettings_prefix.command(name="setrole", description="Set a role to be granted at a specific level")
    async def setrole_prefix(self, ctx: commands.Context, level: int, role: discord.Role):
        await self._handle_level_setting(ctx, "setrole", [level, role])

    @levelsettings_prefix.command(name="clearrole", description="Remove the role assigned to a specific level")
    async def clearrole_prefix(self, ctx: commands.Context, level: int):
        await self._handle_level_setting(ctx, "clearrole", str(level))

    @levelsettings_prefix.command(name="ignorechannel", description="Toggle a channel for XP gain (ignored/not ignored)")
    async def ignorechannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._handle_level_setting(ctx, "ignorechannel", channel)

    @levelsettings_prefix.command(name="xpconfig", description="Set the min and max XP gained per message")
    async def xpconfig_prefix(self, ctx: commands.Context, min_xp: int, max_xp: int):
        await self._handle_level_setting(ctx, "xpconfig", [min_xp, max_xp])

    @levelsettings_prefix.command(name="rankcardconfig", description="Set the background image URL and text color for rank cards")
    async def rankcardconfig_prefix(self, ctx: commands.Context, background_url: str, text_color: str):
        await self._handle_level_setting(ctx, "rankcardconfig", [background_url, text_color])

    @levelsettings_prefix.command(name="messagechannel", description="Set the channel for level up messages")
    async def messagechannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._handle_level_setting(ctx, "messagechannel", channel)

    @levelsettings_prefix.command(name="togglemessage", description="Enable or disable level up messages")
    async def togglemessage_prefix(self, ctx: commands.Context, state: bool):
        await self._handle_level_setting(ctx, "togglemessage", state)
        
    @levelsettings_prefix.command(name="cooldown", description="Set the cooldown in seconds between XP gain (5-300)")
    async def cooldown_prefix(self, ctx: commands.Context, cooldown_seconds: int):
        await self._handle_level_setting(ctx, "cooldown", cooldown_seconds)


    # --- Slash Subcommands (registered under the class Group 'levelsettings') ---
    @levelsettings.command(name="setrole", description="Set a role to be granted at a specific level")
    @app_commands.describe(level="The level to grant the role at (e.g., 5)", role="The role to be granted")
    @app_commands.default_permissions(administrator=True)
    async def setrole_slash(self, interaction: discord.Interaction, level: app_commands.Range[int, 1], role: discord.Role):
        await self._handle_level_setting(interaction, "setrole", [level, role])

    @levelsettings.command(name="clearrole", description="Remove the role assigned to a specific level")
    @app_commands.describe(level="The level to clear the role for")
    @app_commands.default_permissions(administrator=True)
    async def clearrole_slash(self, interaction: discord.Interaction, level: app_commands.Range[int, 1]):
        await self._handle_level_setting(interaction, "clearrole", str(level))

    @levelsettings.command(name="ignorechannel", description="Toggle a channel for XP gain (ignored/not ignored)")
    @app_commands.describe(channel="The channel to toggle XP for")
    @app_commands.default_permissions(administrator=True)
    async def ignorechannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._handle_level_setting(interaction, "ignorechannel", channel)

    @levelsettings.command(name="xpconfig", description="Set the min and max XP gained per message")
    @app_commands.describe(min_xp="Minimum XP (1-100)", max_xp="Maximum XP (min_xp-100)")
    @app_commands.default_permissions(administrator=True)
    async def xpconfig_slash(self, interaction: discord.Interaction, min_xp: app_commands.Range[int, 1, 100], max_xp: app_commands.Range[int, 1, 100]):
        # Note: Logic to ensure min <= max is inside _handle_level_setting
        await self._handle_level_setting(interaction, "xpconfig", [min_xp, max_xp])

    @levelsettings.command(name="rankcardconfig", description="Set the background image URL and text color for rank cards")
    @app_commands.describe(background_url="URL or 'default'", text_color="Hex color code (e.g., #FFFFFF')")
    @app_commands.default_permissions(administrator=True)
    async def rankcardconfig_slash(self, interaction: discord.Interaction, background_url: str, text_color: str):
        await self._handle_level_setting(interaction, "rankcardconfig", [background_url, text_color])

    @levelsettings.command(name="messagechannel", description="Set the channel for level up messages")
    @app_commands.describe(channel="The channel to send level up messages to")
    @app_commands.default_permissions(administrator=True)
    async def messagechannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._handle_level_setting(interaction, "messagechannel", channel)

    @levelsettings.command(name="togglemessage", description="Enable or disable level up messages")
    @app_commands.describe(state="True to enable, False to disable")
    @app_commands.default_permissions(administrator=True)
    async def togglemessage_slash(self, interaction: discord.Interaction, state: bool):
        await self._handle_level_setting(interaction, "togglemessage", state)
        
    @levelsettings.command(name="cooldown", description="Set the cooldown in seconds between XP gain (5-300)")
    @app_commands.describe(cooldown_seconds="The cooldown in the seconds (5-300)")
    @app_commands.default_permissions(administrator=True)
    async def cooldown_slash(self, interaction: discord.Interaction, cooldown_seconds: app_commands.Range[int, 5, 300]):
        await self._handle_level_setting(interaction, "cooldown", cooldown_seconds)


    # ------------------------------------------------------
    # ➕ Level Admin Commands (Unified Handlers)
    # ------------------------------------------------------

    async def _handle_level_admin_action(self, source: Union[commands.Context, discord.Interaction], action: str, member: discord.Member, value: Optional[int] = None):
        if not source.guild:
             await self._send_response(source, self.premium_embed("Error", "❌ This command must be used in a server.", discord.Color.red()), ephemeral=True)
             return
             
        # Defer interaction for slash commands
        if isinstance(source, discord.Interaction) and not source.response.is_done():
            await source.response.defer(ephemeral=True)
        
        guild_id = source.guild.id
        user_data = get_user_data(guild_id, member.id)
        
        updates = {}
        message = ""
        
        if action == "resetuser":
            updates = {
                "xp": 0,
                "level": 0,
                "total_xp": 0,
                "last_message": datetime.datetime.min # Resets cooldown
            }
            message = f"Leveling data for {member.mention} has been **reset**."
        
        elif action == "addxp":
            if value is None or value < 0:
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid XP amount provided."), ephemeral=True)
                return
            
            user_data["total_xp"] += value
            
            # Recalculate level and current XP
            new_info = get_level_info(user_data["total_xp"])
            updates.update(new_info)
            message = f"Added **{value:,} XP** to {member.mention}. New level: **{new_info['level']}**."

        elif action == "removexp":
            if value is None or value < 0:
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid XP amount provided."), ephemeral=True)
                return
            
            # Ensure total_xp doesn't go below zero
            user_data["total_xp"] = max(0, user_data["total_xp"] - value)
            
            # Recalculate level and current XP
            new_info = get_level_info(user_data["total_xp"])
            updates.update(new_info)
            message = f"Removed **{value:,} XP** from {member.mention}. New level: **{new_info['level']}**."
            
        elif action == "setlevel":
            if value is None or value < 0:
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid level provided."), ephemeral=True)
                return
            
            # Calculate the minimum total XP required for the new level
            required_total_xp = get_total_xp_required(value)
            
            user_data["total_xp"] = required_total_xp
            
            # Recalculate level and current XP
            new_info = get_level_info(user_data["total_xp"])
            updates.update(new_info)
            message = f"Set {member.mention}'s level to **{value}** ({required_total_xp:,} total XP)."

        elif action == "setxp":
            if value is None or value < 0:
                await self._send_response(source, self.premium_embed("Error", "❌ Invalid XP amount provided."), ephemeral=True)
                return

            # Set total_xp directly
            user_data["total_xp"] = value
            
            # Recalculate level and current XP
            new_info = get_level_info(user_data["total_xp"])
            updates.update(new_info)
            message = f"Set {member.mention}'s total XP to **{value:,}**. New level: **{new_info['level']}**."

        else:
            await self._send_response(source, self.premium_embed("Error", "❌ Invalid admin action."), ephemeral=True)
            return

        # Update the user data
        if updates:
            # We explicitly update the internal dictionary first to ensure last_message is correctly handled if resetuser
            final_updates = {
                "xp": updates.get("xp", user_data["xp"]),
                "level": updates.get("level", user_data["level"]),
                "total_xp": updates.get("total_xp", user_data["total_xp"]),
                # Only reset last_message if it was explicitly updated (e.g., by resetuser)
                "last_message": updates.get("last_message", user_data["last_message"])
            }
            update_user_data(guild_id, member.id, final_updates)
            
            embed = self.premium_embed(f"User Level Updated: {action.title()}", f"✅ {message}", discord.Color.green())
            await self._send_response(source, embed, ephemeral=True)

    # --- RESET USER (Prefix & Slash) ---
    @commands.command(name="resetuser", description="Reset a member's level and XP to 0")
    @commands.has_permissions(administrator=True)
    async def resetuser_prefix(self, ctx: commands.Context, member: discord.Member):
        await self._handle_level_admin_action(ctx, "resetuser", member)

    @app_commands.command(name="resetuser", description="Reset a member's level and XP to 0")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member whose data will be reset.")
    async def resetuser_slash(self, interaction: discord.Interaction, member: discord.Member):
        await self._handle_level_admin_action(interaction, "resetuser", member)

    # --- ADD XP (Prefix & Slash) ---
    @commands.command(name="addxp", description="Add XP to a member's total XP")
    @commands.has_permissions(administrator=True)
    async def addxp_prefix(self, ctx: commands.Context, member: discord.Member, xp: int):
        await self._handle_level_admin_action(ctx, "addxp", member, xp)

    @app_commands.command(name="addxp", description="Add XP to a member's total XP")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member to add XP to.", xp="The amount of XP to add (must be > 0).")
    async def addxp_slash(self, interaction: discord.Interaction, member: discord.Member, xp: app_commands.Range[int, 1]):
        await self._handle_level_admin_action(interaction, "addxp", member, xp)

    # --- REMOVE XP (Prefix & Slash) ---
    @commands.command(name="removexp", description="Remove XP from a member's total XP")
    @commands.has_permissions(administrator=True)
    async def removexp_prefix(self, ctx: commands.Context, member: discord.Member, xp: int):
        await self._handle_level_admin_action(ctx, "removexp", member, xp)

    @app_commands.command(name="removexp", description="Remove XP from a member's total XP")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member to remove XP from.", xp="The amount of XP to remove (must be > 0).")
    async def removexp_slash(self, interaction: discord.Interaction, member: discord.Member, xp: app_commands.Range[int, 1]):
        await self._handle_level_admin_action(interaction, "removexp", member, xp)

    # --- SET LEVEL (Prefix & Slash) ---
    @commands.command(name="setlevel", description="Set a member to a specific level (and corresponding XP)")
    @commands.has_permissions(administrator=True)
    async def setlevel_prefix(self, ctx: commands.Context, member: discord.Member, level: int):
        await self._handle_level_admin_action(ctx, "setlevel", member, level)

    @app_commands.command(name="setlevel", description="Set a member to a specific level (and corresponding XP)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member to set the level for.", level="The level to set (0 or higher).")
    async def setlevel_slash(self, interaction: discord.Interaction, member: discord.Member, level: app_commands.Range[int, 0]):
        await self._handle_level_admin_action(interaction, "setlevel", member, level)

    # --- SET XP (Prefix & Slash) ---
    @commands.command(name="setxp", description="Set a member's total XP directly")
    @commands.has_permissions(administrator=True)
    async def setxp_prefix(self, ctx: commands.Context, member: discord.Member, xp: int):
        await self._handle_level_admin_action(ctx, "setxp", member, xp)

    @app_commands.command(name="setxp", description="Set a member's total XP directly")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="The member to set the total XP for.", xp="The total XP to set (0 or higher).")
    async def setxp_slash(self, interaction: discord.Interaction, member: discord.Member, xp: app_commands.Range[int, 0]):
        await self._handle_level_admin_action(interaction, "setxp", member, xp)

    # --- RESET SERVER (Prefix & Slash) ---
    @commands.command(name="resetserver", description="Reset ALL level and XP data for the entire server")
    @commands.has_permissions(administrator=True)
    async def resetserver_prefix(self, ctx: commands.Context):
        if not ctx.guild:
            return

        levels = load_data(LEVELS_FILE)
        guild_id_str = str(ctx.guild.id)
        
        if guild_id_str in levels:
            del levels[guild_id_str]
            save_data(LEVELS_FILE, levels)
            embed = self.premium_embed("Server Reset", "✅ Leveling data for this server has been **cleared**.")
            await ctx.reply(embed=embed)
        else:
            embed = self.premium_embed("Server Reset", "⚠️ No leveling data found to reset.")
            await ctx.reply(embed=embed)

    @app_commands.command(name="resetserver", description="Reset ALL level and XP data for the entire server")
    @app_commands.default_permissions(administrator=True)
    async def resetserver_slash(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=True)

        levels = load_data(LEVELS_FILE)
        guild_id_str = str(interaction.guild_id)
        
        if guild_id_str in levels:
            del levels[guild_id_str]
            save_data(LEVELS_FILE, levels)
            embed = self.premium_embed("Server Reset", "✅ Leveling data for this server has been **cleared**.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = self.premium_embed("Server Reset", "⚠️ No leveling data found to reset.")
            await interaction.followup.send(embed=embed, ephemeral=True)


    # --- SYNC (Prefix & Slash) ---
    @commands.command(name="sync", description="Sync the leveling data with member list (removes inactive members)")
    @commands.is_owner()
    async def sync_prefix(self, ctx: commands.Context):
        if not ctx.guild:
            return

        levels = load_data(LEVELS_FILE)
        guild_id_str = str(ctx.guild.id)
        
        if guild_id_str not in levels:
            return await ctx.reply("⚠️ No leveling data found to sync.")

        removed_count = 0
        current_members = {str(m.id) for m in ctx.guild.members}
        
        # Identify members in data but not in guild
        user_ids_to_remove = [
            user_id 
            for user_id in levels[guild_id_str].keys() 
            if user_id not in current_members
        ]

        for user_id in user_ids_to_remove:
            del levels[guild_id_str][user_id]
            removed_count += 1
            
        save_data(LEVELS_FILE, levels)
        
        embed = self.premium_embed("Data Sync Complete", f"✅ Removed **{removed_count}** entries for members no longer in the server.")
        await ctx.reply(embed=embed)

    @app_commands.command(name="sync", description="Sync the leveling data with member list (removes inactive members)")
    @commands.is_owner() # Use prefix check for owner for consistency with existing command
    async def sync_slash(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=True)

        levels = load_data(LEVELS_FILE)
        guild_id_str = str(interaction.guild_id)
        
        if guild_id_str not in levels:
            return await interaction.followup.send("⚠️ No leveling data found to sync.", ephemeral=True)

        removed_count = 0
        # Fetch members list - ensure intents are correct if this fails
        try:
            current_members = {str(m.id) for m in interaction.guild.members}
        except Exception:
            # Fallback for large guilds or if members list is incomplete
            current_members = {str(m.id) for m in await interaction.guild.fetch_members(limit=None).flatten()}
            
        # Identify members in data but not in guild
        user_ids_to_remove = [
            user_id 
            for user_id in levels[guild_id_str].keys() 
            if user_id not in current_members
        ]

        for user_id in user_ids_to_remove:
            del levels[guild_id_str][user_id]
            removed_count += 1
            
        save_data(LEVELS_FILE, levels)
        
        embed = self.premium_embed("Data Sync Complete", f"✅ Removed **{removed_count}** entries for members no longer in the server.")
        await interaction.followup.send(embed=embed, ephemeral=True)


    # ------------------------------------------------------
    # 🚨 Error Handling
    # ------------------------------------------------------
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Ignore errors for commands that don't exist
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingPermissions) or isinstance(error, commands.MissingRole) or isinstance(error, commands.CheckFailure):
            embed = self.premium_embed(
                "Permission Denied", 
                "❌ You need **Administrator** permissions to use this command.", 
                discord.Color.red()
            )
            await ctx.reply(embed=embed)
        elif isinstance(error, commands.BadArgument):
             embed = self.premium_embed(
                "Invalid Input", 
                f"❌ One or more arguments were invalid. Please check the command usage: `{error}`", 
                discord.Color.red()
            )
             await ctx.reply(embed=embed)
        else:
            print(f"An unexpected error occurred in a prefix command: {error}")
            
    
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Handle Missing Permissions error for admin commands
        if isinstance(error, app_commands.MissingPermissions):
            embed = self.premium_embed(
                "Permission Denied", 
                "❌ You need **Administrator** permissions to use this command.", 
                discord.Color.red()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            print(f"An unexpected error occurred in an app command: {error}")


# ------------------------------------------------------
# 🔧 SETUP FUNCTION
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))