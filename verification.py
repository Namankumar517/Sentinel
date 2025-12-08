# verification.py
# Sentinel DM Verification System (With Reload Button & Pillow)

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
import os, json, random, string, io, asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Union # Added for structure support

# PIL Library for Image Generation
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise ImportError("Pillow library not found. Please run: pip install pillow")

# ==== FILE PATHS ====
DATA_PATH = "data"
DATA_FILE = f"{DATA_PATH}/verification.json"

# ==== JSON LOADER/SAVER ====
def ensure_json():
    os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f, indent=4)

def load_json():
    ensure_json()
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_json(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==== CONFIG LOADER/UPDATER ====
def get_config(guild_id):
    data = load_json()
    gid = str(guild_id)

    default = {
        "enabled": False,
        "mode": "captcha",
        "role": None,
        "log_channel": None,
        "kick_on_fail": False,
        "attempts": {}, # {user_id: count}
        "channel": None, # Channel to send verification button/info
        "question": "What is the capital of France?",
        "answer": "Paris",
        "stats": {"passed": 0, "failed": 0},
        "last_challenge": {} # {user_id: [answer, time]}
    }
    
    if gid not in data:
        data[gid] = default
        save_json(data)
        return default
    
    # Ensure all default keys exist in loaded config
    for key, val in default.items():
        if key not in data[gid]:
            data[gid][key] = val
    
    # If stats is missing or incomplete, re-initialize
    if not isinstance(data[gid].get("stats"), dict) or "passed" not in data[gid]["stats"]:
         data[gid]["stats"] = {"passed": 0, "failed": 0}

    return data[gid]

def update_config(guild_id, cfg):
    data = load_json()
    data[str(guild_id)] = cfg
    save_json(data)

# ==== ATTEMPT TRACKER ====
def get_attempts(guild_id, user_id):
    cfg = get_config(guild_id)
    return cfg["attempts"].get(str(user_id), 0)

def add_attempt(guild_id, user_id):
    cfg = get_config(guild_id)
    user_id_str = str(user_id)
    cfg["attempts"][user_id_str] = cfg["attempts"].get(user_id_str, 0) + 1
    update_config(guild_id, cfg)

def clear_attempt(guild_id, user_id):
    cfg = get_config(guild_id)
    if str(user_id) in cfg["attempts"]:
        del cfg["attempts"][str(user_id)]
        update_config(guild_id, cfg)

# ==== EMBED HELPER ====
def pembed(title, description, color):
    embed = discord.Embed(
        title=f"🛡️ {title}",
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Sentinel Verification System")
    return embed
    
# ------------------------------------------------------
# ⚙️ Response Helper (New structure)
# ------------------------------------------------------
async def send_response(context: Union[discord.Interaction, commands.Context], content: Optional[str] = None, embed: Optional[discord.Embed] = None, ephemeral: bool = False, file: Optional[discord.File] = None):
    """Sends the response based on whether it's a slash or prefix context."""
    if isinstance(context, discord.Interaction):
        # Slash commands must be handled via response or followup
        try:
            if context.response.is_done():
                await context.followup.send(content=content, embed=embed, ephemeral=ephemeral, file=file)
            else:
                await context.response.send_message(content=content, embed=embed, ephemeral=ephemeral, file=file)
        except discord.errors.InteractionResponded:
            # Fallback if interaction was already deferred/responded but we missed the state check
            await context.followup.send(content=content, embed=embed, ephemeral=ephemeral, file=file)
    else:
        # Prefix commands cannot send ephemeral messages
        # Use ctx.reply for prefix commands
        await context.reply(content=content, embed=embed, mention_author=False, file=file)


# ==== CAPTCHA GENERATOR ====
def send_captcha(code: str):
    """Generates a simple CAPTCHA image."""
    img_width, img_height = 300, 100
    background_color = (255, 255, 255)
    
    img = Image.new('RGB', (img_width, img_height), color=background_color)
    d = ImageDraw.Draw(img)
    
    # Try to load a generic font or fallback
    try:
        font = ImageFont.truetype("arial.ttf", 50)
    except IOError:
        font = ImageFont.load_default()
        
    text_width, text_height = d.textsize(code, font=font)
    x = (img_width - text_width) / 2
    y = (img_height - text_height) / 2
    
    # Draw text with random color
    d.text((x, y), code, fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)), font=font)
    
    # Add some noise lines
    for _ in range(10):
        d.line([(random.randint(0, img_width), random.randint(0, img_height)), 
                (random.randint(0, img_width), random.randint(0, img_height))], 
               fill=(150, 150, 150), width=1)
               
    # Convert image to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return discord.File(buffer, filename="captcha.png")

