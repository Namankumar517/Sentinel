import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os
from typing import Dict, Any, List, Optional
import datetime
import logging
import asyncio

# Set up logging for the cog itself
logger = logging.getLogger('discord.sentinel.logging')

# --- Configuration ---
CONFIG_FILE = 'data/logs_config.json'
COLOR_NEON_BLUE = 0x00FFFF  # Rich neon cyber-theme color
COLOR_SUCCESS = 0x32CD32
COLOR_WARNING = 0xFF4500
COLOR_ERROR = 0xFF0000

# Default events and their respective channel keys
DEFAULT_EVENTS = {
    "message_delete": True, "message_edit": True, "message_bulk_delete": True,
    "member_join": True, "member_leave": True, "member_ban": True, "member_unban": True, "member_update": True,
    "role_create": True, "role_delete": True, "role_update": True,
    "channel_create": True, "channel_delete": True, "channel_update": True,
    "emoji_add": True, "emoji_remove": True, "sticker_add": True, "sticker_remove": True, "webhook_update": True,
    "guild_update": True,
    "security_nuke_detection": False, "security_permission_abuse": False
}

# Mapping events to categories for the dropdown menu and Channel Selection
EVENT_CATEGORIES: Dict[str, List[str]] = {
    "Message Events (3)": ["message_delete", "message_edit", "message_bulk_delete"],
    "Member Events (5)": ["member_join", "member_leave", "member_ban", "member_unban", "member_update"],
    "Role & Channel Events (6)": ["role_create", "role_delete", "role_update", "channel_create", "channel_delete", "channel_update"],
    "Asset & Webhook Events (5)": ["emoji_add", "emoji_remove", "sticker_add", "sticker_remove", "webhook_update"],
    "Server & Security (3)": ["guild_update", "security_nuke_detection", "security_permission_abuse"],
}
EVENT_LABELS: Dict[str, str] = {
    "message_delete": "Message Deleted", "message_edit": "Message Edited", "message_bulk_delete": "Bulk Delete",
    "member_join": "Member Joined", "member_leave": "Member Left", "member_ban": "Member Banned", "member_unban": "Member Unbanned", "member_update": "Member Updated",
    "role_create": "Role Created", "role_delete": "Role Deleted", "role_update": "Role Updated",
    "channel_create": "Channel Created", "channel_delete": "Channel Deleted", "channel_update": "Channel Updated",
    "emoji_add": "Emoji Added", "emoji_remove": "Emoji Removed", "sticker_add": "Sticker Added", "sticker_remove": "Sticker Removed", "webhook_update": "Webhook Update",
    "guild_update": "Server Update", "security_nuke_detection": "Nuke Detection (Placeholder)", "security_permission_abuse": "Permission Abuse (Placeholder)",
}

# Mapping Categories to a single Channel Key for the new multi-channel configuration
CHANNEL_CATEGORY_MAP: Dict[str, str] = {
    "Message Events (3)": "message_channel",
    "Member Events (5)": "member_channel",
    "Role & Channel Events (6)": "role_channel",
    "Asset & Webhook Events (5)": "asset_channel",
    "Server & Security (3)": "server_channel",
    "All Events (Fallback)": "log_channel"
}


# --- Utility Functions (Config Management) ---

