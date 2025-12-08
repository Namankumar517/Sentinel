# cogs/security.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os
from typing import List, Dict, Any

# --- Configuration File Path ---
CONFIG_FILE = 'data/security.json'

# --- Utility Functions (Unchanged) ---
def load_config() -> Dict[str, Any]:
    """Loads the security configuration from JSON file."""
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
    """Saves the security configuration to JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
def get_guild_config(guild_id: int) -> Dict[str, Any]:
    """Retrieves or initializes the config for a specific guild."""
    config = load_config()
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = {
            "antinuke": False,
            "antiraid": False,
            "antispam": False,
            "antiwebhook": False,
            "punish": "timeout",
            "whitelist": []
        }
        save_config(config)
    return config[guild_id_str]
def update_guild_config(guild_id: int, key: str, value: Any):
    """Updates a specific key in the guild's configuration."""
    config = load_config()
    guild_id_str = str(guild_id)
    if guild_id_str not in config:
        get_guild_config(guild_id)
        config = load_config()
    
    config[guild_id_str][key] = value
    save_config(config)

# --- Premium Embed Utilities ---
COLOR_NEON_PURPLE = 0x8A2BE2 # Purple/blue neon theme
COLOR_WARNING = 0xFF4500     # Orange/Red for alerts
COLOR_SUCCESS = 0x32CD32     # Lime green for success