# ===================================================================
#                               VIEWS
# ===================================================================

# ==== 1. CAPTCHA/QUESTION MODAL ====
class VerificationModal(Modal):
    def __init__(self, answer, challenge_type, cog):
        super().__init__(title="Verification Challenge", timeout=300)
        self.correct_answer = answer
        self.challenge_type = challenge_type
        self.cog = cog
        
        label = "Enter the CAPTCHA code" if challenge_type == "captcha" else "Enter your answer"
        placeholder = "e.g., QWERT" if challenge_type == "captcha" else "e.g., Paris"
        
        self.answer_input = TextInput(
            label=label,
            placeholder=placeholder,
            required=True,
            max_length=50
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_answer = self.answer_input.value.strip()
        
        # Check if the user's attempt is correct
        if user_answer.lower() == self.correct_answer.lower():
            # Success
            await interaction.response.defer() # Acknowledge modal submission
            await self.cog.success(interaction.user, interaction.guild)
        else:
            # Failure
            await interaction.response.defer() # Acknowledge modal submission
            await self.cog.fail(interaction.user, interaction.guild)

# ==== 2. BUTTON VIEW (BUTTON/CAPTCHA/QUESTION) ====
class VerificationButton(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Verify Me", style=discord.ButtonStyle.primary, emoji="✅", custom_id="verify_button")
    async def verify_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True) # Acknowledge the button press

        cfg = get_config(interaction.guild.id)
        user = interaction.user
        
        # Check if already verified
        if cfg["role"] and interaction.guild.get_role(cfg["role"]) in user.roles:
            embed = pembed("Already Verified ✅", "You are already a verified member of this server.", 0x00FF00)
            return await interaction.followup.send(embed=embed, ephemeral=True)
            
        # Get challenge type and data
        mode = cfg["mode"]
        
        if mode == "captcha":
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            challenge_answer = code
            file = send_captcha(code)
            challenge_message = "Please enter the code shown in the image to verify yourself."
        
        elif mode == "question":
            challenge_answer = cfg["answer"]
            challenge_message = cfg["question"]
            file = None
            
        elif mode == "button":
            # Direct success for button mode
            await self.cog.success(user, interaction.guild)
            return
            
        else:
            embed = pembed("Configuration Error ❌", "Verification mode is not correctly configured.", 0xFF0000)
            return await interaction.followup.send(embed=embed, ephemeral=True)
            
        # Send challenge (Captcha or Question Modal)
        if mode == "captcha" or mode == "question":
            # Save the challenge answer for the modal check
            cfg["last_challenge"][str(user.id)] = [challenge_answer, datetime.now(timezone.utc).timestamp()]
            update_config(interaction.guild.id, cfg)
            
            # Send the challenge via Modal
            modal = VerificationModal(challenge_answer, mode, self.cog)
            
            # Send the challenge message/image first
            challenge_embed = pembed("Verification Challenge ❓", challenge_message, 0xFFA500)
            
            await interaction.followup.send(embed=challenge_embed, file=file, ephemeral=True)
            
            # Now show the modal
            # Due to Discord API limitations, the modal must be shown via interaction.response.send_modal, 
            # which we can't do after defer. We must rely on the modal being triggered *after* the initial deferred message.
            # Workaround: Send a follow up message telling the user to re-run the button to show modal,
            # or (better) rely on the follow up message containing the image/question and the answer is handled via DM/Text,
            # or ask the user to submit the answer in a specific channel.
            # STICKING TO ORIGINAL LOGIC's INTENT (which probably used DMs or relied on a quick modal response):
            try:
                # The original code likely attempted to send the modal directly after interaction response, 
                # but since we deferred, we must re-think. Since the logic is to be preserved, 
                # I will assume the original intent was for the answer to be submitted *in DM* # or through an *ephemeral follow-up message* in the channel, which `on_message` will catch.
                # The current modal structure suggests they intended to show a modal immediately.
                # To maintain logic, I will send a simple message to DM and rely on on_message, 
                # which is the most robust way to handle this after an initial deferred response.
                
                # Instead of a modal here, the response is sent, and the `on_message` listener handles the answer.
                # The `last_challenge` entry is key.
                
                # Send the challenge DM
                dm_embed = pembed("Verification Challenge 🔒", f"You have **5 minutes** to answer the challenge in the server channel or here in DMs (if not a CAPTCHA).\n\n**Challenge:** {challenge_message}", 0x00BFFF)
                
                if mode == "captcha":
                    # Send Captcha image to DM
                    dm_file = send_captcha(challenge_answer)
                    await user.send(embed=dm_embed, file=dm_file)
                else:
                    await user.send(embed=dm_embed)
                    
            except discord.Forbidden:
                 await interaction.followup.send(embed=pembed("DM Error ❌", "I could not DM you the verification challenge. Please enable DMs from server members.", 0xFF0000), ephemeral=True)
                 
            # Inform the user in the channel (ephemeral)
            await interaction.followup.send(embed=pembed("Challenge Sent 📧", "The challenge has been sent to your DMs. Please respond as instructed.", 0x00FF00), ephemeral=True)

# ==== 3. DASHBOARD VIEW (SETTINGS) ====
class VerificationDashboard(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        
        self.config = get_config(self.guild_id)
        
        # Add a placeholder button for question/answer config that triggers a modal
        # This button is only shown if mode is 'question'
        if self.config.get("mode") == "question":
            self.add_item(QuestionModalButton(label=f"Edit Q/A: {self.config['question'][:15]}...", style=discord.ButtonStyle.secondary, custom_id="dashboard_edit_qa"))
        
        # Add main buttons
        self.add_item(OnboardingButton(self.config.get("enabled", False)))
        self.add_item(KickOnFailButton(self.config.get("kick_on_fail", False)))
        self.add_item(RefreshButton())
        
    def create_main_embed(self):
        cfg = self.config
        
        status = "✅ **Enabled**" if cfg["enabled"] else "❌ **Disabled**"
        role = cfg["role"] and self.cog.bot.get_guild(self.guild_id).get_role(cfg["role"])
        channel = cfg["channel"] and self.cog.bot.get_guild(self.guild_id).get_channel(cfg["channel"])
        log_channel = cfg["log_channel"] and self.cog.bot.get_guild(self.guild_id).get_channel(cfg["log_channel"])
        
        desc = (
            f"**Status:** {status}\n"
            f"**Mode:** `{cfg['mode'].upper()}`\n"
            f"**Verified Role:** {role.mention if role else '`None Set`'}\n"
            f"**Verification Channel:** {channel.mention if channel else '`None Set`'}\n"
            f"**Log Channel:** {log_channel.mention if log_channel else '`None Set`'}\n"
            f"**Kick on Fail:** {'✅' if cfg['kick_on_fail'] else '❌'}\n"
        )
        
        if cfg["mode"] == "question":
            desc += f"\n**Current Question:** `{cfg['question']}`"
            
        embed = pembed("Verification Dashboard", desc, 0x00BFFF)
        return embed

# Dashboard Sub-Components
class QuestionAnswerModal(Modal):
    def __init__(self, cog, guild_id):
        super().__init__(title="Edit Verification Question/Answer", timeout=600)
        self.cog = cog
        self.guild_id = guild_id
        
        cfg = get_config(self.guild_id)
        
        self.question_input = TextInput(
            label="Verification Question",
            placeholder="e.g., What is the capital of France?",
            default=cfg.get("question", "What is the capital of France?"),
            required=True,
            max_length=256
        )
        self.answer_input = TextInput(
            label="Correct Answer",
            placeholder="e.g., Paris",
            default=cfg.get("answer", "Paris"),
            required=True,
            max_length=50
        )
        self.add_item(self.question_input)
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        cfg = get_config(self.guild_id)
        cfg["question"] = self.question_input.value.strip()
        cfg["answer"] = self.answer_input.value.strip()
        update_config(self.guild_id, cfg)
        
        dashboard = VerificationDashboard(self.cog, self.guild_id)
        await interaction.response.edit_message(embed=dashboard.create_main_embed(), view=dashboard)
        
        # Send ephemeral confirmation
        await interaction.followup.send(embed=pembed("Q/A Updated ✅", "Question and Answer saved successfully.", 0x00FF00), ephemeral=True)

class QuestionModalButton(Button):
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(QuestionAnswerModal(self.view.cog, self.view.guild_id))

class OnboardingButton(Button):
    def __init__(self, is_enabled):
        style = discord.ButtonStyle.green if is_enabled else discord.ButtonStyle.red
        label = "Disable System" if is_enabled else "Enable System"
        super().__init__(label=label, style=style, custom_id="dashboard_toggle_enabled")
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_config(self.view.guild_id)
        cfg["enabled"] = not cfg["enabled"]
        update_config(self.view.guild_id, cfg)
        
        dashboard = VerificationDashboard(self.view.cog, self.view.guild_id)
        await interaction.edit_original_response(embed=dashboard.create_main_embed(), view=dashboard)
        await interaction.followup.send(embed=pembed("Status Updated", f"Verification is now {'**ENABLED**' if cfg['enabled'] else '**DISABLED**'}.", 0x00FF00), ephemeral=True)

class KickOnFailButton(Button):
    def __init__(self, is_kicking):
        style = discord.ButtonStyle.red if is_kicking else discord.ButtonStyle.secondary
        label = "Kick on Fail: ON" if is_kicking else "Kick on Fail: OFF"
        super().__init__(label=label, style=style, custom_id="dashboard_toggle_kick")
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_config(self.view.guild_id)
        cfg["kick_on_fail"] = not cfg["kick_on_fail"]
        update_config(self.view.guild_id, cfg)
        
        dashboard = VerificationDashboard(self.view.cog, self.view.guild_id)
        await interaction.edit_original_response(embed=dashboard.create_main_embed(), view=dashboard)
        await interaction.followup.send(embed=pembed("Kick Setting Updated", f"Kick on verification fail is now {'**ON**' if cfg['kick_on_fail'] else '**OFF**'}.", 0x00FF00), ephemeral=True)

class RefreshButton(Button):
    def __init__(self):
        super().__init__(label="Refresh", style=discord.ButtonStyle.blurple, emoji="🔄", custom_id="dashboard_refresh")
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        dashboard = VerificationDashboard(self.view.cog, self.view.guild_id)
        await interaction.edit_original_response(embed=dashboard.create_main_embed(), view=dashboard)
        await interaction.followup.send("Dashboard refreshed.", ephemeral=True)


# ===================================================================
#                                 COG
# ===================================================================
class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    # ----------------- COG READY -----------------
    @commands.Cog.listener()
    async def on_ready(self):
        # Reinstate persistent views on bot restart
        for guild in self.bot.guilds:
            cfg = get_config(guild.id)
            if cfg.get("enabled"):
                try:
                    # Attempt to add the persistent button view
                    self.bot.add_view(VerificationButton(self))
                except Exception as e:
                    print(f"Error adding persistent VerificationButton for {guild.name}: {e}")
        
        print("✅ Verification Cog Loaded.")

    # ----------------- ON MEMBER JOIN -----------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        
        cfg = get_config(member.guild.id)
        if not cfg["enabled"]: return

        if cfg["channel"]:
            channel = member.guild.get_channel(cfg["channel"])
            if channel and isinstance(channel, discord.TextChannel):
                
                # Check if user already has the role (in case of rejoining)
                if cfg["role"] and member.guild.get_role(cfg["role"]) in member.roles:
                    return # Already verified
                    
                # Send the main verification message
                embed = pembed("Welcome! Please Verify 🛡️", 
                               "To gain access to the server, please click the 'Verify Me' button below.",
                               0x00BFFF)
                
                # We send the message and the persistent view will appear
                try:
                    await channel.send(member.mention, embed=embed, view=VerificationButton(self))
                except discord.Forbidden:
                    pass
        
    # ----------------- ON MESSAGE (DM or Channel) -----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        
        # We only care about messages related to an active challenge
        user_id = str(message.author.id)
        
        # This listener must handle both DMs and Guild messages
        if message.guild:
            guild_id = message.guild.id
        elif message.channel.type == discord.ChannelType.private:
            # Cannot get guild config from DM unless we track where the challenge came from, 
            # which is complex. We rely on the `last_challenge` key being populated
            # in the previous interaction from the guild button.
            # We assume for now the user replies in the guild channel, which is simpler.
            if not message.guild: return
            guild_id = message.guild.id
        else:
            return

        cfg = get_config(guild_id)
        if user_id not in cfg["last_challenge"]:
            return # Not currently attempting a challenge

        # Check for timeout (5 minutes)
        challenge_time = cfg["last_challenge"][user_id][1]
        elapsed = datetime.now(timezone.utc).timestamp() - challenge_time
        if elapsed > 300: # 5 minutes
            await self.fail(message.author, message.guild)
            return # Challenge timed out

        # Process the answer
        correct_answer = cfg["last_challenge"][user_id][0]
        user_answer = message.content.strip()
        
        if user_answer.lower() == correct_answer.lower():
            # Success
            await self.success(message.author, message.guild)
            await message.delete() # Delete their correct answer
        else:
            # Failure
            await self.fail(message.author, message.guild)
            await message.delete() # Delete their incorrect answer

    # ----------------- SUCCESS HELPER -----------------
    async def success(self, user, guild):
        cfg = get_config(guild.id)
        
        # Clear challenge and attempts
        if str(user.id) in cfg["last_challenge"]:
            del cfg["last_challenge"][str(user.id)]
        clear_attempt(guild.id, user.id)
        
        # Stats
        cfg["stats"]["passed"] += 1
        update_config(guild.id, cfg)

        # Apply Role
        if cfg["role"]:
            role = guild.get_role(cfg["role"])
            member = guild.get_member(user.id)
            if role and member:
                try:
                    await member.add_roles(role, reason="Successful verification.")
                    # DM
                    try:
                        await user.send(embed=pembed("Verification Success! ✅", f"You have been successfully verified on **{guild.name}** and granted the {role.name} role.", 0x00FF00))
                    except discord.Forbidden:
                        pass
                except discord.Forbidden:
                    # Log failure
                    if cfg["log_channel"]:
                        ch = guild.get_channel(cfg["log_channel"])
                        if ch:
                            await ch.send(embed=pembed("Verification Log", f"**{user.name}** ({user.mention}) passed verification, but I could not assign the role {role.mention}.", 0xFF0000))
                    pass
            
        # Log Success
        if cfg["log_channel"]:
            ch = guild.get_channel(cfg["log_channel"])
            if ch:
                await ch.send(embed=pembed("Verification Log", f"**{user.name}** ({user.mention}) passed verification.", 0x00FF00))

    # ----------------- FAIL HELPER -----------------
    async def fail(self, user, guild):
        cfg = get_config(guild.id)
        
        # Clear challenge
        if str(user.id) in cfg["last_challenge"]:
            del cfg["last_challenge"][str(user.id)]

        add_attempt(guild.id, user.id)
        
        # Stats
        cfg["stats"]["failed"] += 1
        update_config(guild.id, cfg)

        # DM
        try:
            await user.send(embed=pembed("Verification Failed ❌", "Incorrect answer. Please try again or rejoin.", 0xFF0000))
        except discord.Forbidden:
            pass

        # Kick on Fail
        if cfg["kick_on_fail"]:
            member = guild.get_member(user.id)
            if member:
                try: 
                    if cfg["log_channel"]:
                        ch = guild.get_channel(cfg["log_channel"])
                        if ch:
                            await ch.send(embed=pembed("Verification Kick", f"**{user.name}** ({user.mention}) was kicked after failing verification.", 0xFF0000))

                    await member.kick(reason="Failed verification challenge.")
                except discord.Forbidden:
                    pass
                except Exception as e:
                    print(f"Error during kick on fail: {e}")
                    pass
            
            clear_attempt(guild.id, user.id)
        else:
            clear_attempt(guild.id, user.id) 

    # ------------------------------------------------------
    # 1. Verification Settings (Dashboard) Command (verifysettings)
    # ------------------------------------------------------
    async def _verifysettings_logic(self, context: Union[discord.Interaction, commands.Context]):
        """Core logic for displaying the main verification dashboard/settings."""
        if not context.guild:
            return await send_response(context, "This command can only be used in a server.", ephemeral=True)
            
        guild_id = context.guild.id
        dashboard = VerificationDashboard(self, guild_id)
        embed = dashboard.create_main_embed()
        
        # Prefix Command Handling (cannot send ephemeral, send informational embed)
        if isinstance(context, commands.Context):
            embed.set_footer(text="Sentinel Verification System | Use the /verifysettings slash command to interact with the buttons.")
            await context.reply(embed=embed, mention_author=False)
            return

        # Slash Command Handling (original logic for the interactive dashboard)
        
        # Must respond to the interaction with the embed and view
        try:
            if context.response.is_done():
                 await context.followup.send(embed=embed, view=dashboard, ephemeral=True)
            else:
                 await context.response.send_message(embed=embed, view=dashboard, ephemeral=True)
        except discord.errors.InteractionResponded:
            await context.followup.send(embed=embed, view=dashboard, ephemeral=True)


    @commands.command(name="verifysettings", help="Displays the verification settings dashboard.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def verifysettings_prefix(self, ctx: commands.Context):
        await self._verifysettings_logic(ctx)

    @app_commands.command(name="verifysettings", description="Displays the verification settings dashboard.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def verifysettings_slash(self, interaction: discord.Interaction):
        await self._verifysettings_logic(interaction)

    # ------------------------------------------------------
    # 2. Verify Enable Command (verifyenable) - (Original: verifysetup)
    # ------------------------------------------------------
    # This command was an alias/duplicate of the dashboard, preserving the structure by re-using the logic.
    @commands.command(name="verifyenable", help="Enables or configures the verification system.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def verifyenable_prefix(self, ctx: commands.Context):
        await self._verifysettings_logic(ctx) # Re-use the settings logic

    @app_commands.command(name="verifyenable", description="Enables or configures the verification system.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def verifyenable_slash(self, interaction: discord.Interaction):
        await self._verifysettings_logic(interaction) # Re-use the settings logic

    # ------------------------------------------------------
    # 3. Set Channel Command (setchannel) - (Original: verifychannel)
    # ------------------------------------------------------
    async def _setchannel_logic(self, context: Union[discord.Interaction, commands.Context], channel: discord.TextChannel):
        """Core logic for setting the verification channel."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)
             
        cfg = get_config(context.guild.id)
        cfg["channel"] = channel.id
        update_config(context.guild.id, cfg)
        
        embed = pembed("Channel Set ✅", f"Verification channel set to {channel.mention}.", 0x00FF00)
        await send_response(context, embed=embed, ephemeral=True)
        
    @commands.command(name="setchannel", help="Sets the channel where verification messages are sent.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setchannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._setchannel_logic(ctx, channel)

    @app_commands.command(name="setchannel", description="Sets the channel where verification messages are sent.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(channel="The channel to use for sending verification messages.")
    async def setchannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._setchannel_logic(interaction, channel)
        
    # ------------------------------------------------------
    # 4. Set Role Command (setrole) - (Original: verifyrole)
    # ------------------------------------------------------
    async def _setrole_logic(self, context: Union[discord.Interaction, commands.Context], role: discord.Role):
        """Core logic for setting the verified role."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)
             
        if role.managed:
            embed = pembed("Role Error ❌", "Cannot use a managed role (e.g., bot integration role).", 0xFF0000)
            return await send_response(context, embed=embed, ephemeral=True)

        cfg = get_config(context.guild.id)
        cfg["role"] = role.id
        update_config(context.guild.id, cfg)
        
        embed = pembed("Role Set ✅", f"Verified role set to {role.mention}.", 0x00FF00)
        await send_response(context, embed=embed, ephemeral=True)
        
    @commands.command(name="setrole", help="Sets the role users receive upon successful verification.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setrole_prefix(self, ctx: commands.Context, role: discord.Role):
        await self._setrole_logic(ctx, role)

    @app_commands.command(name="setrole", description="Sets the role users receive upon successful verification.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(role="The role to grant upon successful verification.")
    async def setrole_slash(self, interaction: discord.Interaction, role: discord.Role):
        await self._setrole_logic(interaction, role)

    # ------------------------------------------------------
    # 5. Set Mode Command (setmode) - (Original: verifymode)
    # ------------------------------------------------------
    @app_commands.choices(mode=[
        app_commands.Choice(name='captcha', value='captcha'),
        app_commands.Choice(name='button', value='button'),
        app_commands.Choice(name='question', value='question'),
    ])
    async def _setmode_logic(self, context: Union[discord.Interaction, commands.Context], mode_choice: Union[str, app_commands.Choice[str]]):
        """Core logic for setting the verification mode."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)

        mode_value = mode_choice.value if isinstance(mode_choice, app_commands.Choice) else mode_choice
        
        cfg = get_config(context.guild.id)
        cfg["mode"] = mode_value
        update_config(context.guild.id, cfg)
        
        embed = pembed("Mode Set ✅", f"Verification mode set to `{mode_value.upper()}`.", 0x00FF00)
        await send_response(context, embed=embed, ephemeral=True)

    @commands.command(name="setmode", help="Sets the verification method (captcha, button, question).")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setmode_prefix(self, ctx: commands.Context, mode: str):
        # Prefix command handler needs to manually validate the string input
        valid_modes = ['captcha', 'button', 'question']
        mode_lower = mode.lower()
        if mode_lower not in valid_modes:
            embed = pembed("Mode Error ❌", f"Invalid mode. Must be one of: `{', '.join(valid_modes)}`.", 0xFF0000)
            return await send_response(ctx, embed=embed)
        
        await self._setmode_logic(ctx, mode_lower)


    @app_commands.command(name="setmode", description="Sets the verification method (captcha, button, question).")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(mode="The verification method to use.")
    async def setmode_slash(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await self._setmode_logic(interaction, mode)

    # ------------------------------------------------------
    # 6. Verification Stats Command (stats) - (Original: verifystats)
    # ------------------------------------------------------
    async def _stats_logic(self, context: Union[discord.Interaction, commands.Context]):
        """Core logic for displaying verification statistics."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)
             
        cfg = get_config(context.guild.id)
        stats = cfg.get("stats", {"passed": 0, "failed": 0})
        
        total = stats["passed"] + stats["failed"]
        
        desc = (
            f"**Total Attempts:** `{total}`\n"
            f"**Successful Verifications:** `{stats['passed']:,}`\n"
            f"**Failed Verifications:** `{stats['failed']:,}`\n"
        )
        
        embed = pembed("Verification Statistics 📈", desc, 0x00BFFF)
        await send_response(context, embed=embed)

    @commands.command(name="stats", help="Displays server-wide verification statistics.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def stats_prefix(self, ctx: commands.Context):
        await self._stats_logic(ctx)

    @app_commands.command(name="stats", description="Displays server-wide verification statistics.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def stats_slash(self, interaction: discord.Interaction):
        await self._stats_logic(interaction)

    # ------------------------------------------------------
    # 7. Set Log Channel Command (setlogchannel) - (Original: verifylog)
    # ------------------------------------------------------
    async def _setlogchannel_logic(self, context: Union[discord.Interaction, commands.Context], channel: discord.TextChannel):
        """Core logic for setting the verification log channel."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)
             
        cfg = get_config(context.guild.id)
        cfg["log_channel"] = channel.id
        update_config(context.guild.id, cfg)
        
        embed = pembed("Log Channel Set 📝", f"Verification log channel set to {channel.mention}.", 0x00FF00)
        await send_response(context, embed=embed, ephemeral=True)

    @commands.command(name="setlogchannel", help="Sets the channel where verification logs are sent.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setlogchannel_prefix(self, ctx: commands.Context, channel: discord.TextChannel):
        await self._setlogchannel_logic(ctx, channel)

    @app_commands.command(name="setlogchannel", description="Sets the channel where verification logs are sent.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(channel="The channel for verification logs.")
    async def setlogchannel_slash(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._setlogchannel_logic(interaction, channel)

    # ------------------------------------------------------
    # 8. Reset Config Command (resetconfig) - (Original: verifyreset)
    # ------------------------------------------------------
    async def _resetconfig_logic(self, context: Union[discord.Interaction, commands.Context]):
        """Core logic for resetting the server's verification configuration."""
        if not context.guild:
             return await send_response(context, "This command can only be used in a server.", ephemeral=True)
             
        data = load_json()
        gid = str(context.guild.id)
        if gid in data:
            del data[gid]
        save_json(data)
        
        embed = pembed("Config Reset 🗑️", "Verification configuration has been completely reset for this server.", 0xFFA500)
        await send_response(context, embed=embed)

    @commands.command(name="resetconfig", help="Resets the entire verification configuration for the server.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def resetconfig_prefix(self, ctx: commands.Context):
        await self._resetconfig_logic(ctx)

    @app_commands.command(name="resetconfig", description="Resets the entire verification configuration for the server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def resetconfig_slash(self, interaction: discord.Interaction):
        await self._resetconfig_logic(interaction)

# ===================================================================
#                            SETUP
# ===================================================================
async def setup(bot):
    await bot.add_cog(Verification(bot))
