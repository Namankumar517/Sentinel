import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
import asyncio
import random
import datetime
from datetime import timedelta
import string
from typing import Union, cast, Literal

# ----------------- GIVEAWAY VIEW (FOR BUTTONS) -----------------
class GiveawayView(View):
    def __init__(self, cog, duration_seconds: int, role_id: int = None):
        """
        A view for the giveaway, handling the join button.
        """
        # Set timeout slightly longer than duration to allow for latency
        super().__init__(timeout=duration_seconds + 300) 
        self.cog = cog
        self.role_id = role_id

    @discord.ui.button(label="Join (0 Entries)", style=discord.ButtonStyle.primary, custom_id="join_giveaway", emoji="🎉")
    async def join_button(self, interaction: discord.Interaction, button: Button):
        # Find the giveaway in the memory dictionary
        giveaway = self.cog.active_giveaways.get(interaction.message.id)

        # 1. Check if giveaway exists in memory (handled active state)
        if not giveaway:
            await interaction.response.send_message("This giveaway has ended or the bot was restarted.", ephemeral=True)
            return

        user_id = interaction.user.id
        
        # 2. Check if user already entered
        if user_id in giveaway["entries"]:
            await interaction.response.send_message("You have already entered this giveaway.", ephemeral=True)
            return

        # 3. Check for required role
        if self.role_id:
            # Need to fetch member object to check roles
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                # Should not happen in a guild context, but safe check
                await interaction.response.send_message("Could not check your roles. Try again.", ephemeral=True)
                return

            role = interaction.guild.get_role(self.role_id)
            if not role:
                # Role was deleted after giveaway started
                pass 
            elif role not in member.roles:
                await interaction.response.send_message(f"You need the {role.mention} role to enter this giveaway.", ephemeral=True)
                return

        # 4. Add user to entries
        giveaway["entries"].append(user_id)
        
        # 5. Update button label to show new count
        button.label = f"Join ({len(giveaway['entries'])} Entries)"
        await interaction.message.edit(view=self)

        # 6. Confirm entry to user
        await interaction.response.send_message("You have successfully entered the giveaway!", ephemeral=True)