def create_premium_embed(title: str, description: str, color: int = COLOR_NEON_PURPLE) -> discord.Embed:
    """Creates a stylized, premium embed."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    # Add a glowing divider effect to the footer
    embed.set_footer(text=":: SENTINEL PROTOCOL ONLINE ::")
    return embed

# --- UI Components ---

# 1. Main Dashboard View
class SecurityDashboard(ui.View):
    """The main dashboard view for the /antinuke command."""
    def __init__(self, bot: commands.Bot, guild_id: int, guild_owner_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.guild_owner_id = guild_owner_id
        
        # Add the Anti-Nuke Toggle Button directly to the dashboard (NEW)
        self.antinuke_toggle = AntiNukeToggle(guild_id, guild_owner_id)
        self.add_item(self.antinuke_toggle)

    def create_main_embed(self) -> discord.Embed:
        """Creates the enhanced cyberpunk-themed dashboard embed."""
        config = get_guild_config(self.guild_id)
        
        status = {
            "Anti-Nuke": "✅ ONLINE" if config['antinuke'] else "❌ OFFLINE",
            "Anti-Raid": "🛡️ Active" if config['antiraid'] else "💤 Idle",
            "Anti-Spam": "🚫 Blocking" if config['antispam'] else "⚠️ Monitoring",
            "Anti-Webhook": "🕸️ Secured" if config['antiwebhook'] else "🔓 Vulnerable",
        }
        
        embed = create_premium_embed(
            title="✨ SENTINEL SECURITY SYSTEM | CYBER-SEC CONSOLE",
            description="Welcome to the **Premium Dashboard**. Review and adjust defense protocols.",
            color=COLOR_NEON_PURPLE
        )
        
        # Enhanced Protection Status Field
        protection_value = (
            f"**{status['Anti-Nuke']}** (Owner Locked)\n"
            f"`Anti-Raid:` {status['Anti-Raid']}\n"
            f"`Anti-Spam:` {status['Anti-Spam']}\n"
            f"`Anti-Webhook:` {status['Anti-Webhook']}\n"
        )
        embed.add_field(name="<:shield:1234567890> DEFENSE PROTOCOL STATUS", value=protection_value, inline=False)
        
        # Key Metrics Field
        embed.add_field(
            name="🔨 PUNISHMENT METRICS",
            value=(
                f"**Punishment:** `{config['punish'].upper()}`\n"
                f"**Whitelist:** `{len(config['whitelist'])}` Exempt Users"
            ),
            inline=True
        )
        
        # Cyberpunk visual divider
        embed.add_field(name="\u200b", value="--- **GLOWING DIVIDER** ---", inline=False)
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only users with manage_guild permission can interact with general settings."""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("🚨 ACCESS DENIED: You require **Manage Server** permissions for dashboard access.", ephemeral=True)
            return False
        return True
    
    # Existing buttons are now in a separate row (row=1, row=2)
    @ui.button(label="1. Protection Settings", style=discord.ButtonStyle.primary, emoji="🛡️", row=1)
    async def protection_settings_button(self, interaction: discord.Interaction, button: ui.Button):
        """Opens the protection settings panel."""
        await interaction.response.edit_message(
            embed=self.create_main_embed(), 
            view=ProtectionSettingsView(self.bot, self.guild_id, self.guild_owner_id)
        )

    @ui.button(label="2. Punishment Settings", style=discord.ButtonStyle.red, emoji="🔨", row=1)
    async def punishment_settings_button(self, interaction: discord.Interaction, button: ui.Button):
        """Opens the punishment settings panel."""
        await interaction.response.edit_message(
            embed=self.create_main_embed(), 
            view=PunishmentSettingsView(self.bot, self.guild_id)
        )

    @ui.button(label="3. Whitelist Manager", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def whitelist_manager_button(self, interaction: discord.Interaction, button: ui.Button):
        """Opens the whitelist manager panel."""
        await interaction.response.send_modal(WhitelistManagerModal(self.bot, self.guild_id))

# --- NEW: Anti-Nuke Toggle Button (Owner Only) ---
class AntiNukeToggle(ui.Button):
    def __init__(self, guild_id: int, guild_owner_id: int):
        self.guild_id = guild_id
        self.guild_owner_id = guild_owner_id
        config = get_guild_config(guild_id)
        initial_state = config.get('antinuke', False)
        
        label = f"ANTI-NUKE: {'🔴 OFF' if not initial_state else '🟢 ON'}"
        style = discord.ButtonStyle.danger if not initial_state else discord.ButtonStyle.success
        
        super().__init__(label=label, style=style, emoji="☢️", row=0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Restricts interaction to the guild owner."""
        if interaction.user.id != self.guild_owner_id:
            await interaction.response.send_message("👑 ACCESS DENIED: Only the **Guild Owner** can toggle the Anti-Nuke system.", ephemeral=True)
            return False
        return True

    async def callback(self, interaction: discord.Interaction):
        config = get_guild_config(self.guild_id)
        new_state = not config.get('antinuke', False)
        update_guild_config(self.guild_id, 'antinuke', new_state)
        
        # Update button visual
        self.label = f"ANTI-NUKE: {'🔴 OFF' if not new_state else '🟢 ON'}"
        self.style = discord.ButtonStyle.danger if not new_state else discord.ButtonStyle.success
        
        # Edit the parent view and send premium confirmation message
        await interaction.response.edit_message(view=self.view)
        
        status_msg = "**ACTIVATED**" if new_state else "**DEACTIVATED**"
        
        log_embed = create_premium_embed(
            title=f"🚨 ANTI-NUKE PROTOCOL {status_msg}",
            description=f"Sentinel Anti-Nuke has been **{status_msg}** by **{interaction.user.mention}**.",
            color=COLOR_SUCCESS if new_state else COLOR_WARNING
        )
        await interaction.followup.send(embed=log_embed, ephemeral=True)

# 2. Protection Settings View (Anti-Nuke removed here)
class ProtectionSettingsView(ui.View):
    """View to toggle specific security features, excluding the owner-locked Anti-Nuke."""
    def __init__(self, bot: commands.Bot, guild_id: int, guild_owner_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        self.guild_owner_id = guild_owner_id
        
        config = get_guild_config(guild_id)
        
        # Add toggles (Anti-Nuke is now on the dashboard)
        self.add_item(ProtectionToggle(
            'Anti-Raid', 
            'antiraid', 
            config['antiraid'], 
            "raid_toggle"
        ))
        self.add_item(ProtectionToggle(
            'Anti-Spam', 
            'antispam', 
            config['antispam'], 
            "spam_toggle"
        ))
        self.add_item(ProtectionToggle(
            'Anti-Webhook', 
            'antiwebhook', 
            config['antiwebhook'], 
            "webhook_toggle"
        ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only users with manage_guild permission can interact."""
        # Non-owner staff can manage non-Nuke settings
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("🚨 Access Denied! You require **Manage Server** permissions.", ephemeral=True)
            return False
        return True

    @ui.button(label="⬅️ Back to Dashboard", style=discord.ButtonStyle.grey, row=4)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        """Returns to the main dashboard."""
        # Pass owner ID back to the dashboard constructor
        dashboard = SecurityDashboard(self.bot, self.guild_id, self.guild_owner_id)
        await interaction.response.edit_message(embed=dashboard.create_main_embed(), view=dashboard)

class ProtectionToggle(ui.Button):
    """A button to toggle a specific protection feature."""
    def __init__(self, label: str, config_key: str, initial_state: bool, custom_id: str):
        self.config_key = config_key
        self.current_state = initial_state
        self.base_label = label
        
        label_text = f"Toggle {label}: {'✅' if initial_state else '❌'}"
        style = discord.ButtonStyle.success if initial_state else discord.ButtonStyle.danger

        super().__init__(label=label_text, style=style, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        # Toggle state
        self.current_state = not self.current_state
        update_guild_config(interaction.guild_id, self.config_key, self.current_state)
        
        # Update button appearance
        self.label = f"Toggle {self.base_label}: {'✅' if self.current_state else '❌'}"
        self.style = discord.ButtonStyle.success if self.current_state else discord.ButtonStyle.danger
        
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"**{self.base_label}** is now **{'ENABLED' if self.current_state else 'DISABLED'}**.", ephemeral=True)

# 3. Punishment Settings View (Unchanged)
class PunishmentSettingsView(ui.View):
    # ... (Unchanged from previous code) ...
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        config = get_guild_config(guild_id)
        self.add_item(PunishmentSelect(config['punish']))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("🚨 Access Denied!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="⬅️ Back to Dashboard", style=discord.ButtonStyle.grey, row=2)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        dashboard = SecurityDashboard(self.bot, self.guild_id, interaction.guild.owner_id) # Needs owner_id
        await interaction.response.edit_message(embed=dashboard.create_main_embed(), view=dashboard)

class PunishmentSelect(ui.Select):
    # ... (Unchanged from previous code) ...
    def __init__(self, current_punishment: str):
        options = [
            discord.SelectOption(label="Ban", value="ban", description="Permanently bans the attacker from the server."),
            discord.SelectOption(label="Kick", value="kick", description="Kicks the attacker from the server."),
            discord.SelectOption(label="Timeout (60m)", value="timeout", description="Times out the attacker for 60 minutes."),
            discord.SelectOption(label="Remove Roles", value="remove_roles", description="Removes all non-essential roles from the attacker."),
        ]
        for option in options:
            if option.value == current_punishment:
                option.default = True
        super().__init__(placeholder="Select the Auto-Punishment Action...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected_punish = self.values[0]
        update_guild_config(interaction.guild_id, 'punish', selected_punish)
        
        new_options = []
        for option in self.options:
            option.default = (option.value == selected_punish)
            new_options.append(option)
        self.options = new_options
        
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"🔨 Auto-Punishment set to **{selected_punish.upper()}**.", ephemeral=True)


# 4. Whitelist Manager Modal (Unchanged from the FIX)
class WhitelistManagerModal(ui.Modal, title='Whitelist Manager'):
    # ... (Unchanged from the fixed code in the previous response) ...
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        
        self.action_input = ui.TextInput(
            label="Action (Type: add, remove, or view)",
            placeholder="Type 'add', 'remove', or 'view' here.",
            required=True,
            min_length=3,
            max_length=6,
            custom_id="action_input_field"
        )
        self.user_input = ui.TextInput(
            label="User ID or Mention (Required for Add/Remove)",
            placeholder="e.g. 123456789012345678 or @User",
            required=False,
            custom_id="user_input_field"
        )
        self.add_item(self.action_input)
        self.add_item(self.user_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        config = get_guild_config(self.guild_id)
        whitelist = config['whitelist']
        
        action = self.action_input.value.lower().strip() 
        user_input_value = self.user_input.value.strip()

        if action not in ["add", "remove", "view"]:
            await interaction.response.send_message("❌ Invalid action. Please type **'add'**, **'remove'**, or **'view'**.", ephemeral=True)
            return

        if action == "view":
            if not whitelist:
                await interaction.response.send_message("📜 The Whitelist is empty.", ephemeral=True)
                return
            
            user_mentions = [f"<@{user_id}>" for user_id in whitelist]
            view_embed = create_premium_embed(
                title="📜 Current Whitelisted Users",
                description="\n".join(user_mentions),
                color=COLOR_NEON_PURPLE
            )
            await interaction.response.send_message(embed=view_embed, ephemeral=True)
            return
            
        if not user_input_value:
            await interaction.response.send_message(f"❌ User ID or Mention is required for the **'{action}'** action.", ephemeral=True)
            return
            
        user_id_str = user_input_value.strip('<@!>')
        try:
            user_id = int(user_id_str)
        except ValueError:
            await interaction.response.send_message("❌ Invalid User ID or Mention format. Please use a valid ID or mention.", ephemeral=True)
            return

        if action == "add":
            if user_id in whitelist:
                msg = f"❌ User <@{user_id}> is already on the whitelist."
            else:
                whitelist.append(user_id)
                update_guild_config(self.guild_id, 'whitelist', whitelist)
                msg = f"✅ User <@{user_id}> has been **added** to the whitelist."
        
        elif action == "remove":
            if user_id in whitelist:
                whitelist.remove(user_id)
                update_guild_config(self.guild_id, 'whitelist', whitelist)
                msg = f"✅ User <@{user_id}> has been **removed** from the whitelist."
            else:
                msg = f"❌ User <@{user_id}> is not on the whitelist."

        await interaction.response.send_message(msg, ephemeral=True)


# --- Cog Implementation ---
class Security(commands.Cog):
    """A full cog for the Sentinel Security System."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.exists('data'):
            os.makedirs('data')
        load_config()

    # --- Commands (Prefix & Slash) ---

    @commands.command(name="antinuke", help="Sentinel Security System Configuration Dashboard.")
    @commands.has_permissions(manage_guild=True)
    async def antinuke_prefix(self, ctx: commands.Context):
        """Displays the main security dashboard (Prefix Version)."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        # Pass the guild owner ID to the view
        guild_owner_id = ctx.guild.owner_id
        dashboard = SecurityDashboard(self.bot, ctx.guild.id, guild_owner_id)
        embed = dashboard.create_main_embed()
        
        await ctx.send(embed=embed, view=dashboard)

    @app_commands.command(name="antinuke", description="Sentinel Security System Configuration Dashboard.")
    @app_commands.default_permissions(manage_guild=True)
    async def antinuke_slash(self, interaction: discord.Interaction):
        """Displays the main security dashboard (Slash Version)."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        # Pass the guild owner ID to the view
        guild_owner_id = interaction.guild.owner_id
        dashboard = SecurityDashboard(self.bot, interaction.guild_id, guild_owner_id)
        embed = dashboard.create_main_embed()
        
        await interaction.response.send_message(embed=embed, view=dashboard, ephemeral=True)
        
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        DEFENSIVE LOGIC PLACEHOLDER: 
        This is where complex detection logic for Anti-Nuke would go. 
        """
        guild_id = channel.guild.id
        config = get_guild_config(guild_id)
        
        if config.get('antinuke', False):
            # 🚨 INSECURE/COMPLEX LOGIC OMITTED (Placeholder): 
            # 1. Audit logs to find the attacker.
            # 2. Check if the attacker is whitelisted.
            # 3. Rate-limit checks (channel delete spam).
            # 4. Execute punishment (ban/kick/timeout) and logging.
            pass
            
# --- Setup Function ---
async def setup(bot: commands.Bot):
    """Adds the Security cog to the bot."""
    await bot.add_cog(Security(bot))
