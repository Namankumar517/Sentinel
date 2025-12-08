# cogs/roles.py

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Dict, Any, Optional

# --- Configuration & Styling Constants ---
COLOR_PRIMARY = 0x8A2BE2  # Neon Purple
COLOR_SECONDARY = 0x00BFFF # Electric Blue
REACTION_ROLES_FILE = 'data/reaction_roles.json'

# --- State Management Keys ---
STATE_MSG_ID = 0    # Expecting Message ID or 'new'
STATE_EMOJI = 1     # Expecting Reaction Emoji
STATE_ROLE_ID = 2   # Expecting Role ID or Mention
STATE_TITLE = 3     # Expecting New Embed Title
STATE_DESCRIPTION = 4 # Expecting New Embed Description

# --- Utility Components ---

class DataHandler:
    """Handles persistent storage for reaction roles."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._data = self._load_data()
        
    def _load_data(self) -> Dict[int, Dict[str, int]]:
        if not os.path.exists(self.file_path): return {}
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                return {int(k): v for k, v in raw_data.items()}
        except (json.JSONDecodeError, FileNotFoundError): return {}

    def _save_data(self):
        data_to_save = {str(k): v for k, v in self._data.items()}
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"Error saving reaction role data: {e}")

    @property
    def data(self) -> Dict[int, Dict[str, int]]:
        return self._data

    def add_entry(self, message_id: int, emoji: str, role_id: int):
        if message_id not in self._data:
            self._data[message_id] = {}
        self._data[message_id][emoji] = role_id
        self._save_data()

    def get_role(self, message_id: int, emoji: str) -> Optional[int]:
        return self._data.get(message_id, {}).get(emoji)
    
    def remove_entry(self, message_id: int, emoji: str) -> bool:
        if message_id in self._data and emoji in self._data[message_id]:
            del self._data[message_id][emoji]
            if not self._data[message_id]:
                del self._data[message_id]
            self._save_data()
            return True
        return False
        
    def clear_all(self):
        self._data = {}
        self._save_data()

# --- New Multi-Add View Component ---

class AddAnotherView(discord.ui.View):
    """View shown after a successful RR addition to prompt for adding another."""
    def __init__(self, cog: 'RolesCog', user_id: int, message_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.message_id = message_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button is only for the administrator who ran the setup.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Add Another Reaction to this Message', style=discord.ButtonStyle.primary, emoji='🔄')
    async def add_another(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Skips to the EMOJI step for the same message ID."""
        await interaction.response.defer(thinking=True, ephemeral=True)
        self.stop() 

        # 1. Re-initialize state, setting step to STATE_EMOJI
        self.cog.user_states[self.user_id] = {
            'step': STATE_EMOJI,
            'data': {
                'message_id': self.message_id,
                'new_message': False, 
            },
            'channel_id': interaction.channel_id,
        }
        
        # 2. Jump to the EMOJI prompt (Step 2/3)
        embed = self.cog._info_embed(
            "Step 2/3: Reaction Emoji (Continuous Add)", 
            f"Target Message ID: `{self.message_id}` confirmed. Reply with the **NEXT Emoji** you want to use (e.g., ⭐ or `<:shield:id>`)."
        )
        cancel_view = self.cog.get_cancel_view(self.user_id)
        
        try:
             # Edit the confirmation message to become the new prompt
             await interaction.edit_original_response(embed=embed, view=cancel_view)
        except:
             await interaction.followup.send(embed=embed, view=cancel_view)


    @discord.ui.button(label='Finish Setup', style=discord.ButtonStyle.success, emoji='✅')
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stops the loop and confirms completion."""
        self.stop()
        
        # Clean up the user state
        if self.user_id in self.cog.user_states:
             del self.cog.user_states[self.user_id]
             
        embed = self.cog._success_embed("Configuration Complete", f"Finished adding reaction roles to message ID `{self.message_id}`.")
        await interaction.response.edit_message(embed=embed, view=None)

# --- Advanced View Components ---

class PaginationView(discord.ui.View):
    """View for handling pagination in the List Reaction Roles command."""
    def __init__(self, embeds: list[discord.Embed], user: discord.User, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self.max_pages = len(embeds)
        self.user = user # Only the original user can interact
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.user:
            await interaction.response.send_message("This interaction is only for the command issuer.", ephemeral=True)
            return False
        return True

    def _update_buttons(self):
        if self.max_pages == 1:
            self.children[0].disabled = True
            self.children[2].disabled = True
        else:
            self.children[0].disabled = self.current_page == 0 # Previous button
            self.children[2].disabled = self.current_page == self.max_pages - 1 # Next button
        self.children[1].label = f"Page {self.current_page + 1}/{self.max_pages}" # Indicator

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.primary, disabled=True, row=0)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Indicator is disabled, no action needed
        await interaction.response.defer() 

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

class ClearAllConfirmationView(discord.ui.View):
    """View for confirming the removal of ALL reaction roles."""
    def __init__(self, cog: 'RolesCog', original_interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.cog = cog
        self.original_interaction = original_interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.original_interaction.user:
            await interaction.response.send_message("Only the command issuer can confirm this action.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label='Confirm Clear All', style=discord.ButtonStyle.danger, emoji='💥')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.data_handler.clear_all()
        self.stop()
        
        embed = self.cog._success_embed("🚨 Database Wiped", "All reaction role configurations have been successfully removed.")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.secondary, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        embed = self.cog._info_embed("Cancellation", "Database wipe operation canceled.")
        await interaction.response.edit_message(embed=embed, view=None)
        
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.original_interaction.edit_original_response(view=self)
        except:
            pass 

class SetupPanel(discord.ui.View):
    """The main interactive dashboard for the /roles command."""
    
    def __init__(self, cog: 'RolesCog'):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label='Add Reaction Role', style=discord.ButtonStyle.primary, emoji='➕', row=0)
    async def add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Triggers the step-by-step interactive message dialog."""
        
        if interaction.user.id in self.cog.user_states:
            embed = self.cog._error_embed("Setup in Progress", "You are already in a configuration process. Please complete or cancel the previous one.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Initialize the state for the user
        self.cog.user_states[interaction.user.id] = {
            'step': STATE_MSG_ID,
            'data': {},
            'channel_id': interaction.channel_id,
        }
        
        # Start the dialog - Step 1
        embed = self.cog._info_embed(
            "Step 1/5: Target Message",
            (
                "Please send the **Message ID** of the message you want to use in this channel."
                "\n\n**To create a new, custom message**, reply with `new`."
            )
        )
        
        cancel_view = self.cog.get_cancel_view(interaction.user.id)
        
        await interaction.response.send_message(embed=embed, ephemeral=True, view=cancel_view)


    @discord.ui.button(label='Remove Single Entry', style=discord.ButtonStyle.danger, emoji='➖', row=0)
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shows the dropdown selection view for removal."""
        remove_view = self.cog.get_remove_role_view()
        if not remove_view:
             embed = self.cog._error_embed("Deletion Error", "No active reaction roles found to remove.")
             await interaction.response.send_message(embed=embed, ephemeral=True)
             return
             
        embed = self.cog._info_embed(
            "⚡ Select Role to Remove",
            "Choose an existing Message ID/Emoji mapping from the dropdown menu to permanently remove it."
        )
        await interaction.response.send_message(embed=embed, view=remove_view, ephemeral=True)

    @discord.ui.button(label='List All Configurations', style=discord.ButtonStyle.secondary, emoji='📋', row=1)
    async def list_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shows a list of all currently configured reaction roles with pagination."""
        embeds = self.cog.create_list_embeds(interaction)
        
        if not embeds:
            embed = self.cog._error_embed("List Error", "No reaction roles found.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = PaginationView(embeds, interaction.user)
        await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)
        
    @discord.ui.button(label='WIPE ALL MAPPINGS', style=discord.ButtonStyle.danger, emoji='💣', row=1)
    async def clear_all_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Prompts for confirmation to clear ALL reaction role data."""
        if not self.cog.data_handler.data:
            embed = self.cog._error_embed("Error", "The database is already empty.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        embed = self.cog._error_embed(
            "⚠️ CONFIRMATION REQUIRED: WIPE DATABASE",
            "**This action is irreversible.** Are you sure you want to delete **ALL** reaction role configurations from Sentinel?"
        )
        await interaction.response.send_message(embed=embed, view=ClearAllConfirmationView(self.cog, interaction), ephemeral=True)

class RolesCog(commands.Cog):
    """Sentinel's Reaction Roles Module."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_handler = DataHandler(REACTION_ROLES_FILE)
        # Temporary storage for multi-step configuration
        self.user_states: Dict[int, Dict[str, Any]] = {} 

    # --- Helper Functions for Consistent UI ---
    
    def _error_embed(self, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(title=f"⚠️ {title}", description=description, color=0xFF0000)
        return embed

    def _success_embed(self, description: str, title: str = "Operation Successful") -> discord.Embed:
        embed = discord.Embed(title=f"✅ {title}", description=description, color=COLOR_SECONDARY)
        return embed

    def _info_embed(self, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(title=f"✨ {title}", description=description, color=COLOR_PRIMARY)
        return embed

    def _create_setup_embed(self, user: discord.User) -> discord.Embed:
        """Creates the premium-styled main setup dashboard embed."""
        embed = discord.Embed(
            title="⚙️ Sentinel Setup Panel: Reaction Roles",
            description=(
                "**Welcome, Admin!** Use the buttons below to manage the **Reaction Roles System**."
            ),
            color=COLOR_PRIMARY
        )
        embed.add_field(name="⚡ System Status", value="**ONLINE**", inline=True)
        embed.add_field(name="🛡️ Mapped Messages", value=f"`{len(self.data_handler.data)}`", inline=True)
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Cyber Protocol Engaged | Sentinel v1.1 | All operations are logged.")
        return embed
        
    def get_cancel_view(self, user_id: int) -> discord.ui.View:
        """Helper to create a simple cancel view for the dialog."""
        cancel_view = discord.ui.View(timeout=180)
        cancel_view.add_item(discord.ui.Button(label="Cancel Setup", style=discord.ButtonStyle.danger, custom_id=f"rr_cancel_{user_id}"))
        return cancel_view
        
    def create_list_embeds(self, interaction: discord.Interaction) -> list[discord.Embed]:
        """Creates a list of embeds for pagination."""
        all_data = self.data_handler.data
        if not all_data:
            return []

        # Convert data into a list of strings (entries)
        entries = []
        for msg_id, mappings in all_data.items():
            for emoji, role_id in mappings.items():
                role = interaction.guild.get_role(role_id) if interaction.guild else None
                role_mention = role.mention if role else f"Unknown Role ID: `{role_id}`"
                entries.append(f"• **Msg ID:** `{msg_id}`\n  `{emoji}` → {role_mention}")

        # Split entries into pages (max 5 entries per field, max 3 fields per embed)
        MAX_ENTRIES_PER_PAGE = 15
        paged_entries = [entries[i:i + MAX_ENTRIES_PER_PAGE] for i in range(0, len(entries), MAX_ENTRIES_PER_PAGE)]
        
        embeds = []
        for i, page_entries in enumerate(paged_entries):
            embed = self._info_embed(
                f"📋 Active Configurations (Page {i+1}/{len(paged_entries)})",
                "Below is the current list of all message-emoji-role mappings."
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            
            # Combine entries into a single description or multiple fields
            embed.description = "\n\n".join(page_entries)
            
            embeds.append(embed)
            
        return embeds

    # --- Commands (Prefix & Slash) ---

    @commands.command(name="roles", help="Opens the Sentinel administrative dashboard.")
    @commands.has_permissions(administrator=True)
    async def roles_prefix(self, ctx: commands.Context):
        """The single global command that opens the interactive button dashboard (Prefix Version)."""
        embed = self._create_setup_embed(ctx.author)
        await ctx.send(embed=embed, view=SetupPanel(self))
    
    @app_commands.command(name="roles", description="Opens the Sentinel administrative dashboard.")
    @app_commands.checks.has_permissions(administrator=True)
    async def roles_slash(self, interaction: discord.Interaction):
        """The single global command that opens the interactive button dashboard (Slash Version)."""
        
        embed = self._create_setup_embed(interaction.user)
        await interaction.response.send_message(
            embed=embed, 
            view=SetupPanel(self), 
            ephemeral=True
        )

    # --- Dialog Listener (UPDATED LOGIC) ---
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for user input during the step-by-step setup process."""
        user_id = message.author.id
        
        if message.author.bot or not message.guild or user_id not in self.user_states:
            return

        state = self.user_states[user_id]
        if message.channel.id != state['channel_id']:
            return

        current_step = state['step']
        content = message.content.strip()
        
        # Helper for next step
        async def send_next_step(step, title, text):
            state['step'] = step
            await message.channel.send(embed=self._info_embed(title, text), view=self.get_cancel_view(user_id), delete_after=60)
        
        # Clean up the input message
        try: await message.delete() 
        except discord.Forbidden: pass

        # --- Step 1: Get Message ID (STATE_MSG_ID) ---
        if current_step == STATE_MSG_ID:
            
            if content.lower() == 'new':
                # **NEW MESSAGE FLOW** - Ask for Title first
                state['data']['new_message'] = True
                await send_next_step(
                    STATE_TITLE, 
                    "Step 2/5: Embed Title", 
                    "You chose to create a new message. Reply with the **Title** you want for the reaction role embed (e.g., 'Get Your Roles Here')."
                )
            else:
                # **EXISTING MESSAGE FLOW**
                try:
                    msg_id = int(content)
                    await message.channel.fetch_message(msg_id) # Validate existence
                    state['data']['message_id'] = msg_id
                    state['data']['new_message'] = False
                    
                    await send_next_step(
                        STATE_EMOJI, 
                        "Step 2/3: Reaction Emoji", 
                        f"Target Message ID: `{msg_id}` confirmed. Reply with the **Emoji** you want to use (e.g., 👍 or `<:name:id>`)."
                    )
                except ValueError:
                    await message.channel.send(embed=self._error_embed("Invalid Message ID", "Please reply with a valid numeric Message ID or 'new'."), delete_after=10)
                except (discord.NotFound, discord.Forbidden):
                    await message.channel.send(embed=self._error_embed("Message Error", "Could not find or access that message in this channel. Check the ID."), delete_after=10)
            
        # --- Step 2: Get New Title (STATE_TITLE) ---
        elif current_step == STATE_TITLE:
            state['data']['title'] = content
            await send_next_step(
                STATE_DESCRIPTION, 
                "Step 3/5: Embed Description", 
                f"Title: `{content}` confirmed. Reply with the **Description** for the reaction role embed."
            )
            
        # --- Step 3: Get New Description (STATE_DESCRIPTION) ---
        elif current_step == STATE_DESCRIPTION:
            state['data']['description'] = content
            
            # Now send the message and get its ID
            temp_embed = discord.Embed(
                title=state['data']['title'], 
                description=state['data']['description'], 
                color=COLOR_SECONDARY
            )
            try:
                new_msg = await message.channel.send(embed=temp_embed)
                state['data']['message_id'] = new_msg.id
            except discord.Forbidden:
                await message.channel.send(embed=self._error_embed("Permission Error", "Sentinel cannot send messages in this channel."), delete_after=10)
                del self.user_states[user_id]
                return
                
            await send_next_step(
                STATE_EMOJI, 
                "Step 4/5: Reaction Emoji", 
                f"New Message ID: `{new_msg.id}` created. Reply with the **Emoji** you want to use (e.g., 👍 or `<:name:id>`)."
            )
            
        # --- Step 4/2: Get Emoji (STATE_EMOJI) ---
        elif current_step == STATE_EMOJI:
            state['data']['emoji'] = content
            
            step_num = '5/5' if state['data'].get('new_message') else '3/3'
            await send_next_step(
                STATE_ROLE_ID, 
                f"Step {step_num}: Role Assignment", 
                f"Emoji: `{content}` confirmed. Reply with the **Role ID or Mention** you want to assign to this reaction.",
            )
            
        # --- Step 5/3: Get Role ID (STATE_ROLE_ID) & Finalize ---
        elif current_step == STATE_ROLE_ID:
            
            msg_id = state['data']['message_id']
            emoji_raw = state['data']['emoji']
            role_input = content.replace('<@&', '').replace('>', '')
            
            try:
                role_id = int(role_input)
            except ValueError:
                await message.channel.send(embed=self._error_embed("Invalid Role Input", "The role input must be a valid ID or a mention."), delete_after=10)
                return

            # Role Validation
            guild = message.guild
            role = guild.get_role(role_id)
            
            if not role:
                await message.channel.send(embed=self._error_embed("Role Not Found", f"Could not find a role with ID `{role_id}`."), delete_after=10)
                return
            if role >= guild.me.top_role:
                 await message.channel.send(embed=self._error_embed("Permission Error", "Sentinel cannot manage a role that is equal to or higher than its own highest role."), delete_after=10)
                 return

            # --- FINALIZATION: React and Save ---
            try:
                target_message = await message.channel.fetch_message(msg_id)
                await target_message.add_reaction(emoji_raw)
                
            except discord.HTTPException as e:
                await message.channel.send(embed=self._error_embed("Reaction Error", f"Could not react with the input `{emoji_raw}`. Ensure it is a valid emoji. Error: `{e}`"), delete_after=15)
                del self.user_states[user_id]
                return
            
            except discord.NotFound:
                await message.channel.send(embed=self._error_embed("Message Deleted", f"The target message `{msg_id}` was deleted during the setup."), delete_after=10)
                del self.user_states[user_id]
                return
            
            # Save Data
            self.data_handler.add_entry(msg_id, emoji_raw, role_id)
            
            # **Set temporary state to prevent new messages from interfering**
            self.user_states[user_id]['step'] = -1 
            
            # Confirmation with Loop Button
            embed = self._success_embed(
                "🛡️ Reaction Role Added Successfully",
                f"**1.** Sentinel is now monitoring **Message ID: `{msg_id}`** for **`{emoji_raw}`** to assign {role.mention}.\n\n"
                f"Click **'Add Another Reaction...'** to configure more roles on this same message ID."
            )
            # Send the confirmation message with the loop view
            await message.channel.send(embed=embed, view=AddAnotherView(self, user_id, msg_id))

        else:
            # Ignore messages when state is -1 (waiting for button click)
            pass
            
    # --- Interaction Listeners ---
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handles the Cancel button interaction."""
        custom_id = interaction.data.get('custom_id', '')

        # 1. Handle Cancel Button
        if custom_id.startswith('rr_cancel_'):
            user_id = int(custom_id.split('_')[-1])
            
            if interaction.user.id != user_id:
                await interaction.response.send_message(self._error_embed("Unauthorized Access", "You can only cancel your own setup process."), ephemeral=True)
                return
                
            if user_id in self.user_states:
                del self.user_states[user_id]
                await interaction.response.edit_message(embed=self._info_embed("Setup Canceled", "The reaction role configuration has been aborted."), view=None)
                
        # 2. Handle RemoveRoleSelect (Callback is defined inside get_remove_role_view)

        
    # --- Existing Reaction Event Listeners (on_raw_reaction_add/remove) ---

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id: return
        emoji_str = str(payload.emoji)
        role_id = self.data_handler.get_role(payload.message_id, emoji_str)
        if not role_id: return 

        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return

        member = guild.get_member(payload.user_id)
        if not member:
            try: member = await guild.fetch_member(payload.user_id)
            except discord.NotFound: return

        role = guild.get_role(role_id)
        if not role or role >= guild.me.top_role: return

        if role not in member.roles:
            try: await member.add_roles(role, reason="Sentinel Reaction Role Assignment")
            except Exception as e: print(f"Error giving role: {e}")
                
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id: return
        emoji_str = str(payload.emoji)
        role_id = self.data_handler.get_role(payload.message_id, emoji_str)
        if not role_id: return 

        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return

        member = guild.get_member(payload.user_id)
        if not member:
            try: member = await guild.fetch_member(payload.user_id)
            except discord.NotFound: return
            
        role = guild.get_role(role_id)
        if not role or role >= guild.me.top_role: return

        if role in member.roles:
            try: await member.remove_roles(role, reason="Sentinel Reaction Role Removal")
            except Exception as e: print(f"Error removing role: {e}")


    # --- Helper for RemoveRoleView ---
    
    def get_remove_role_view(self) -> Optional[discord.ui.View]:
        """Dynamically creates the View/Select for removing entries, returns None if empty."""
        
        class RemoveRoleSelect(discord.ui.Select):
            def __init__(self, options, handler, cog_ref):
                super().__init__(
                    placeholder='Select a reaction role entry to remove...', 
                    custom_id='remove_role_select', 
                    min_values=1, max_values=1, options=options, row=0
                )
                self.data_handler = handler
                self.cog = cog_ref
                
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer(thinking=True, ephemeral=True)
                msg_id_str, emoji = self.values[0].split(':', 1)
                msg_id = int(msg_id_str)

                role_id = self.data_handler.get_role(msg_id, emoji)
                
                if self.data_handler.remove_entry(msg_id, emoji):
                    guild = interaction.guild
                    role_mention = guild.get_role(role_id).mention if guild and role_id and guild.get_role(role_id) else f"Role ID: `{role_id}`"
                    
                    embed = self.cog._success_embed("🔥 Reaction Role Removed", f"The mapping **{emoji}** on **{msg_id}** for {role_mention} has been deleted.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                
                updated_view = self.cog.get_remove_role_view()
                if updated_view:
                    await self.view.message.edit(view=updated_view)
                else:
                    embed = self.cog._success_embed("Configuration Cleared", "The last reaction role entry was removed. This panel is now disabled.")
                    await self.view.message.edit(embed=embed, view=None)


        class DynamicRemoveRoleView(discord.ui.View):
            def __init__(self, handler, cog_ref):
                super().__init__(timeout=180)
                self.data_handler = handler
                self.cog = cog_ref
                self._add_select()
            
            def _add_select(self):
                self.clear_items()
                options = []
                for msg_id, mappings in self.data_handler.data.items():
                    for emoji, role_id in mappings.items():
                        value = f"{msg_id}:{emoji}"
                        label = f"Msg:{msg_id} | {emoji}"
                        options.append(discord.SelectOption(label=label[:100], value=value))
                        if len(options) >= 25: break 
                    if len(options) >= 25: break
                
                if options:
                    self.add_item(RemoveRoleSelect(options, self.data_handler, self.cog))
                else:
                    self.add_item(discord.ui.Button(label="No Roles to Remove", style=discord.ButtonStyle.secondary, disabled=True))
                    
        if any(self.data_handler.data):
            return DynamicRemoveRoleView(self.data_handler, self)
        else:
            return None


# Mandatory setup function for Cogs
async def setup(bot: commands.Bot):
    """Adds the RolesCog to the bot."""
    await bot.add_cog(RolesCog(bot))
