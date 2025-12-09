# cogs/generator.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import aiofiles
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Literal, List, Union, cast, Dict, Any
import time

# --- Configuration and File Setup (Multi-Server) ---

DATA_DIR = "data"
GLOBAL_CONFIG_FILE = os.path.join(DATA_DIR, "global_gen_config.json")
GLOBAL_SERVICES_FILE = os.path.join(DATA_DIR, "global_services.json")
GLOBAL_STATS_FILE = os.path.join(DATA_DIR, "global_stats.json")
GLOBAL_BLACKLIST_FILE = os.path.join(DATA_DIR, "global_blacklist.json")
GLOBAL_COOLDOWNS_FILE = os.path.join(DATA_DIR, "global_cooldowns.json")
STOCK_BASE_FOLDER = os.path.join(DATA_DIR, "Stock")

os.makedirs(STOCK_BASE_FOLDER, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_GUILD_CONFIG = {
    "free_role_id": None,
    "premium_role_id": None,
    "booster_role_id": None,
    "free_channel_id": None,
    "premium_channel_id": None,
    "booster_channel_id": None,
    "log_channel_id": None,
    "vouch_channel_id": None,
    "max_amount": 1000
}

DEFAULT_GLOBAL_CONFIG = {
    "free_cooldown_seconds": 60,
    "premium_cooldown_seconds": 30,
    "booster_cooldown_seconds": 15,
    "restock_logging_enabled": True
}

# --- Helper Functions (File Management) ---

async def load_json(filepath: str, default_data: Any) -> Any:
    if not os.path.exists(filepath):
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(default_data, indent=4))
        return default_data
    
    try:
        async with aiofiles.open(filepath, 'r') as f:
            content = await f.read()
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_data

async def save_json(filepath: str, data: Any):
    async with aiofiles.open(filepath, 'w') as f:
        await f.write(json.dumps(data, indent=4))

async def load_guild_config(guild_id: int) -> Dict[str, Any]:
    global_config = await load_json(GLOBAL_CONFIG_FILE, {})
    guild_id_str = str(guild_id)
    if guild_id_str not in global_config:
        global_config[guild_id_str] = DEFAULT_GUILD_CONFIG.copy()
        await save_json(GLOBAL_CONFIG_FILE, global_config)
    return global_config[guild_id_str]

async def update_guild_config(guild_id: int, key: str, value: Any):
    global_config = await load_json(GLOBAL_CONFIG_FILE, {})
    guild_id_str = str(guild_id)
    if guild_id_str not in global_config:
        global_config[guild_id_str] = DEFAULT_GUILD_CONFIG.copy()
    
    global_config[guild_id_str][key] = value
    await save_json(GLOBAL_CONFIG_FILE, global_config)

async def load_global_config() -> Dict[str, Any]:
    return await load_json(GLOBAL_SERVICES_FILE, DEFAULT_GLOBAL_CONFIG.copy())

async def update_global_config(key: str, value: Any):
    config = await load_json(GLOBAL_SERVICES_FILE, DEFAULT_GLOBAL_CONFIG.copy())
    config[key] = value
    await save_json(GLOBAL_SERVICES_FILE, config)
    
async def load_blacklist() -> List[int]:
    return await load_json(GLOBAL_BLACKLIST_FILE, [])

async def update_blacklist(blacklist: List[int]):
    await save_json(GLOBAL_BLACKLIST_FILE, blacklist)

async def load_cooldowns() -> Dict[str, Any]:
    cooldowns = await load_json(GLOBAL_COOLDOWNS_FILE, {})
    # Cleanup expired cooldowns on load
    current_time = time.time()
    valid_cooldowns = {}
    for user_id, data in cooldowns.items():
        new_data = {
            service: expiry for service, expiry in data.items() if expiry > current_time
        }
        if new_data:
            valid_cooldowns[user_id] = new_data
    await save_json(GLOBAL_COOLDOWNS_FILE, valid_cooldowns)
    return valid_cooldowns

async def update_cooldown(user_id: int, service: str, expiry_time: float):
    cooldowns = await load_cooldowns()
    user_id_str = str(user_id)
    if user_id_str not in cooldowns:
        cooldowns[user_id_str] = {}
    cooldowns[user_id_str][service] = expiry_time
    await save_json(GLOBAL_COOLDOWNS_FILE, cooldowns)