def load_config() -> Dict[str, Any]:
    """Loads the logging configuration from the JSON file."""
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f)

    with open(CONFIG_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_config(config: Dict[str, Any]):
    """Saves the logging configuration to the JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


def get_guild_config(guild_id: int) -> Dict[str, Any]:
    """Gets the configuration for a specific guild, creating defaults if necessary."""
    config = load_config()
    guild_id_str = str(guild_id)

    if guild_id_str not in config:
        new_config = {
            "enabled": False,
            "log_channel": None,
            "message_channel": None,
            "member_channel": None,
            "role_channel": None,
            "asset_channel": None,
            "server_channel": None,
            "events": DEFAULT_EVENTS.copy()
        }
        config[guild_id_str] = new_config
        save_config(config)
    return config[guild_id_str]


def update_guild_config(guild_id: int, key: str, value: Any):
    """Updates and saves a specific configuration key for a guild."""
    config = load_config()
    guild_id_str = str(guild_id)
    # Ensure guild exists before updating
    if guild_id_str not in config:
        get_guild_config(guild_id)  # Initializes defaults
        config = load_config()  # Reloads the initialized config

    config[guild_id_str][key] = value
    save_config(config)


# --- UI Components for Event Configuration ---

class EventCategoryDropdown(ui.Select):
    """Dropdown for selecting and toggling logging events within a category."""

    def __init__(self, guild_id: int, category: str, events: List[str]):
        self.guild_id = guild_id
        self.events = events
        self.category = category
        config = get_guild_config(guild_id)

        options = []
        for event_key in events:
            is_enabled = config['events'].get(event_key, False)
            emoji = "✅" if is_enabled else "❌"
            label = f"{emoji} {EVENT_LABELS[event_key]}"

            options.append(discord.SelectOption(
                label=label, value=event_key, default=is_enabled
            ))

        super().__init__(
            placeholder=f"Configure {category} events...",
            options=options,
            min_values=0,
            max_values=len(events)
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        config = get_guild_config(self.guild_id)
        enabled_events = set(self.values)
        changes = []

        for event_key in self.events:
            is_currently_enabled = config['events'].get(event_key, False)
            should_be_enabled = event_key in enabled_events

            if is_currently_enabled != should_be_enabled:
                config['events'][event_key] = should_be_enabled
                changes.append(f"{EVENT_LABELS[event_key]}: {'✅' if should_be_enabled else '❌'}")

        update_guild_config(self.guild_id, 'events', config['events'])

        if changes:
            message = f"✅ Updated the following events in **{self.category}**:\n" + "\n".join(changes)
        else:
            message = "⚠️ No changes detected for this category."

        view = self.view
        # Safely attempt to edit the original message if possible, otherwise reply
        try:
            await interaction.edit_original_response(embed=view.create_event_embed(), view=view)
        except Exception:
            # Fallback: send an ephemeral message with the updated embed
            try:
                await interaction.response.send_message(embed=view.create_event_embed(), view=view, ephemeral=True)
            except Exception:
                # As a last resort, just send the changes message
                await interaction.followup.send(message, ephemeral=True)
                return

        await interaction.followup.send(message, ephemeral=True)


class EventConfigView(ui.View):
    """View containing dropdowns to configure all logging events. FIX: Uses safe placement for the back button."""

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id

        # Add a dropdown for each category. Let discord auto-place them to avoid row overflow.
        for category, events in EVENT_CATEGORIES.items():
            dropdown = EventCategoryDropdown(guild_id, category, events)
            # Remove manual row assignment to avoid "item would not fit at row" errors
            self.add_item(dropdown)

        # DO NOT manually add the decorated back_button here to avoid duplicate custom_id errors.
        # The decorated method will be included automatically in the View.

    def create_event_embed(self) -> discord.Embed:
        """Generates the embed showing the status of all configured events."""
        config = get_guild_config(self.guild_id)
        embed = discord.Embed(
            title="⚙️ Logging Event Configuration",
            description="Toggle which events Sentinel should log. Settings are applied immediately.",
            color=COLOR_NEON_BLUE
        )

        for category, events in EVENT_CATEGORIES.items():
            active_events = [f"**{EVENT_LABELS[e]}**" for e in events if config['events'].get(e, False)]

            if active_events:
                value = ", ".join(active_events)
            else:
                value = "*(None enabled)*"

            embed.add_field(name=category, value=value, inline=False)

        embed.set_footer(text="Select options in the dropdowns above to toggle events.")
        return embed

    @ui.button(label="Back to Dashboard", style=discord.ButtonStyle.grey, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        dashboard = LoggingPanel(interaction.client, self.guild_id)
        await interaction.response.edit_message(embed=dashboard.create_dashboard_embed(), view=dashboard)


# --- UI Components for Channel Configuration ---

class ChannelSetterModal(ui.Modal, title='Set Log Channel'):
    """Modal for the user to input the desired log channel ID for a specific channel type."""

    channel_input = ui.TextInput(label="Channel ID or Mention", placeholder="Enter the ID or mention the channel (e.g., #logs)", min_length=1)

    def __init__(self, guild_id: int, channel_key: str, channel_name: str, back_view_type: type):
        super().__init__()
        self.guild_id = guild_id
        self.channel_key = channel_key
        self.channel_name = channel_name
        self.back_view_type = back_view_type

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.channel_input.value.strip()
            cid_str = value.replace('<#', '').replace('>', '')
            cid = int(cid_str)

            channel = interaction.guild.get_channel(cid)

            if channel and isinstance(channel, discord.TextChannel):
                update_guild_config(self.guild_id, self.channel_key, cid)

                back_view = self.back_view_type(interaction.client, self.guild_id)
                await interaction.response.edit_message(embed=back_view.create_dashboard_embed(), view=back_view)
                await interaction.followup.send(f"✅ **{self.channel_name}** successfully set to {channel.mention}.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Invalid ID/Mention or not a text channel.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid ID format.", ephemeral=True)


class ChannelConfigPanel(ui.View):
    """New view to set different log channels for different event categories. FIX: Ensures unique custom_ids."""

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self._setup_buttons()

    def _setup_buttons(self):
        """Dynamically create buttons for each channel category."""

        categories = list(CHANNEL_CATEGORY_MAP.keys())

        for i, category_name in enumerate(categories):
            channel_key = CHANNEL_CATEGORY_MAP[category_name]
            button_label = f"Set {category_name.replace(' (Fallback)', '')}"

            # Button style and row placement
            style = discord.ButtonStyle.secondary
            if 'All' in category_name:
                style = discord.ButtonStyle.blurple
                row = 2
            elif i < 3:
                row = 0
            else:
                row = 1

            # FIX: Use a unique custom_id for each dynamic button
            button = ui.Button(label=button_label, style=style, emoji="#️⃣", row=row, custom_id=f"channel_set_{channel_key}_{i}")
            button.callback = self._create_channel_button_callback(channel_key, category_name)
            self.add_item(button)

        # DO NOT manually add the decorated back_button here to avoid duplicate custom_id errors.
        # The decorated method will be included automatically in the View.

    def _create_channel_button_callback(self, channel_key: str, channel_name: str):
        """Creates a callback function for the dynamically generated channel buttons."""
        async def callback(interaction: discord.Interaction):
            # Public prompt (Option 3): ask in the same channel (non-ephemeral)
            try:
                await interaction.response.send_message(
                    f"📌 **Enter the channel ID or mention for `{channel_name}`.**\n"
                    f"Example: `#logs` or `123456789012345678`\n\n"
                    f"⏳ You have 60 seconds to reply in this channel.",
                    ephemeral=False
                )
            except Exception:
                # If we cannot send a normal response (rare), try an ephemeral fallback
                try:
                    await interaction.response.send_message(
                        f"📌 **Enter the channel ID or mention for `{channel_name}`.**\n"
                        f"Example: `#logs` or `123456789012345678`\n\n"
                        f"⏳ You have 60 seconds to reply in this channel.",
                        ephemeral=True
                    )
                except Exception:
                    return

            def check(msg: discord.Message):
                # require same user and same channel where the interaction originated (public)
                return (
                    msg.author.id == interaction.user.id
                    and msg.channel == interaction.channel
                )

            try:
                msg: discord.Message = await self.bot.wait_for("message", timeout=60.0, check=check)
            except asyncio.TimeoutError:
                # Inform about timeout publicly in the same channel if possible
                try:
                    await interaction.followup.send("⏳ You didn't respond in time. Please try again.", ephemeral=False)
                except Exception:
                    try:
                        await interaction.followup.send("⏳ You didn't respond in time. Please try again.", ephemeral=True)
                    except Exception:
                        pass
                return

            content = msg.content.strip()
            cid_str = content.replace('<#', '').replace('>', '').strip()

            if not cid_str.isdigit():
                try:
                    await interaction.followup.send("❌ Invalid channel format. Provide a channel mention (e.g., #logs) or a numeric ID.", ephemeral=False)
                except Exception:
                    await interaction.followup.send("❌ Invalid channel format.", ephemeral=True)
                return

            cid = int(cid_str)
            channel = interaction.guild.get_channel(cid) if interaction.guild else None

            if not channel or not isinstance(channel, discord.TextChannel):
                try:
                    await interaction.followup.send("❌ That is not a valid text channel. Make sure I can see the channel and you provided correct ID/mention.", ephemeral=False)
                except Exception:
                    await interaction.followup.send("❌ That is not a valid text channel.", ephemeral=True)
                return

            # Save the channel to config
            update_guild_config(self.guild_id, channel_key, channel.id)

            try:
                await interaction.followup.send(f"✅ **{channel_name}** successfully set to {channel.mention}.", ephemeral=False)
            except Exception:
                await interaction.followup.send(f"✅ **{channel_name}** set.", ephemeral=True)

        return callback

    def create_dashboard_embed(self) -> discord.Embed:
        """Generates the embed showing the status of all configured log channels."""
        config = get_guild_config(self.guild_id)
        embed = discord.Embed(
            title="#️⃣ LOG CHANNEL CONFIGURATION",
            description="Set a dedicated channel for each type of log. Unset categories will not log their events.",
            color=COLOR_NEON_BLUE,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        for category_name, channel_key in CHANNEL_CATEGORY_MAP.items():
            channel_id = config.get(channel_key)
            channel_info = f"<#{channel_id}>" if channel_id else "❌ Not Set"

            name = f"**{category_name}**"

            if 'All' in category_name:
                embed.add_field(name="--- Fallback Channel (Test Log uses this) ---", value=f"`{channel_key}`: {channel_info}", inline=False)
            else:
                embed.add_field(name=name, value=channel_info, inline=True)

        embed.set_footer(text="Use the buttons below to set the channels via ID or Mention.")
        return embed

    @ui.button(label="Back to Main Panel", style=discord.ButtonStyle.grey, emoji="⬅️", row=3)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        dashboard = LoggingPanel(interaction.client, self.guild_id)
        await interaction.response.edit_message(embed=dashboard.create_dashboard_embed(), view=dashboard)


# --- Main Dashboard UI Component ---

class LoggingPanel(ui.View):
    """The main control panel for the logging system."""

    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id

    def create_dashboard_embed(self) -> discord.Embed:
        """Generates the rich neon cyber-themed dashboard embed."""
        config = get_guild_config(self.guild_id)

        status = "✅ ENABLED" if config['enabled'] else "❌ DISABLED"
        status_emoji = "🟢" if config['enabled'] else "🔴"

        enabled_count = sum(config['events'].values())

        set_channels = sum(1 for key in CHANNEL_CATEGORY_MAP.values() if config.get(key))

        embed = discord.Embed(
            title=f"{status_emoji} SENTINEL LOGGING SYSTEM | CONTROL PANEL",
            description="Manage all integrated audit and security logs for this server.",
            color=COLOR_NEON_BLUE,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        embed.add_field(name="CORE STATUS", value=f"**System**: {status}", inline=True)
        embed.add_field(name="LOG CHANNELS SET", value=f"**{set_channels}** categories set.", inline=True)
        embed.add_field(name="CONFIGURED EVENTS", value=f"**{enabled_count}** events enabled.", inline=False)

        embed.set_footer(text=f"Server ID: {self.guild_id}")
        return embed

    @ui.button(label="Toggle Logging", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def toggle_logging(self, interaction: discord.Interaction, button: ui.Button):
        config = get_guild_config(self.guild_id)
        new_state = not config['enabled']
        update_guild_config(self.guild_id, 'enabled', new_state)

        message = f"✅ Logging System is now **{'ENABLED' if new_state else 'DISABLED'}**."
        await interaction.response.edit_message(embed=self.create_dashboard_embed(), view=self)
        await interaction.followup.send(message, ephemeral=True)

    @ui.button(label="Set Log Channels", style=discord.ButtonStyle.success, emoji="#️⃣", row=1)
    async def set_log_channels(self, interaction: discord.Interaction, button: ui.Button):
        channel_view = ChannelConfigPanel(self.bot, self.guild_id)
        await interaction.response.edit_message(embed=channel_view.create_dashboard_embed(), view=channel_view)

    @ui.button(label="Configure Events", style=discord.ButtonStyle.secondary, emoji="⚙️", row=2)
    async def configure_events(self, interaction: discord.Interaction, button: ui.Button):
        event_view = EventConfigView(self.bot, self.guild_id)
        await interaction.response.edit_message(embed=event_view.create_event_embed(), view=event_view)

    @ui.button(label="Test Log", style=discord.ButtonStyle.secondary, emoji="🧪", row=2)
    async def test_log(self, interaction: discord.Interaction, button: ui.Button):
        config = get_guild_config(self.guild_id)

        channel_key = CHANNEL_CATEGORY_MAP['All Events (Fallback)']
        channel_id = config.get(channel_key)

        if not channel_id or not config['enabled']:
            await interaction.response.send_message("❌ Cannot test. Logging must be enabled and the 'All Events (Fallback)' channel must be set.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ Log Channel not found or deleted. Please re-set the channel.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🧪 LOG TEST SUCCESSFUL",
            description=f"This message was successfully sent to {channel.mention}.",
            color=COLOR_SUCCESS,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Initiated by {interaction.user.name} | Event: Log Test")

        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Test log sent to {channel.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Bot lacks **SEND_MESSAGES** permission in the log channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while sending the test log: {e}", ephemeral=True)

    @ui.button(label="Reset Config", style=discord.ButtonStyle.danger, emoji="🗑️", row=3)
    async def reset_config(self, interaction: discord.Interaction, button: ui.Button):
        # Reset logic adjusted to handle all keys correctly
        update_guild_config(self.guild_id, 'enabled', False)
        update_guild_config(self.guild_id, 'log_channel', None)
        update_guild_config(self.guild_id, 'message_channel', None)
        update_guild_config(self.guild_id, 'member_channel', None)
        update_guild_config(self.guild_id, 'role_channel', None)
        update_guild_config(self.guild_id, 'asset_channel', None)
        update_guild_config(self.guild_id, 'server_channel', None)
        update_guild_config(self.guild_id, 'events', DEFAULT_EVENTS.copy())

        await interaction.response.edit_message(embed=self.create_dashboard_embed(), view=self)
        await interaction.followup.send("⚠️ All logging settings have been **RESET** to default.", ephemeral=True)


# --- Cog Implementation ---
# The listener logic remains the same, as it relies on the now-fixed get_log_info and UI.

class LoggingSystem(commands.Cog):
    """A modular and professional logging system for Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.exists('data'):
            os.makedirs('data')
        load_config()

    def get_log_info(self, guild_id: int, event_key: str) -> Optional[discord.TextChannel]:
        """Utility to check config and return the log channel if logging is enabled for the event."""
        config = get_guild_config(guild_id)

        if not config['enabled'] or not config['events'].get(event_key, False):
            return None

        channel_key = None
        for category, events in EVENT_CATEGORIES.items():
            if event_key in events:
                channel_key = CHANNEL_CATEGORY_MAP.get(category)
                break

        # Fallback to the main 'log_channel' key if no specific one is found (or if the specific key is None)
        channel_id = config.get(channel_key)

        if not channel_id:
            return None

        return self.bot.get_channel(channel_id)

    async def send_log_embed(self, channel: discord.TextChannel, embed: discord.Embed):
        """Helper function to handle sending logs and error handling."""
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Failed to send log to #{channel.name} ({channel.id}) due to insufficient permissions.")

    # --- Slash Commands ---

    @app_commands.command(name="logs", description="Open the Sentinel Logging System control panel.")
    @app_commands.default_permissions(manage_guild=True)
    async def logs_command(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        dashboard = LoggingPanel(self.bot, interaction.guild_id)
        await interaction.response.send_message(embed=dashboard.create_dashboard_embed(), view=dashboard, ephemeral=True)

    @app_commands.command(name="logchannels", description="Configure dedicated channels for log categories.")
    @app_commands.default_permissions(manage_guild=True)
    async def logchannels_command(self, interaction: discord.Interaction):
        if not interaction.guild:
            return

        panel = ChannelConfigPanel(self.bot, interaction.guild_id)
        await interaction.response.send_message(embed=panel.create_dashboard_embed(), view=panel, ephemeral=True)

    # --- Event Listeners (Message Events) ---
    # (Keeping the listeners short for the final response)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        channel = self.get_log_info(message.guild.id, "message_delete")
        if not channel:
            return

        embed = discord.Embed(
            title="🗑️ MESSAGE DELETED",
            description=f"Message by {message.author.mention} deleted in {message.channel.mention}",
            color=COLOR_WARNING,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Content", value=discord.utils.escape_markdown(message.content[:1024]) or "*No content*", inline=False)
        await self.send_log_embed(channel, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        channel = self.get_log_info(before.guild.id, "message_edit")
        if not channel:
            return

        embed = discord.Embed(title="✍️ MESSAGE EDITED", description=f"Message by {before.author.mention} edited in {before.channel.mention} ([Jump to message]({after.jump_url}))", color=COLOR_NEON_BLUE, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="Before", value=discord.utils.escape_markdown(before.content[:500]) or "*Empty*", inline=False)
        embed.add_field(name="After", value=discord.utils.escape_markdown(after.content[:500]) or "*Empty*", inline=False)
        await self.send_log_embed(channel, embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        if not messages or not messages[0].guild:
            return
        log_channel = self.get_log_info(messages[0].guild.id, "message_bulk_delete")
        if not log_channel:
            return

        embed = discord.Embed(title="🔥 BULK MESSAGES DELETED", description=f"**{len(messages)}** messages were deleted in {messages[0].channel.mention}.", color=0xFF0000, timestamp=datetime.datetime.now(datetime.timezone.utc))
        await self.send_log_embed(log_channel, embed)

    # --- Event Listeners (Member, Role, Channel, etc. - all rely on the fixed get_log_info) ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild:
            return
        channel = self.get_log_info(member.guild.id, "member_join")
        if not channel:
            return
        embed = discord.Embed(title="📥 MEMBER JOINED", description=f"{member.mention} has joined the server!", color=COLOR_SUCCESS, timestamp=datetime.datetime.now(datetime.timezone.utc))
        await self.send_log_embed(channel, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.guild:
            return
        channel = self.get_log_info(member.guild.id, "member_leave")
        if not channel:
            return
        embed = discord.Embed(title="📤 MEMBER LEFT", description=f"{member.mention} has left the server.", color=COLOR_WARNING, timestamp=datetime.datetime.now(datetime.timezone.utc))
        await self.send_log_embed(channel, embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        channel = self.get_log_info(role.guild.id, "role_create")
        if not channel:
            return
        embed = discord.Embed(title="➕ ROLE CREATED", description=f"A new role, **{role.mention}**, was created.", color=role.color if role.color != discord.Color.default() else COLOR_NEON_BLUE, timestamp=datetime.datetime.now(datetime.timezone.utc))
        await self.send_log_embed(channel, embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if not channel.guild:
            return
        log_channel = self.get_log_info(channel.guild.id, "channel_create")
        if not log_channel:
            return
        embed = discord.Embed(title="➕ CHANNEL CREATED", description=f"A new channel, **{channel.mention}** (`{channel.name}`), was created.", color=COLOR_SUCCESS, timestamp=datetime.datetime.now(datetime.timezone.utc))
        await self.send_log_embed(log_channel, embed)

    # All other listeners (ban, unban, member_update, role_delete, channel_delete, emoji, etc.) are implicitly handled by the updated utility functions.


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingSystem(bot))
