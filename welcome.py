# welcome.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
from typing import Union, Optional # Added for structured command splitting

# ------------------------------------------------------
# 📁 File Path Setup
# ------------------------------------------------------
WELCOME_FILE = "data/welcome.json"

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# Load welcome data or initialize empty
try:
    if os.path.exists(WELCOME_FILE):
        with open(WELCOME_FILE, "r") as f:
            welcome_data = json.load(f)
    else:
        welcome_data = {}
except json.JSONDecodeError:
    # Handle case where file is corrupted or empty
    print(f"[WARN] Failed to decode {WELCOME_FILE}. Initializing empty data.")
    welcome_data = {}


def save_data():
    """Save welcome configuration data."""
    # Ensure all data is saved as strings (e.g., Guild IDs)
    data_to_save = {str(k): v for k, v in welcome_data.items()}
    with open(WELCOME_FILE, "w") as f:
        json.dump(data_to_save, f, indent=4)


# ------------------------------------------------------
# 🌟 MAIN WELCOME CLASS
# ------------------------------------------------------
class Welcome(commands.Cog):
    """Premium Welcome & Leave System"""

    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------
    # 🌟 Premium Embed Template
    # ------------------------------------------------------
    def premium_embed(self, title: str, desc: str, color=discord.Color.gold()):
        """Creates a standardized premium-style embed."""
        # Use discord.utils.utcnow() for consistency
        embed = discord.Embed(
            title=f"✨ {title} ✨",
            description=desc,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(
            text=f"{self.bot.user.name} • Premium System",
            icon_url=self.bot.user.display_avatar.url
        )
        return embed

    # ------------------------------------------------------
    # ⚙️ Response Helper
    # ------------------------------------------------------
    async def _send_response(self, context: Union[commands.Context, discord.Interaction], embed: discord.Embed, ephemeral: bool = False):
        """Handles sending response for both prefix and slash commands."""
        if isinstance(context, commands.Context):
            # Prefix command: cannot be ephemeral, use reply
            await context.reply(embed=embed, mention_author=False)
        else:
            # Slash command: respects ephemeral setting
            if context.response.is_done():
                 await context.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                 await context.response.send_message(embed=embed, ephemeral=ephemeral)


    # ------------------------------------------------------
    # 1. Welcome Guide Command (Renamed from welcomehelp)
    # ------------------------------------------------------
    async def _welcomeguide_logic(self, context: Union[commands.Context, discord.Interaction]):
        """Core logic for displaying the welcome setup guide."""
        
        embed = discord.Embed(
            title="⚙️ Welcome System Setup Guide",
            description="Here's how to set up premium welcome and leave messages for your server.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Get guild icon safely
        guild_icon_url = context.guild.icon.url if context.guild and context.guild.icon else self.bot.user.display_avatar.url
        embed.set_thumbnail(url=guild_icon_url)

        embed.add_field(
            name="`/setwelcomechannel <channel>`", # Updated name for the guide
            value="Sets the channel for welcome messages.\n*Example:* `/setwelcomechannel #welcome`",
            inline=False
        )
        embed.add_field(
            name="`/setleavechannel <channel>`", # Updated name for the guide
            value="Sets the channel for leave messages.\n*Example:* `/setleavechannel #goodbye`",
            inline=False
        )
        embed.add_field(
            name="`/setautorole <role>`",
            value="Automatically assigns a role to new members.\n*Example:* `/setautorole @Member`",
            inline=False
        )
        embed.add_field(
            name="`/setwelcomebg <image_url>`",
            value="Sets a background image/GIF for welcome messages.\n*Tip:* Upload to Imgur and use the direct URL.",
            inline=False
        )
        embed.add_field(
            name="`/setleavebg <image_url>`",
            value="Sets a background image/GIF for leave messages.\n*Tip:* Upload to Imgur and use the direct URL.",
            inline=False
        )

        embed.set_footer(
            text=f"{self.bot.user.name} • Welcome System",
            icon_url=self.bot.user.display_avatar.url
        )
        
        # Original used ephemeral=True, which is only respected by slash/hybrid commands
        await self._send_response(context, embed, ephemeral=True)

    @commands.command(
        name="welcomeguide",
        help="Get setup guide for the premium welcome system."
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def welcomeguide_prefix(self, ctx: commands.Context):
        await self._welcomeguide_logic(ctx)

    @app_commands.command(
        name="welcomeguide",
        description="Get setup guide for the premium welcome system."
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def welcomeguide_slash(self, interaction: discord.Interaction):
        await self._welcomeguide_logic(interaction)


    # ------------------------------------------------------
    # 2. Set Welcome Channel (Renamed from setwelcome)
    # ------------------------------------------------------
    async def _setwelcomechannel_logic(self, context: Union[commands.Context, discord.Interaction], channel: discord.TextChannel):
        """Core logic for setting the welcome channel."""
        guild_id = str(context.guild.id)
        # Use .copy() to safely modify data without unintended side effects
        data = welcome_data.get(guild_id, {}).copy()
        data["welcome_channel"] = channel.id
        welcome_data[guild_id] = data
        save_data()
        
        embed = self.premium_embed("Configuration Updated", f"Welcome messages will now be sent in {channel.mention}.")
        await self._send_response(context, embed)

    @commands.command(name="setwelcomechannel", help="Set the channel for welcome messages.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setwelcomechannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._setwelcomechannel_logic(ctx, channel)

    @app_commands.command(name="setwelcomechannel", description="Set the channel for welcome messages.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(channel="The channel to send welcome messages in.")
    async def setwelcomechannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._setwelcomechannel_logic(interaction, channel)


    # ------------------------------------------------------
    # 3. Set Leave Channel (Renamed from setleave)
    # ------------------------------------------------------
    async def _setleavechannel_logic(self, context: Union[commands.Context, discord.Interaction], channel: discord.TextChannel):
        """Core logic for setting the leave channel."""
        guild_id = str(context.guild.id)
        data = welcome_data.get(guild_id, {}).copy()
        data["leave_channel"] = channel.id
        welcome_data[guild_id] = data
        save_data()
        
        embed = self.premium_embed("Configuration Updated", f"Leave messages will now be sent in {channel.mention}.")
        await self._send_response(context, embed)

    @commands.command(name="setleavechannel", help="Set the channel for leave messages.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setleavechannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._setleavechannel_logic(ctx, channel)

    @app_commands.command(name="setleavechannel", description="Set the channel for leave messages.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(channel="The channel to send leave messages in.")
    async def setleavechannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._setleavechannel_logic(interaction, channel)


    # ------------------------------------------------------
    # 4. Set Auto Role (Name retained: setautorole)
    # ------------------------------------------------------
    async def _setautorole_logic(self, context: Union[commands.Context, discord.Interaction], role: discord.Role):
        """Core logic for setting the auto role."""
        if not context.guild:
            # Should not happen due to @commands.guild_only() but for safety
            embed = self.premium_embed("Error", "This command must be used in a server.", discord.Color.red())
            return await self._send_response(context, embed)
            
        # Context extraction for permission check
        guild = context.guild
        
        # Permission check: Bot's top role must be higher than the role to assign
        if guild.me.top_role <= role:
            embed = self.premium_embed(
                "Permission Error",
                f"I cannot assign {role.mention} because it's higher than or equal to my top role. Please move my role above it.",
                color=discord.Color.red()
            )
            return await self._send_response(context, embed)

        guild_id = str(guild.id)
        data = welcome_data.get(guild_id, {}).copy()
        data["autorole"] = role.id
        welcome_data[guild_id] = data
        save_data()
        
        embed = self.premium_embed("Configuration Updated", f"New members will now receive {role.mention} automatically.")
        await self._send_response(context, embed)


    @commands.command(name="setautorole", help="Automatically assign a role to new members.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setautorole_prefix(self, ctx: commands.Context, role: discord.Role):
        await self._setautorole_logic(ctx, role)

    @app_commands.command(name="setautorole", description="Automatically assign a role to new members.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(role="The role to automatically assign to new members.")
    async def setautorole_slash(self, interaction: discord.Interaction, role: discord.Role):
        await self._setautorole_logic(interaction, role)


    # ------------------------------------------------------
    # 5. Set Welcome Background (Name retained: setwelcomebg)
    # ------------------------------------------------------
    async def _setwelcomebg_logic(self, context: Union[commands.Context, discord.Interaction], url: str):
        """Core logic for setting the welcome background image/GIF."""
        guild_id = str(context.guild.id)
        data = welcome_data.get(guild_id, {}).copy()
        data["welcome_bg"] = url
        welcome_data[guild_id] = data
        save_data()
        
        embed = self.premium_embed("Configuration Updated", "Custom background set for welcome messages.")
        await self._send_response(context, embed)


    @commands.command(name="setwelcomebg", help="Set background image/GIF for welcome messages.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setwelcomebg_prefix(self, ctx: commands.Context, url: str):
        await self._setwelcomebg_logic(ctx, url)

    @app_commands.command(name="setwelcomebg", description="Set background image/GIF for welcome messages.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(url="Direct URL of the image or GIF to use as background.")
    async def setwelcomebg_slash(self, interaction: discord.Interaction, url: str):
        await self._setwelcomebg_logic(interaction, url)


    # ------------------------------------------------------
    # 6. Set Leave Background (Name retained: setleavebg)
    # ------------------------------------------------------
    async def _setleavebg_logic(self, context: Union[commands.Context, discord.Interaction], url: str):
        """Core logic for setting the leave background image/GIF."""
        guild_id = str(context.guild.id)
        data = welcome_data.get(guild_id, {}).copy()
        data["leave_bg"] = url
        welcome_data[guild_id] = data
        save_data()
        
        embed = self.premium_embed("Configuration Updated", "Custom background set for leave messages.")
        await self._send_response(context, embed)

    @commands.command(name="setleavebg", help="Set background image/GIF for leave messages.")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setleavebg_prefix(self, ctx: commands.Context, url: str):
        await self._setleavebg_logic(ctx, url)

    @app_commands.command(name="setleavebg", description="Set background image/GIF for leave messages.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(url="Direct URL of the image or GIF to use as background.")
    async def setleavebg_slash(self, interaction: discord.Interaction, url: str):
        await self._setleavebg_logic(interaction, url)


    # ------------------------------------------------------
    # 💬 Member Join Event
    # ------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return  # Ignore bots joining

        guild_id = str(member.guild.id)
        data = welcome_data.get(guild_id, {})
        channel_id = data.get("welcome_channel")
        autorole_id = data.get("autorole")

        # Send Welcome Message
        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel and channel.permissions_for(member.guild.me).send_messages:
                bg_url = data.get("welcome_bg")

                embed = discord.Embed(
                    description=f"👋 Welcome, {member.mention}! We're thrilled to have you join our community! ✨\n\nEnjoy your stay 🎉",
                    color = discord.Color.from_rgb(255, 30, 30),
                    timestamp=discord.utils.utcnow() # Use utcnow
                )
                embed.set_author(
                    name=f"Welcome to {member.guild.name}!",
                    icon_url=member.guild.icon.url if member.guild.icon else self.bot.user.display_avatar.url
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Total Members", value=f"**{member.guild.member_count}** members now!", inline=True)
                embed.add_field(
                    name="Account Created", 
                    value=discord.utils.format_dt(member.created_at, "R"), # Use relative time for better display
                    inline=True
                )
                if bg_url:
                    embed.set_image(url=bg_url)
                embed.set_footer(
                    text=f"{self.bot.user.name} • Welcome System",
                    icon_url=self.bot.user.display_avatar.url
                )
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"[WARN] Missing permissions to send message in welcome channel {channel.name}.")
                except Exception as e:
                    print(f"[ERROR] Failed to send welcome message: {e}")

        # Auto Role Assignment
        if autorole_id:
            role = member.guild.get_role(autorole_id)
            if role:
                # Check bot role hierarchy before attempting to add role
                if member.guild.me.top_role > role:
                    try:
                        await member.add_roles(role, reason="Auto role assignment")
                    except discord.Forbidden:
                        print(f"[WARN] Missing permissions to assign {role.name} to {member}.")
                    except Exception as e:
                        print(f"[ERROR] Failed to assign role: {e}")
                else:
                    print(f"[WARN] Role {role.name} is too high for bot to assign to {member}.")

    # ------------------------------------------------------
    # 💬 Member Leave Event
    # ------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return  # Ignore bots leaving

        guild_id = str(member.guild.id)
        data = welcome_data.get(guild_id, {})
        channel_id = data.get("leave_channel")

        if channel_id:
            channel = member.guild.get_channel(channel_id)
            if channel and channel.permissions_for(member.guild.me).send_messages:
                bg_url = data.get("leave_bg")

                embed = discord.Embed(
                    title=f"Goodbye, {member.name} 👋",
                    description=f"**{member.name}** has left the server. We wish them the best ahead!",
                    color=discord.Color.from_rgb(60, 60, 60),
                    timestamp=discord.utils.utcnow() # Use utcnow
                )
                embed.set_author(
                    name=member.guild.name,
                    icon_url=member.guild.icon.url if member.guild.icon else self.bot.user.display_avatar.url
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                # member.guild.member_count is the correct count AFTER the member leaves
                embed.add_field(name="Members Remaining", value=f"**{member.guild.member_count}**")
                if bg_url:
                    embed.set_image(url=bg_url)
                embed.set_footer(
                    text=f"{self.bot.user.name} • Welcome System",
                    icon_url=self.bot.user.display_avatar.url
                )
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"[WARN] Missing permissions to send message in leave channel {channel.name}.")
                except Exception as e:
                    print(f"[ERROR] Failed to send leave message: {e}")


# ------------------------------------------------------
# 🔧 SETUP FUNCTION
# ------------------------------------------------------
async def setup(bot):
    """**FIXED**: setup function is now properly awaited."""
    await bot.add_cog(Welcome(bot))