class Giveaways(commands.Cog):
    """Premium Giveaways & Events Commands"""
    def __init__(self, bot):
        self.bot = bot
        # Active giveaways: {message_id: {data}}
        # Note: Data is lost on bot restart unless a database is implemented.
        self.active_giveaways = {} 
        # Ended giveaways (for reroll): {message_id: {data}}
        self.ended_giveaways = {}

    # ----------------- EMBED HELPERS (PRO LEVEL) -----------------
    
    def _create_embed(self, title: str, description: str, color=discord.Color.gold()):
        """Base embed creator for a consistent 'pro' look."""
        embed = discord.Embed(
            title=f"🎁 {title}",
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        return embed

    def _create_start_embed(self, host: discord.Member, prize: str, ends_at: datetime.datetime, winners: int, giveaway_id: str, role: discord.Role = None):
        embed = self._create_embed(
            "New Giveaway Started!",
            f"React with the button below to enter!\n**Prize:** {prize}"
        )
        embed.add_field(name="🏆 Winners", value=str(winners), inline=True)
        embed.add_field(name="⏰ Ends At", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        embed.add_field(name="👤 Hosted By", value=host.mention, inline=False)
        if role:
            embed.add_field(name="🔒 Role Required", value=role.mention, inline=False)
        
        # Using a generic gift icon
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/4213/4213958.png") 
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        return embed

    def _create_end_embed(self, prize: str, winner_text: str, giveaway_id: str):
        embed = self._create_embed(
            "Giveaway Ended",
            f"**Prize:** {prize}",
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="🏆 Winners", value=winner_text, inline=False)
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/7486/7486744.png") # Party popper
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        return embed

    def _create_reroll_embed(self, prize: str, winner_text: str, giveaway_id: str):
        embed = self._create_embed(
            "Giveaway Reroll",
            f"**Prize:** {prize}",
            color=discord.Color.blue()
        )
        embed.add_field(name="🎉 New Winners", value=winner_text, inline=False)
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        return embed

    def _create_info_embed(self, title: str, description: str):
        embed = self._create_embed(title, description, color=discord.Color.blurple())
        embed.set_footer(text="Giveaways | Command Info")
        return embed

    def _create_error_embed(self, title: str, description: str):
        embed = self._create_embed(f"❌ {title}", description, color=discord.Color.red())
        embed.set_footer(text="Giveaways | Error")
        return embed

    # ----------------- HELPER FUNCTIONS -----------------
    def _generate_giveaway_id(self):
        """Generates a random 8-character ID."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # ----------------- UNIFIED START GIVEAWAY HANDLER -----------------
    async def _start_giveaway_handler(self, source: Union[discord.Interaction, commands.Context], channel: discord.TextChannel, prize: str, time: int, winners: int, role: discord.Role = None):
        
        if isinstance(source, commands.Context):
            ctx = source
            user = ctx.author
            
            def respond_error(embed): return ctx.reply(embed=embed)
            def respond_success(embed): return ctx.reply(embed=embed)
        else: # discord.Interaction
            interaction = source
            user = interaction.user
            await interaction.response.defer(ephemeral=True)

            def respond_error(embed): return interaction.followup.send(embed=embed, ephemeral=True)
            def respond_success(embed): return interaction.followup.send(embed=embed, ephemeral=True)
            
        # Permission check
        if not user.guild_permissions.manage_guild:
            await respond_error(
                embed=self._create_error_embed("Permission Denied", "You do not have permission to start giveaways.")
            )
            return

        giveaway_id = self._generate_giveaway_id()
        # Use discord.utils.utcnow() for timezone awareness
        ends_at = discord.utils.utcnow() + timedelta(minutes=time)
        duration_seconds = time * 60

        embed = self._create_start_embed(user, prize, ends_at, winners, giveaway_id, role)
        view = GiveawayView(cog=self, duration_seconds=duration_seconds, role_id=role.id if role else None)

        try:
            giveaway_msg = await channel.send(embed=embed, view=view)
        except Exception as e:
            await respond_error(
                embed=self._create_error_embed("Failed to Start", f"Could not send message to {channel.mention}.\n`{e}`")
            )
            return

        # Store giveaway data
        self.active_giveaways[giveaway_msg.id] = {
            "gid": giveaway_id,
            "channel_id": channel.id,
            "prize": prize,
            "winners": winners,
            "entries": [], 
            "ends_at": ends_at,
            "role_id": role.id if role else None,
            "host_id": user.id
        }

        # Success message
        await respond_success(
            embed=self._create_info_embed("Giveaway Created", f"Your giveaway has been started in {channel.mention}.\nID: `{giveaway_id}`")
        )

        # Start the background timer task
        asyncio.create_task(self._end_giveaway(giveaway_msg.id, duration_seconds))


    # ----------------- START GIVEAWAY (PREFIX COMMANDS) -----------------
    @commands.command(name="giveaway", description="Start a giveaway")
    @commands.has_permissions(manage_guild=True)
    async def giveaway_prefix(self, ctx: commands.Context, channel: discord.TextChannel, prize: str, time: int, winners: int = 1):
        """!giveaway #channel "Prize Name" 10 1"""
        await self._start_giveaway_handler(ctx, channel, prize, time, winners, role=None)
        
    @commands.command(name="giveawayrole", description="Start a giveaway restricted to a specific role")
    @commands.has_permissions(manage_guild=True)
    async def giveawayrole_prefix(self, ctx: commands.Context, channel: discord.TextChannel, prize: str, time: int, winners: int, role: discord.Role):
        """!giveawayrole #channel "Prize Name" 10 1 @Role"""
        await self._start_giveaway_handler(ctx, channel, prize, time, winners, role=role)

    # ----------------- START GIVEAWAY (SLASH COMMANDS) -----------------
    @app_commands.command(name="giveaway", description="Start a giveaway")
    @app_commands.describe(channel="Channel to host giveaway", prize="Prize", time="Duration in minutes", winners="Number of winners")
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway(self, interaction: discord.Interaction, channel: discord.TextChannel, prize: str, time: int, winners: int = 1):
        await self._start_giveaway_handler(interaction, channel, prize, time, winners, role=None)
        
    @app_commands.command(name="giveawayrole", description="Start a giveaway restricted to a specific role")
    @app_commands.describe(channel="Channel to host giveaway", prize="Prize", time="Duration (minutes)", winners="Number of winners", role="Role required to join")
    @app_commands.default_permissions(manage_guild=True)
    async def giveawayrole(self, interaction: discord.Interaction, channel: discord.TextChannel, prize: str, time: int, winners: int, role: discord.Role):
        await self._start_giveaway_handler(interaction, channel, prize, time, winners, role=role)

    # ----------------- INTERNAL END GIVEAWAY -----------------
    async def _end_giveaway(self, message_id: int, duration: int):
        # Wait for the duration of the giveaway
        if duration > 0:
            await asyncio.sleep(duration)
        
        # Retrieve and remove from active list
        giveaway = self.active_giveaways.pop(message_id, None)
        if not giveaway:
            # If not found, it was likely cancelled manually via gcancel
            return

        channel = self.bot.get_channel(giveaway["channel_id"])
        if not channel:
            return

        all_entries = giveaway["entries"]
        
        # Select winners
        if not all_entries:
            winner_text = "No participants."
            winner_ids = []
        else:
            # Ensure we don't try to pick more winners than entries
            count = min(giveaway["winners"], len(all_entries))
            winner_ids = random.sample(all_entries, count)
            winner_text = ", ".join(f"<@{uid}>" for uid in winner_ids)
        
        embed = self._create_end_embed(giveaway["prize"], winner_text, giveaway["gid"])
        
        try:
            # Ping winners in the channel
            await channel.send(content=f"Congratulations {winner_text}!" if winner_ids else "The giveaway ended with no participants.", embed=embed)
        except Exception:
            pass

        # Disable the button on the original message
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(view=None)
        except Exception:
            pass

        # Store ended giveaway for rerolling
        self.ended_giveaways[message_id] = {
            "all_entries": all_entries,
            "prize": giveaway["prize"],
            "winners_count": giveaway["winners"],
            "gid": giveaway["gid"]
        }

    # ----------------- REROLL (PREFIX COMMAND) -----------------
    @commands.command(name="reroll", description="Reroll a giveaway winner (must have ended)")
    @commands.has_permissions(manage_guild=True)
    async def reroll_prefix(self, ctx: commands.Context, message_id: str):
        # Convert message_id to int, handling potential input errors
        try:
            m_id = int(message_id)
        except ValueError:
             await ctx.reply("Please provide a valid numeric Message ID.")
             return

        ended_giveaway = self.ended_giveaways.get(m_id)
        if not ended_giveaway:
            await ctx.reply(
                embed=self._create_error_embed("Not Found", "Giveaway not found in recent history.\n(Data is cleared on bot restart)")
            )
            return

        all_entries = ended_giveaway["all_entries"]
        if not all_entries:
            await ctx.reply(embed=self._create_info_embed("No Participants", "Cannot reroll; 0 entries."))
            return
            
        new_winner_ids = random.sample(all_entries, min(ended_giveaway["winners_count"], len(all_entries)))
        winner_text = ", ".join(f"<@{uid}>" for uid in new_winner_ids)
        
        embed = self._create_reroll_embed(ended_giveaway["prize"], winner_text, ended_giveaway["gid"])
        
        # Send reroll message to the channel where command was executed
        await ctx.send(content=f"🎉 **Reroll!** {winner_text}", embed=embed)
        # Confirmation message
        await ctx.reply(embed=self._create_info_embed("Reroll Successful", "Winners have been rerolled."))

    # ----------------- REROLL (SLASH COMMAND) -----------------
    @app_commands.command(name="reroll", description="Reroll a giveaway winner (must have ended)")
    @app_commands.describe(message_id="ID of the giveaway message that ended")
    @app_commands.default_permissions(manage_guild=True)
    async def reroll(self, interaction: discord.Interaction, message_id: str):
        # Convert message_id to int, handling potential input errors
        try:
            m_id = int(message_id)
        except ValueError:
             await interaction.response.send_message("Please provide a valid numeric Message ID.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True)

        ended_giveaway = self.ended_giveaways.get(m_id)
        if not ended_giveaway:
            await interaction.followup.send(
                embed=self._create_error_embed("Not Found", "Giveaway not found in recent history.\n(Data is cleared on bot restart)"),
                ephemeral=True
            )
            return

        all_entries = ended_giveaway["all_entries"]
        if not all_entries:
            await interaction.followup.send(embed=self._create_info_embed("No Participants", "Cannot reroll; 0 entries."), ephemeral=True)
            return
            
        new_winner_ids = random.sample(all_entries, min(ended_giveaway["winners_count"], len(all_entries)))
        winner_text = ", ".join(f"<@{uid}>" for uid in new_winner_ids)
        
        embed = self._create_reroll_embed(ended_giveaway["prize"], winner_text, ended_giveaway["gid"])
        
        # Send reroll message to the channel where interaction occurred
        await interaction.channel.send(content=f"🎉 **Reroll!** {winner_text}", embed=embed)
        await interaction.followup.send(embed=self._create_info_embed("Reroll Successful", "Winners have been rerolled."), ephemeral=True)

    # ----------------- LIST ACTIVE GIVEAWAYS (PREFIX COMMAND) -----------------
    @commands.command(name="glist", description="List all active giveaways")
    @commands.has_permissions(manage_guild=True)
    async def glist_prefix(self, ctx: commands.Context):
        if not self.active_giveaways:
            await ctx.reply(embed=self._create_info_embed("No Active Giveaways", "There are currently no active giveaways."))
            return

        embed = self._create_info_embed("Active Giveaways", "Here is a list of all running giveaways:")
        
        for mid, data in self.active_giveaways.items():
            remaining = data["ends_at"] - discord.utils.utcnow()
            # Ensure remaining is not negative before calculating minutes
            remaining_seconds = remaining.total_seconds() if remaining.total_seconds() > 0 else 0
            mins = int(remaining_seconds // 60)
            channel = self.bot.get_channel(data['channel_id'])
            
            field_name = f"🎁 {data['prize']} (ID: {data['gid']})"
            field_value = (
                f"Ends in: `{mins}` minutes (<t:{int(data['ends_at'].timestamp())}:R>)\n"
                f"Channel: {channel.mention if channel else 'Unknown'}\n"
                f"[Jump to Giveaway](https://discord.com/channels/{ctx.guild.id}/{data['channel_id']}/{mid})"
            )
            embed.add_field(name=field_name, value=field_value, inline=False)
            
        await ctx.reply(embed=embed)

    # ----------------- LIST ACTIVE GIVEAWAYS (SLASH COMMAND) -----------------
    @app_commands.command(name="glist", description="List all active giveaways")
    @app_commands.default_permissions(manage_guild=True)
    async def glist(self, interaction: discord.Interaction):
        if not self.active_giveaways:
            await interaction.response.send_message(embed=self._create_info_embed("No Active Giveaways", "There are currently no active giveaways."), ephemeral=True)
            return

        embed = self._create_info_embed("Active Giveaways", "Here is a list of all running giveaways:")
        
        for mid, data in self.active_giveaways.items():
            remaining = data["ends_at"] - discord.utils.utcnow()
            # Ensure remaining is not negative before calculating minutes
            remaining_seconds = remaining.total_seconds() if remaining.total_seconds() > 0 else 0
            mins = int(remaining_seconds // 60)
            channel = self.bot.get_channel(data['channel_id'])
            
            field_name = f"🎁 {data['prize']} (ID: {data['gid']})"
            field_value = (
                f"Ends in: `{mins}` minutes (<t:{int(data['ends_at'].timestamp())}:R>)\n"
                f"Channel: {channel.mention if channel else 'Unknown'}\n"
                f"[Jump to Giveaway](https://discord.com/channels/{interaction.guild_id}/{data['channel_id']}/{mid})"
            )
            embed.add_field(name=field_name, value=field_value, inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ----------------- CANCEL GIVEAWAY (PREFIX COMMAND) -----------------
    @commands.command(name="gcancel", description="Cancel an ongoing giveaway")
    @commands.has_permissions(manage_guild=True)
    async def gcancel_prefix(self, ctx: commands.Context, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await ctx.reply("Invalid ID.")
             return

        giveaway = self.active_giveaways.pop(m_id, None)
        if not giveaway:
            await ctx.reply(embed=self._create_error_embed("Not Found", "No active giveaway found with that ID."))
            return

        # Disable button on original message
        channel = self.bot.get_channel(giveaway["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(m_id)
                await msg.edit(view=None)
                await channel.send(embed=self._create_embed("Giveaway Cancelled", f"**Prize:** {giveaway['prize']}\n**Cancelled by:** {ctx.author.mention}", discord.Color.orange()))
            except Exception:
                pass
        
        await ctx.reply(embed=self._create_info_embed("Cancelled", "The giveaway has been cancelled successfully."))

    # ----------------- CANCEL GIVEAWAY (SLASH COMMAND) -----------------
    @app_commands.command(name="gcancel", description="Cancel an ongoing giveaway")
    @app_commands.describe(message_id="The message ID of the giveaway to cancel")
    @app_commands.default_permissions(manage_guild=True)
    async def gcancel(self, interaction: discord.Interaction, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await interaction.response.send_message("Invalid ID.", ephemeral=True)
             return
        
        await interaction.response.defer(ephemeral=True)

        giveaway = self.active_giveaways.pop(m_id, None)
        if not giveaway:
            await interaction.followup.send(embed=self._create_error_embed("Not Found", "No active giveaway found with that ID."), ephemeral=True)
            return

        # Disable button on original message
        channel = self.bot.get_channel(giveaway["channel_id"])
        if channel:
            try:
                msg = await channel.fetch_message(m_id)
                await msg.edit(view=None)
                await channel.send(embed=self._create_embed("Giveaway Cancelled", f"**Prize:** {giveaway['prize']}\n**Cancelled by:** {interaction.user.mention}", discord.Color.orange()))
            except Exception:
                pass
        
        await interaction.followup.send(embed=self._create_info_embed("Cancelled", "The giveaway has been cancelled successfully."), ephemeral=True)

    # ----------------- END GIVEAWAY MANUALLY (PREFIX COMMAND) -----------------
    @commands.command(name="gend", description="Manually end a giveaway early")
    @commands.has_permissions(manage_guild=True)
    async def gend_prefix(self, ctx: commands.Context, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await ctx.reply("Invalid ID.")
             return

        if m_id not in self.active_giveaways:
            await ctx.reply(embed=self._create_error_embed("Not Found", "No active giveaway found for that ID."))
            return

        # Call internal end function with 0 duration to trigger immediate end
        asyncio.create_task(self._end_giveaway(m_id, 0))
        
        await ctx.reply(embed=self._create_info_embed("Giveaway Ended", "The giveaway is being ended now."))

    # ----------------- END GIVEAWAY MANUALLY (SLASH COMMAND) -----------------
    @app_commands.command(name="gend", description="Manually end a giveaway early")
    @app_commands.describe(message_id="The message ID of the giveaway to end")
    @app_commands.default_permissions(manage_guild=True)
    async def gend(self, interaction: discord.Interaction, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await interaction.response.send_message("Invalid ID.", ephemeral=True)
             return
        
        await interaction.response.defer(ephemeral=True)

        if m_id not in self.active_giveaways:
            await interaction.followup.send(embed=self._create_error_embed("Not Found", "No active giveaway found for that ID."), ephemeral=True)
            return

        # Call internal end function with 0 duration to trigger immediate end
        # We start it as a task so we don't block the interaction response
        asyncio.create_task(self._end_giveaway(m_id, 0))
        
        await interaction.followup.send(embed=self._create_info_embed("Giveaway Ended", "The giveaway is being ended now."), ephemeral=True)

    # ----------------- CHECK ENTRIES (PREFIX COMMAND) -----------------
    @commands.command(name="gentries", description="Check number of entries in a giveaway")
    async def gentries_prefix(self, ctx: commands.Context, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await ctx.reply("Invalid ID.")
             return

        giveaway = self.active_giveaways.get(m_id)
        if not giveaway:
            await ctx.reply(embed=self._create_error_embed("Not Found", "No active giveaway found with that ID."))
            return

        entry_count = len(giveaway["entries"])
        embed = self._create_info_embed(
            "🎟️ Giveaway Entries",
            f"**Prize:** {giveaway['prize']}\n**Total Entries:** {entry_count}"
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway['gid']}")
        await ctx.reply(embed=embed)

    # ----------------- CHECK ENTRIES (SLASH COMMAND) -----------------
    @app_commands.command(name="gentries", description="Check number of entries in a giveaway")
    @app_commands.describe(message_id="The message ID of the giveaway to check")
    async def gentries(self, interaction: discord.Interaction, message_id: str):
        try:
            m_id = int(message_id)
        except ValueError:
             await interaction.response.send_message("Invalid ID.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True)

        giveaway = self.active_giveaways.get(m_id)
        if not giveaway:
            await interaction.followup.send(embed=self._create_error_embed("Not Found", "No active giveaway found with that ID."), ephemeral=True)
            return

        entry_count = len(giveaway["entries"])
        embed = self._create_info_embed(
            "🎟️ Giveaway Entries",
            f"**Prize:** {giveaway['prize']}\n**Total Entries:** {entry_count}"
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway['gid']}")
        await interaction.followup.send(embed=embed)

    # ----------------- AUTO REMINDER -----------------
    @tasks.loop(minutes=1)
    async def giveaway_reminder(self):
        # Create a copy of items to avoid "RuntimeError: dictionary changed size during iteration"
        current_time = discord.utils.utcnow()
        
        for gid, data in list(self.active_giveaways.items()):
            remaining_seconds = (data["ends_at"] - current_time).total_seconds()
            
            # Remind at 5 minutes left or 1 minute left
            # We use a small range because the loop runs every 60s
            if 295 <= remaining_seconds <= 305 or 55 <= remaining_seconds <= 65:
                channel = self.bot.get_channel(data["channel_id"])
                if channel:
                    mins = int(remaining_seconds // 60)
                    if mins == 0: mins = 1
                    
                    embed = self._create_embed(
                        "⏳ Giveaway Reminder",
                        f"**Prize:** {data['prize']}\nEnds in about `{mins}` minute(s)!\nReact with the button to enter!",
                        discord.Color.teal()
                    )
                    embed.set_footer(text=f"Giveaway ID: {data['gid']}")
                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass # Channel might be deleted

    @giveaway_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()

    # ----------------- COG LOAD -----------------
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.giveaway_reminder.is_running():
            self.giveaway_reminder.start()
        print(f"✅ Giveaway Cog loaded | Active: {len(self.active_giveaways)}")


async def setup(bot):
    await bot.add_cog(Giveaways(bot))