# --- Cog Implementation ---
class Generator(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.services: Dict[str, Any] = {}
        self.blacklist: List[int] = []
        self.cooldowns: Dict[str, Any] = {}
        self.bg_task = self.load_data_task.start()

    def cog_unload(self):
        self.bg_task.cancel()

    @tasks.loop(minutes=5)
    async def load_data_task(self):
        """Background task to periodically load and refresh all generator data."""
        self.services = await load_json(GLOBAL_SERVICES_FILE, {})
        self.blacklist = await load_blacklist()
        self.cooldowns = await load_cooldowns()
        self.global_config = await load_global_config()

    # --- Autocomplete for Service Names ---
    async def service_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for service_name in self.services.keys():
            if current.lower() in service_name.lower():
                choices.append(app_commands.Choice(name=service_name, value=service_name))
        return choices[:25]

    # --- Core Generation Logic (Helper) ---
    async def _handle_generation(self, source, service_name: str, tier: Literal['free', 'premium', 'booster']):
        # Determine source type for response handling
        ctx: Optional[commands.Context] = None
        interaction: Optional[discord.Interaction] = None
        if isinstance(source, commands.Context):
            ctx = source
            user = ctx.author
            guild = ctx.guild
            # Prefix commands don't support app_commands.Range, so we check limits here for consistency
            if service_name not in self.services:
                return await ctx.reply(f"❌ Service `{service_name}` not found.")
        else: # discord.Interaction
            interaction = source
            user = interaction.user
            guild = interaction.guild
            # Defer response early for slash commands
            await interaction.response.defer(ephemeral=True)
            if service_name not in self.services:
                return await interaction.followup.send(f"❌ Service `{service_name}` not found.", ephemeral=True)
        
        # --- Pre-Checks ---
        if user.id in self.blacklist:
            embed = discord.Embed(
                title="❌ Access Denied", 
                description="You are currently blacklisted from using the generator.", 
                color=discord.Color.red()
            )
            if ctx: await ctx.reply(embed=embed)
            else: await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild_config = await load_guild_config(guild.id)
        
        # Check Channel
        channel_id = guild_config.get(f'{tier}_channel_id')
        if channel_id and source.channel.id != channel_id:
            channel_mention = f"<#{channel_id}>"
            embed = discord.Embed(
                title="⚠️ Wrong Channel", 
                description=f"You can only use the **{tier.title()}** generator in {channel_mention}.", 
                color=discord.Color.gold()
            )
            if ctx: await ctx.reply(embed=embed)
            else: await interaction.followup.send(embed=embed, ephemeral=True)
            return
            
        # Check Role
        role_id = guild_config.get(f'{tier}_role_id')
        if role_id and not discord.utils.get(user.roles, id=role_id):
            role_mention = f"<@&{role_id}>"
            embed = discord.Embed(
                title="🔒 Role Required", 
                description=f"You need the {role_mention} role to use the **{tier.title()}** generator.", 
                color=discord.Color.red()
            )
            if ctx: await ctx.reply(embed=embed)
            else: await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Check Cooldown
        cooldown_key = str(user.id)
        service_key = service_name
        cooldown_seconds = self.global_config.get(f'{tier}_cooldown_seconds', 60 if tier == 'free' else 30)
        
        user_cooldowns = self.cooldowns.get(cooldown_key, {})
        last_use = user_cooldowns.get(service_key, 0)
        
        time_left = last_use - time.time()
        
        if time_left > 0:
            minutes, seconds = divmod(time_left, 60)
            embed = discord.Embed(
                title="⏳ Cooldown Active", 
                description=f"You must wait **{int(minutes)}m {int(seconds)}s** before generating `{service_name}` again.", 
                color=discord.Color.orange()
            )
            if ctx: await ctx.reply(embed=embed)
            else: await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # --- Generation Logic ---
        
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        try:
            async with aiofiles.open(stock_file_path, mode='r') as f:
                lines = await f.readlines()
            
            lines = [line.strip() for line in lines if line.strip()]

            if not lines:
                embed = discord.Embed(
                    title="⚠️ Out of Stock", 
                    description=f"The `{service_name}` service is currently out of stock.", 
                    color=discord.Color.dark_red()
                )
                if ctx: await ctx.reply(embed=embed)
                else: await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Get one account and remove it
            account = lines.pop(0)

            async with aiofiles.open(stock_file_path, mode='w') as f:
                await f.write('\n'.join(lines) + '\n')
                
            # Update stats
            stats = await load_json(GLOBAL_STATS_FILE, {})
            stats[service_name] = stats.get(service_name, 0) + 1
            await save_json(GLOBAL_STATS_FILE, stats)

            # Set Cooldown
            await update_cooldown(user.id, service_name, time.time() + cooldown_seconds)
            self.cooldowns = await load_cooldowns() # Refresh local copy

            # --- Success Response ---
            success_embed = discord.Embed(
                title="✅ Account Generated", 
                description=f"You generated a `{service_name}` account. Check your DMs!", 
                color=discord.Color.green()
            )
            
            dm_embed = discord.Embed(
                title=f"🔒 Your Generated {service_name} Account",
                description=f"**Service:** `{service_name}`\n**Account:** ```{account}```",
                color=discord.Color.blue(),
                timestamp=datetime.now(tz=datetime.timezone.utc)
            )
            dm_embed.set_footer(text=f"Generated by {guild.name} | Cooldown: {cooldown_seconds}s")
            
            try:
                await user.send(embed=dm_embed)
                if ctx: await ctx.reply(embed=success_embed, ephemeral=True)
                else: await interaction.followup.send(embed=success_embed, ephemeral=True)
            except discord.Forbidden:
                fail_embed = discord.Embed(
                    title="❌ Generation Failed",
                    description="Could not send you the account. Please enable your DMs for this server.",
                    color=discord.Color.red()
                )
                if ctx: await ctx.reply(embed=fail_embed)
                else: await interaction.followup.send(embed=fail_embed, ephemeral=True)
            
        except FileNotFoundError:
            embed = discord.Embed(
                title="❌ Service Error", 
                description=f"The stock file for `{service_name}` is missing on the server. Please inform an admin.", 
                color=discord.Color.red()
            )
            if ctx: await ctx.reply(embed=embed)
            else: await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Generator Error: {e}")
            error_embed = discord.Embed(
                title="❌ Internal Error", 
                description=f"An unexpected error occurred during generation: `{e}`", 
                color=discord.Color.red()
            )
            if ctx: await ctx.reply(embed=error_embed)
            else: await interaction.followup.send(embed=error_embed, ephemeral=True)

    # =========================================================================
# GENERATOR CORE COMMANDS (FREE, PREMIUM, BOOSTER)
# =========================================================================

# --- FREE GENERATOR ---
@commands.command(name="fgen", description="Generate a free account from a service")
@commands.cooldown(1, 5, commands.BucketType.user)
async def freegen_prefix(self, ctx: commands.Context, service_name: str):
    await self._handle_generation(ctx, service_name, 'free')
        
@app_commands.command(name="fgen", description="Generate a free account from a service")
@app_commands.autocomplete(service_name=service_autocomplete)
async def freegen_slash(self, interaction, service_name: str):
    await self._handle_generation(interaction, service_name, 'free')

# --- PREMIUM GENERATOR ---
@commands.command(name="pgen", description="Generate a premium account from a service")
@commands.cooldown(1, 5, commands.BucketType.user)
async def premiumgen_prefix(self, ctx: commands.Context, service_name: str):
    await self._handle_generation(ctx, service_name, 'premium')

@app_commands.command(name="pgen", description="Generate a premium account from a service")
@app_commands.autocomplete(service_name=service_autocomplete)
async def premiumgen_slash(self, interaction, service_name: str):
    await self._handle_generation(interaction, service_name, 'premium')

# --- BOOSTER GENERATOR ---
@commands.command(name="bgen", description="Generate a booster account from a service")
@commands.cooldown(1, 5, commands.BucketType.user)
async def boostergen_prefix(self, ctx: commands.Context, service_name: str):
    await self._handle_generation(ctx, service_name, 'booster')
        
@app_commands.command(name="bgen", description="Generate a booster account from a service")
@app_commands.autocomplete(service_name=service_autocomplete)
async def boostergen_slash(self, interaction, service_name: str):
    await self._handle_generation(interaction, service_name, 'booster')

    # =========================================================================
    # CONFIGURATION COMMANDS
    # =========================================================================
    
    # --- GUILD SETTINGS CONFIG ---
    @commands.command(name="gensettings", description="Set generator settings for this guild")
    @commands.has_permissions(administrator=True)
    async def gensettings_prefix(self, ctx: commands.Context, key: str, value: Union[discord.TextChannel, discord.Role, str, int, None]):
        key = key.lower()
        
        # Mapping values to config keys
        if 'channel' in key and isinstance(value, discord.TextChannel):
            config_value = value.id
        elif 'role' in key and isinstance(value, discord.Role):
            config_value = value.id
        elif key == 'max_amount' and isinstance(value, int):
            config_value = value
        else:
            if value is None or isinstance(value, str) and value.lower() in ('none', 'null', '0'):
                config_value = None
            else:
                config_value = str(value)

        # Basic key validation
        if key not in DEFAULT_GUILD_CONFIG:
            return await ctx.reply(f"❌ Invalid setting key. Available keys: `{', '.join(DEFAULT_GUILD_CONFIG.keys())}`")

        await update_guild_config(ctx.guild.id, key, config_value)
        
        # Display feedback
        display_value = f"<#{config_value}>" if 'channel' in key and config_value else \
                        f"<@&{config_value}>" if 'role' in key and config_value else \
                        str(config_value)
                        
        embed = discord.Embed(
            title="⚙️ Generator Settings Updated",
            description=f"Set `{key}` to `{display_value}` for this guild.",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed)

    @app_commands.command(name="gensettings", description="Set generator settings for this guild")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        key="The setting to change (e.g., free_role_id, max_amount)", 
        value="The value (role, channel, number, or 'none' to clear)"
    )
    async def gensettings_slash(self, interaction: discord.Interaction, key: str, value: str):
        key = key.lower()
        config_value: Optional[Union[int, str]] = None
        
        if key not in DEFAULT_GUILD_CONFIG:
             return await interaction.response.send_message(f"❌ Invalid setting key. Available keys: `{', '.join(DEFAULT_GUILD_CONFIG.keys())}`", ephemeral=True)

        if value.lower() in ('none', 'null', '0'):
            config_value = None
        elif 'channel' in key:
            try: config_value = int(value.strip('<#>'))
            except ValueError: return await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)
        elif 'role' in key:
            try: config_value = int(value.strip('<@&>'))
            except ValueError: return await interaction.response.send_message("❌ Invalid role ID.", ephemeral=True)
        elif key == 'max_amount':
            try: config_value = int(value)
            except ValueError: return await interaction.response.send_message("❌ Invalid number for max_amount.", ephemeral=True)
        else:
            config_value = value

        await update_guild_config(interaction.guild_id, key, config_value)
        
        # Display feedback
        display_value = f"<#{config_value}>" if 'channel' in key and config_value else \
                        f"<@&{config_value}>" if 'role' in key and config_value else \
                        str(config_value)
                        
        embed = discord.Embed(
            title="⚙️ Generator Settings Updated",
            description=f"Set `{key}` to `{display_value}` for this guild.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # =========================================================================
    # SERVICE/STOCK MANAGEMENT COMMANDS
    # =========================================================================
    
    # --- ADD SERVICE (Prefix) ---
    @commands.command(name="stockaddservice", description="Add a new service name to the generator")
    @commands.is_owner()
    async def stockaddservice_prefix(self, ctx: commands.Context, service_name: str):
        if service_name in self.services:
            return await ctx.reply(f"❌ Service `{service_name}` already exists.")
            
        self.services[service_name] = {"usage": 0}
        await save_json(GLOBAL_SERVICES_FILE, self.services)
        
        # Create the corresponding stock file
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        async with aiofiles.open(stock_file_path, mode='w') as f:
            await f.write('')

        await ctx.reply(f"✅ Service `{service_name}` has been added and stock file created.")

    # --- ADD SERVICE (Slash) ---
    @app_commands.command(name="stockaddservice", description="Add a new service name to the generator")
    @app_commands.is_owner()
    async def stockaddservice_slash(self, interaction: discord.Interaction, service_name: str):
        if service_name in self.services:
            return await interaction.response.send_message(f"❌ Service `{service_name}` already exists.", ephemeral=True)
            
        self.services[service_name] = {"usage": 0}
        await save_json(GLOBAL_SERVICES_FILE, self.services)
        
        # Create the corresponding stock file
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        async with aiofiles.open(stock_file_path, mode='w') as f:
            await f.write('')

        await interaction.response.send_message(f"✅ Service `{service_name}` has been added and stock file created.", ephemeral=True)


    # --- REMOVE SERVICE (Prefix) ---
    @commands.command(name="stockremoveservice", description="Remove a service name from the generator")
    @commands.is_owner()
    async def stockremoveservice_prefix(self, ctx: commands.Context, service_name: str):
        if service_name not in self.services:
            return await ctx.reply(f"❌ Service `{service_name}` does not exist.")
            
        del self.services[service_name]
        await save_json(GLOBAL_SERVICES_FILE, self.services)
        
        # Delete the corresponding stock file
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        if os.path.exists(stock_file_path):
            os.remove(stock_file_path)

        await ctx.reply(f"✅ Service `{service_name}` has been removed.")

    # --- REMOVE SERVICE (Slash) ---
    @app_commands.command(name="stockremoveservice", description="Remove a service name from the generator")
    @app_commands.autocomplete(service_name=service_autocomplete)
    @app_commands.is_owner()
    async def stockremoveservice_slash(self, interaction: discord.Interaction, service_name: str):
        if service_name not in self.services:
            return await interaction.response.send_message(f"❌ Service `{service_name}` does not exist.", ephemeral=True)
            
        del self.services[service_name]
        await save_json(GLOBAL_SERVICES_FILE, self.services)
        
        # Delete the corresponding stock file
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        if os.path.exists(stock_file_path):
            os.remove(stock_file_path)

        await interaction.response.send_message(f"✅ Service `{service_name}` has been removed.", ephemeral=True)


    # --- ADD/UPDATE STOCK (Prefix) ---
    @commands.command(name="stockupdate", description="Add new accounts to a service stock (one account per line)")
    @commands.is_owner()
    async def stockupdate_prefix(self, ctx: commands.Context, service_name: str, *, accounts: str):
        if service_name not in self.services:
            return await ctx.reply(f"❌ Service `{service_name}` does not exist.")
            
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        # Ensure only unique, non-empty lines are added
        new_lines = [line.strip() for line in accounts.split('\n') if line.strip()]
        
        try:
            async with aiofiles.open(stock_file_path, mode='a+') as f:
                # Read existing lines to prevent duplicates
                await f.seek(0)
                existing_lines = [line.strip() for line in (await f.readlines()) if line.strip()]
                
                lines_to_add = []
                for line in new_lines:
                    if line not in existing_lines:
                        lines_to_add.append(line)
                        
                # Append unique lines
                if lines_to_add:
                    await f.write('\n'.join(lines_to_add) + '\n')
                    await ctx.reply(f"✅ Added **{len(lines_to_add)}** unique accounts to `{service_name}` stock.")
                else:
                    await ctx.reply(f"⚠️ No unique accounts were added to `{service_name}` stock.")
                    
        except Exception as e:
            await ctx.reply(f"❌ An error occurred while updating stock: {e}")

    # --- ADD/UPDATE STOCK (Slash) ---
    @app_commands.command(name="stockupdate", description="Add new accounts to a service stock (one account per line)")
    @app_commands.autocomplete(service_name=service_autocomplete)
    @app_commands.is_owner()
    async def stockupdate_slash(self, interaction: discord.Interaction, service_name: str, accounts: str):
        await interaction.response.defer(ephemeral=True)

        if service_name not in self.services:
            return await interaction.followup.send(f"❌ Service `{service_name}` does not exist.", ephemeral=True)
            
        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        # Ensure only unique, non-empty lines are added
        new_lines = [line.strip() for line in accounts.split('\n') if line.strip()]
        
        try:
            async with aiofiles.open(stock_file_path, mode='a+') as f:
                # Read existing lines to prevent duplicates
                await f.seek(0)
                existing_lines = [line.strip() for line in (await f.readlines()) if line.strip()]
                
                lines_to_add = []
                for line in new_lines:
                    if line and line not in existing_lines:
                        lines_to_add.append(line)
                        
                # Append unique lines
                if lines_to_add:
                    await f.write('\n'.join(lines_to_add) + '\n')
                    await interaction.followup.send(f"✅ Added **{len(lines_to_add)}** unique accounts to `{service_name}` stock.", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ No unique accounts were added to `{service_name}` stock.", ephemeral=True)
                    
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while updating stock: {e}", ephemeral=True)


    # --- CLEAR STOCK (Prefix) ---
    @commands.command(name="stockclear", description="Clear all accounts from a service stock")
    @commands.is_owner()
    async def stockclear_prefix(self, ctx: commands.Context, service_name: str):
        if service_name not in self.services:
            return await ctx.reply(f"❌ Service `{service_name}` does not exist.")

        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        try:
            # Check current stock size before clearing
            async with aiofiles.open(stock_file_path, mode='r') as f:
                lines = await f.readlines()
            count = len([line for line in lines if line.strip()])
            
            # Clear the file by opening in write mode and writing nothing
            async with aiofiles.open(stock_file_path, mode='w') as f:
                await f.write('')

            await ctx.reply(f"✅ Cleared **{count}** accounts from `{service_name}` stock.")
        except FileNotFoundError:
            await ctx.reply(f"❌ Stock file for `{service_name}` not found. (No action taken)")
        except Exception as e:
            await ctx.reply(f"❌ An error occurred while clearing stock: {e}")

    # --- CLEAR STOCK (Slash) ---
    @app_commands.command(name="stockclear", description="Clear all accounts from a service stock")
    @app_commands.autocomplete(service_name=service_autocomplete)
    @app_commands.is_owner()
    async def stockclear_slash(self, interaction: discord.Interaction, service_name: str):
        if service_name not in self.services:
            return await interaction.response.send_message(f"❌ Service `{service_name}` does not exist.", ephemeral=True)

        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        try:
            # Check current stock size before clearing
            async with aiofiles.open(stock_file_path, mode='r') as f:
                lines = await f.readlines()
            count = len([line for line in lines if line.strip()])
            
            # Clear the file by opening in write mode and writing nothing
            async with aiofiles.open(stock_file_path, mode='w') as f:
                await f.write('')

            await interaction.response.send_message(f"✅ Cleared **{count}** accounts from `{service_name}` stock.", ephemeral=True)
        except FileNotFoundError:
            await interaction.response.send_message(f"❌ Stock file for `{service_name}` not found. (No action taken)", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while clearing stock: {e}", ephemeral=True)


    # --- BULK RESTOCK (Prefix) ---
    @commands.command(name="stockrefill", description="Bulk restock multiple services (Format: service:account|service2:account2)")
    @commands.is_owner()
    async def stockrefill_prefix(self, ctx: commands.Context, *, accounts: str):
        restocked_count = {}
        
        # Split into service:account pairs
        pairs = [p.strip() for p in accounts.split('|') if p.strip()]
        
        if not pairs:
            return await ctx.reply("⚠️ Invalid format. Use `service:account|service2:account2|...`")
            
        for pair in pairs:
            if ':' not in pair:
                continue
                
            service_name, account = pair.split(':', 1)
            service_name = service_name.strip()
            account = account.strip()
            
            if service_name not in self.services or not account:
                continue

            stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
            
            try:
                async with aiofiles.open(stock_file_path, mode='a+') as f:
                    # Check for duplicates (simplified approach for restock - assumes no existing duplicates check needed for speed)
                    await f.seek(0)
                    existing_lines = [line.strip() for line in (await f.readlines()) if line.strip()]
                    
                    if account not in existing_lines:
                        await f.write(account + '\n')
                        restocked_count[service_name] = restocked_count.get(service_name, 0) + 1
                        
            except Exception as e:
                print(f"Restock error for {service_name}: {e}")
                
        if restocked_count:
            summary = "\n".join([f"**{name}**: +{count}" for name, count in restocked_count.items()])
            embed = discord.Embed(
                title="📈 Bulk Stock Refill Complete",
                description=summary,
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("⚠️ No valid accounts were restocked.")

    # --- BULK RESTOCK (Slash) ---
    @app_commands.command(name="stockrefill", description="Bulk restock multiple services (Format: service:account|service2:account2)")
    @app_commands.is_owner()
    async def stockrefill_slash(self, interaction: discord.Interaction, accounts: str):
        await interaction.response.defer(ephemeral=True)
        restocked_count = {}
        
        # Split into service:account pairs
        pairs = [p.strip() for p in accounts.split('|') if p.strip()]
        
        if not pairs:
            return await interaction.followup.send("⚠️ Invalid format. Use `service:account|service2:account2|...`", ephemeral=True)
            
        for pair in pairs:
            if ':' not in pair:
                continue
                
            service_name, account = pair.split(':', 1)
            service_name = service_name.strip()
            account = account.strip()
            
            if service_name not in self.services or not account:
                continue

            stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
            
            try:
                async with aiofiles.open(stock_file_path, mode='a+') as f:
                    # Check for duplicates (simplified approach for restock)
                    await f.seek(0)
                    existing_lines = [line.strip() for line in (await f.readlines()) if line.strip()]
                    
                    if account not in existing_lines:
                        await f.write(account + '\n')
                        restocked_count[service_name] = restocked_count.get(service_name, 0) + 1
                        
            except Exception as e:
                print(f"Restock error for {service_name}: {e}")
                
        if restocked_count:
            summary = "\n".join([f"**{name}**: +{count}" for name, count in restocked_count.items()])
            embed = discord.Embed(
                title="📈 Bulk Stock Refill Complete",
                description=summary,
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("⚠️ No valid accounts were restocked.", ephemeral=True)


    # --- CHECK STOCK (Prefix) ---
    @commands.command(name="stockview", description="View the current stock level for a specific service")
    @commands.is_owner()
    async def stockview_prefix(self, ctx: commands.Context, service_name: str):
        if service_name not in self.services:
            return await ctx.reply(f"❌ Service `{service_name}` does not exist.")

        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        try:
            async with aiofiles.open(stock_file_path, mode='r') as f:
                lines = await f.readlines()
            count = len([line for line in lines if line.strip()])
            
            embed = discord.Embed(
                title=f"📊 Stock for `{service_name}`",
                description=f"Current Stock: **{count}** accounts.",
                color=discord.Color.teal()
            )
            await ctx.reply(embed=embed)
        except FileNotFoundError:
            await ctx.reply(f"❌ Stock file for `{service_name}` not found.")
        except Exception as e:
            await ctx.reply(f"❌ An error occurred while checking stock: {e}")

    # --- CHECK STOCK (Slash) ---
    @app_commands.command(name="stockview", description="View the current stock level for a specific service")
    @app_commands.autocomplete(service_name=service_autocomplete)
    @app_commands.is_owner()
    async def stockview_slash(self, interaction: discord.Interaction, service_name: str):
        if service_name not in self.services:
            return await interaction.response.send_message(f"❌ Service `{service_name}` does not exist.", ephemeral=True)

        stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
        
        try:
            async with aiofiles.open(stock_file_path, mode='r') as f:
                lines = await f.readlines()
            count = len([line for line in lines if line.strip()])
            
            embed = discord.Embed(
                title=f"📊 Stock for `{service_name}`",
                description=f"Current Stock: **{count}** accounts.",
                color=discord.Color.teal()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except FileNotFoundError:
            await interaction.response.send_message(f"❌ Stock file for `{service_name}` not found.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred while checking stock: {e}", ephemeral=True)


    # =========================================================================
    # GLOBAL ADMIN COMMANDS
    # =========================================================================

    # --- GLOBAL SETTINGS ---
    @commands.command(name="globalconfig", description="Set global generator settings")
    @commands.is_owner()
    async def globalconfig_prefix(self, ctx: commands.Context, key: str, value: str):
        key = key.lower()
        if key not in DEFAULT_GLOBAL_CONFIG:
            return await ctx.reply(f"❌ Invalid global setting key. Available keys: `{', '.join(DEFAULT_GLOBAL_CONFIG.keys())}`")

        # Type conversion based on key
        if 'cooldown' in key:
            try:
                config_value = int(value)
            except ValueError:
                return await ctx.reply("❌ Cooldowns must be an integer (seconds).")
        elif key == 'restock_logging_enabled':
            config_value = value.lower() in ('true', 'yes', '1')
        else:
            config_value = value
            
        await update_global_config(key, config_value)
        self.global_config = await load_global_config() # Refresh local copy

        embed = discord.Embed(
            title="🌐 Global Settings Updated",
            description=f"Set **{key}** to `{config_value}` globally.",
            color=discord.Color.blue()
        )
        await ctx.reply(embed=embed)

    @app_commands.command(name="globalconfig", description="Set global generator settings")
    @app_commands.is_owner()
    @app_commands.describe(key="The global setting key", value="The value for the setting")
    async def globalconfig_slash(self, interaction: discord.Interaction, key: str, value: str):
        key = key.lower()
        if key not in DEFAULT_GLOBAL_CONFIG:
            return await interaction.response.send_message(f"❌ Invalid global setting key. Available keys: `{', '.join(DEFAULT_GLOBAL_CONFIG.keys())}`", ephemeral=True)

        # Type conversion based on key
        if 'cooldown' in key:
            try:
                config_value = int(value)
            except ValueError:
                return await interaction.response.send_message("❌ Cooldowns must be an integer (seconds).", ephemeral=True)
        elif key == 'restock_logging_enabled':
            config_value = value.lower() in ('true', 'yes', '1')
        else:
            config_value = value
            
        await update_global_config(key, config_value)
        self.global_config = await load_global_config() # Refresh local copy

        embed = discord.Embed(
            title="🌐 Global Settings Updated",
            description=f"Set **{key}** to `{config_value}` globally.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    # --- BLACKLIST COMMAND ---
    @commands.group(name="modblacklist", description="Manage the generator blacklist", invoke_without_command=True)
    @commands.is_owner()
    async def modblacklist_prefix(self, ctx: commands.Context):
        await ctx.send("Missing action. Use `!modblacklist add`, `!modblacklist remove`, or `!modblacklist list`.")
        
    @modblacklist_prefix.command(name="add", description="Add a user to the blacklist")
    @commands.is_owner()
    async def modblacklist_add_prefix(self, ctx: commands.Context, member: Union[discord.Member, discord.User], *, reason: Optional[str] = "No reason provided"):
        if member.id in self.blacklist:
            return await ctx.reply(f"❌ {member.mention} is already blacklisted.")
            
        self.blacklist.append(member.id)
        await update_blacklist(self.blacklist)
        
        embed = discord.Embed(
            title="🚫 User Blacklisted",
            description=f"{member.mention} added to the blacklist.\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)

    @modblacklist_prefix.command(name="remove", description="Remove a user from the blacklist")
    @commands.is_owner()
    async def modblacklist_remove_prefix(self, ctx: commands.Context, member: Union[discord.Member, discord.User]):
        if member.id not in self.blacklist:
            return await ctx.reply(f"❌ {member.mention} is not currently blacklisted.")
            
        self.blacklist.remove(member.id)
        await update_blacklist(self.blacklist)
        
        embed = discord.Embed(
            title="✅ Blacklist Removed",
            description=f"{member.mention} removed from the blacklist.",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)

    @modblacklist_prefix.command(name="list", description="List all blacklisted users")
    @commands.is_owner()
    async def modblacklist_list_prefix(self, ctx: commands.Context):
        if not self.blacklist:
            return await ctx.reply("The generator blacklist is currently empty.")
            
        user_list = []
        for user_id in self.blacklist:
            user = self.bot.get_user(user_id)
            user_list.append(f"{user.name if user else 'Unknown User'} (`{user_id}`)")
            
        embed = discord.Embed(
            title="📋 Generator Blacklist",
            description="\n".join(user_list) or "The blacklist is currently empty.",
            color=discord.Color.dark_red()
        )
        await ctx.reply(embed=embed)

    # --- BLACKLIST COMMAND (Slash) ---
    @app_commands.command(name="modblacklist", description="Manage the generator blacklist")
    @app_commands.is_owner()
    @app_commands.describe(
        action="The action to perform: add, remove, or list",
        member="The user to add or remove (required for add/remove)",
        reason="The reason for blacklisting (optional for add)"
    )
    async def modblacklist_slash(self, interaction: discord.Interaction, 
                                action: Literal['add', 'remove', 'list'], 
                                member: Optional[Union[discord.Member, discord.User]] = None, 
                                reason: Optional[str] = "No reason provided"):
        
        if action in ('add', 'remove') and member is None:
            return await interaction.response.send_message("❌ You must specify a user for the 'add' or 'remove' action.", ephemeral=True)

        if action == 'list':
            if not self.blacklist:
                return await interaction.response.send_message("The generator blacklist is currently empty.", ephemeral=True)
            
            user_list = []
            for user_id in self.blacklist:
                user = self.bot.get_user(user_id)
                user_list.append(f"{user.name if user else 'Unknown User'} (`{user_id}`)")
                
            embed = discord.Embed(
                title="📋 Generator Blacklist",
                description="\n".join(user_list) or "The blacklist is currently empty.",
                color=discord.Color.dark_red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == 'add':
            member = cast(Union[discord.Member, discord.User], member)
            if member.id in self.blacklist:
                return await interaction.response.send_message(f"❌ {member.mention} is already blacklisted.", ephemeral=True)
            
            self.blacklist.append(member.id)
            await update_blacklist(self.blacklist)
            
            embed = discord.Embed(
                title="🚫 User Blacklisted",
                description=f"{member.mention} added to the blacklist.\n**Reason:** {reason}",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action == 'remove':
            member = cast(Union[discord.Member, discord.User], member)
            if member.id not in self.blacklist:
                return await interaction.response.send_message(f"❌ {member.mention} is not currently blacklisted.", ephemeral=True)
            
            self.blacklist.remove(member.id)
            await update_blacklist(self.blacklist)
            
            embed = discord.Embed(
                title="✅ Blacklist Removed",
                description=f"{member.mention} removed from the blacklist.",
                color=discord.Color.green()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)


    # =========================================================================
    # INFO / STATS COMMANDS
    # =========================================================================

    # --- GENERATION STATS ---
    @commands.command(name="viewstats", description="View global generation statistics")
    @commands.is_owner()
    async def viewstats_prefix(self, ctx: commands.Context):
        stats = await load_json(GLOBAL_STATS_FILE, {})
        
        if not stats:
            return await ctx.reply("📊 No generation statistics available yet.")
            
        total_gens = sum(stats.values())
        stats_list = [f"**{service}**: {count} generations" for service, count in sorted(stats.items(), key=lambda item: item[1], reverse=True)]
        
        embed = discord.Embed(
            title="📈 Global Generation Statistics",
            description="\n".join(stats_list) if stats_list else "No data.",
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Total Generations: {total_gens}")
        await ctx.reply(embed=embed)

    @app_commands.command(name="viewstats", description="View global generation statistics")
    @app_commands.is_owner()
    async def viewstats_slash(self, interaction: discord.Interaction):
        stats = await load_json(GLOBAL_STATS_FILE, {})
        
        if not stats:
            return await interaction.response.send_message("📊 No generation statistics available yet.", ephemeral=True)
            
        total_gens = sum(stats.values())
        stats_list = [f"**{service}**: {count} generations" for service, count in sorted(stats.items(), key=lambda item: item[1], reverse=True)]
        
        embed = discord.Embed(
            title="📈 Global Generation Statistics",
            description="\n".join(stats_list) if stats_list else "No data.",
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Total Generations: {total_gens}")
        await interaction.response.send_message(embed=embed, ephemeral=True)


    # --- VIEW ALL STOCK ---
    @commands.command(name="viewstockall", description="View stock levels for all services")
    @commands.is_owner()
    async def viewstockall_prefix(self, ctx: commands.Context):
        stock_summary = []
        total_stock = 0
        
        for service_name in self.services.keys():
            stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
            count = 0
            try:
                async with aiofiles.open(stock_file_path, mode='r') as f:
                    lines = await f.readlines()
                count = len([line for line in lines if line.strip()])
            except FileNotFoundError:
                pass # File missing means 0 stock
                
            stock_summary.append(f"**{service_name}**: {count}")
            total_stock += count
            
        if not stock_summary:
            return await ctx.reply("❌ No services defined.")

        embed = discord.Embed(
            title="📦 Current Stock Levels",
            description="\n".join(stock_summary),
            color=discord.Color.dark_green()
        )
        embed.set_footer(text=f"Total Accounts in Stock: {total_stock}")
        await ctx.reply(embed=embed)

    @app_commands.command(name="viewstockall", description="View stock levels for all services")
    @app_commands.is_owner()
    async def viewstockall_slash(self, interaction: discord.Interaction):
        stock_summary = []
        total_stock = 0
        
        for service_name in self.services.keys():
            stock_file_path = os.path.join(STOCK_BASE_FOLDER, f"{service_name}.txt")
            count = 0
            try:
                async with aiofiles.open(stock_file_path, mode='r') as f:
                    lines = await f.readlines()
                count = len([line for line in lines if line.strip()])
            except FileNotFoundError:
                pass # File missing means 0 stock
                
            stock_summary.append(f"**{service_name}**: {count}")
            total_stock += count
            
        if not stock_summary:
            return await interaction.response.send_message("❌ No services defined.", ephemeral=True)

        embed = discord.Embed(
            title="📦 Current Stock Levels",
            description="\n".join(stock_summary),
            color=discord.Color.dark_green()
        )
        embed.set_footer(text=f"Total Accounts in Stock: {total_stock}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # =========================================================================
    # NITRO COMMANDS
    # =========================================================================

    # --- SEND FAKE NITRO ---
    @commands.command(name="sendfake", description="Send a fake item to a user (e.g., fake Nitro)")
    @commands.is_owner()
    async def sendfake_prefix(self, ctx: commands.Context, member: discord.Member, amount: int, item: Literal['nitro']):
        if amount <= 0:
            return await ctx.reply("❌ Amount must be greater than 0.")
            
        embed = discord.Embed(
            title=f"💸 {amount} Fake {item.title()} Sent!",
            description=f"Successfully sent **{amount}** fake {item} to {member.mention}.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)

    @app_commands.command(name="sendfake", description="Send a fake item to a user (e.g., fake Nitro)")
    @app_commands.is_owner()
    @app_commands.describe(member="The user to send the fake item to", amount="The quantity", item="The item to send (only 'nitro')")
    async def sendfake_slash(self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1], item: Literal['nitro']):
        # No need to check amount > 0 due to app_commands.Range[int, 1]
        
        embed = discord.Embed(
            title=f"💸 {amount} Fake {item.title()} Sent!",
            description=f"Successfully sent **{amount}** fake {item} to {member.mention}.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- SEND MASS FAKE NITRO ---
    @commands.command(name="sendmassfake", description="Mass send a fake item to all server members (e.g., fake Nitro)")
    @commands.is_owner()
    async def sendmassfake_prefix(self, ctx: commands.Context, amount: int, item: Literal['nitro']):
        if amount <= 0:
            return await ctx.reply("❌ Amount must be greater than 0.")
            
        embed = discord.Embed(
            title=f"📢 Mass Sent {amount} Fake {item.title()}",
            description=f"Successfully mass sent **{amount}** fake {item} to all members on the server.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)

    @app_commands.command(name="sendmassfake", description="Mass send a fake item to all server members (e.g., fake Nitro)")
    @app_commands.is_owner()
    @app_commands.describe(amount="The quantity", item="The item to send (only 'nitro')")
    async def sendmassfake_slash(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1], item: Literal['nitro']):
        # No need to check amount > 0 due to app_commands.Range[int, 1]

        embed = discord.Embed(
            title=f"📢 Mass Sent {amount} Fake {item.title()}",
            description=f"Successfully mass sent **{amount}** fake {item} to all members on the server.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


    # =========================================================================
    # HELP COMMAND (ADMIN GUIDE)
    # =========================================================================

    @commands.command(name="genadminhelp", description="Shows the generator administration guide")
    @commands.is_owner()
    async def genadminhelp_prefix(self, ctx: commands.Context):
        embed = discord.Embed(
            title="📜 Sentinel Generator Admin Guide",
            description="All commands are for bot owners/admins.",
            color=discord.Color.dark_teal()
        )

        embed.add_field(
            name="🔧 Generator Commands",
            value=(
                "`!freegen <service>` - Free generation (User command)\\n"
                "`!premiumgen <service>` - Premium generation (User command)\\n"
                "`!boostergen <service>` - Booster generation (User command)"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`!gensettings <key> <value>` - Set role/channel/max_amount for this guild\\n"
                "`!globalconfig <key> <value>` - Set global cooldowns/logging"
            ),
            inline=False
        )

        embed.add_field(
            name="📦 Service & Stock Management",
            value=(
                "`!stockaddservice <name>` - Add a new service\\n"
                "`!stockremoveservice <name>` - Remove a service\\n"
                "`!stockupdate <service> <accounts>` - Add accounts to stock\\n"
                "`!stockclear <service>` - Clear stock for a service\\n"
                "`!stockrefill <service:acc|service2:acc2>` - Bulk restock"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚫 Moderation",
            value=(
                "`!modblacklist add @user [reason]` - Blacklist user\\n"
                "`!modblacklist remove @user` - Unblacklist user\\n"
                "`!modblacklist list` - View blacklisted users"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Analytics",
            value=(
                "`!viewstats` - View generation statistics\\n"
                "`!viewstockall` - View current stock levels"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Nitro Commands",
            value=(
                "`!sendfake @user <amount> nitro` - Send fake Nitro\\n"
                "`!sendmassfake <amount> nitro` - Mass send fake Nitro"
            ),
            inline=False
        )

        embed.set_footer(text="Sentinel Generator | Admin Guide")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3953/3953226.png")

        await ctx.send(embed=embed)


    @app_commands.command(name="genadminhelp", description="Shows the generator administration guide")
    @app_commands.is_owner()
    async def genadminhelp_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Sentinel Generator Admin Guide",
            description="All commands are for bot owners/admins.",
            color=discord.Color.dark_teal()
        )

        embed.add_field(
            name="🔧 Generator Commands",
            value=(
                "`/freegen <service>` - Free generation (User command)\\n"
                "`/premiumgen <service>` - Premium generation (User command)\\n"
                "`/boostergen <service>` - Booster generation (User command)"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`/gensettings <key> <value>` - Set role/channel/max_amount for this guild\\n"
                "`/globalconfig <key> <value>` - Set global cooldowns/logging"
            ),
            inline=False
        )

        embed.add_field(
            name="📦 Service & Stock Management",
            value=(
                "`/stockaddservice <name>` - Add a new service\\n"
                "`/stockremoveservice <name>` - Remove a service\\n"
                "`/stockupdate <service> <accounts>` - Add accounts to stock\\n"
                "`/stockclear <service>` - Clear stock for a service\\n"
                "`/stockrefill <service:acc|service2:acc2>` - Bulk restock"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚫 Moderation",
            value=(
                "`/modblacklist add <user> [reason]` - Blacklist user\\n"
                "`/modblacklist remove <user>` - Unblacklist user\\n"
                "`/modblacklist list` - View blacklisted users"
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Analytics",
            value=(
                "`/viewstats` - View generation statistics\\n"
                "`/viewstockall` - View current stock levels"
            ),
            inline=False
        )

        embed.add_field(
            name="💰 Nitro Commands",
            value=(
                "`/sendfake <user> <amount> nitro` - Send fake Nitro\\n"
                "`/sendmassfake <amount> nitro` - Mass send fake Nitro"
            ),
            inline=False
        )

        embed.set_footer(text="Sentinel Generator | Admin Guide")
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3953/3953226.png")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    cog = Generator(bot)
    await bot.add_cog(cog)
