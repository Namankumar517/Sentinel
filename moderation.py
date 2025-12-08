# moderation.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone # Added timezone

class Moderation(commands.Cog):
    """Premium Moderation Commands with embeds and hybrid support."""
    def __init__(self, bot):
        self.bot = bot
        # Removed self.muted_users since native timeouts are used and the check_mutes task is empty.
        # self.muted_users = {} # temp mute tracking: {guild_id: {user_id: unmute_time}}
        self.check_mutes.start() # Start the background task (now just a placeholder/startup function)

    # ----------------- UTILITY EMBED FUNCTION -----------------
    def premium_embed(self, title: str, description: str, color=discord.Color.blurple()):
        """Returns a premium style embed for moderation commands."""
        embed = discord.Embed(
            title=f"🛡️ {title}", # Changed Emoji
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc) # Use timezone-aware datetime
        )
        embed.set_footer(text=f"Premium Moderation | {self.bot.user.name}", icon_url=self.bot.user.display_avatar.url)
        return embed

    # ----------------- KICK (Hybrid) -----------------
    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @commands.has_permissions(kick_members=True) # Use decorator for permission check
    @app_commands.checks.has_permissions(kick_members=True) # Slash command permission check
    async def kick(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        # Bot permission check
        if not ctx.guild.me.guild_permissions.kick_members:
             return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to kick members.", discord.Color.red()), ephemeral=True)
        # Hierarchy check
        # Check against author's top role
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot kick someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        # Check against bot's top role
        if member.top_role >= ctx.guild.me.top_role:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "I cannot kick someone with a higher or equal role than mine.", discord.Color.red()), ephemeral=True)
        # Prevent self-kick/kick owner
        if member == ctx.author or member == ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot kick yourself or the server owner.", discord.Color.red()), ephemeral=True)
             
        try:
            await member.kick(reason=f"{reason} (Kicked by {ctx.author})")
            embed = self.premium_embed("Member Kicked", f"{member.mention} has been kicked.\n**Reason:** {reason}", discord.Color.orange())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not kick {member.mention}.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- BAN (Hybrid) -----------------
    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    @commands.has_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        if not ctx.guild.me.guild_permissions.ban_members:
             return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to ban members.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot ban someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.guild.me.top_role:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "I cannot ban someone with a higher or equal role than mine.", discord.Color.red()), ephemeral=True)
        if member == ctx.author or member == ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot ban yourself or the server owner.", discord.Color.red()), ephemeral=True)
             
        try:
            await member.ban(reason=f"{reason} (Banned by {ctx.author})")
            embed = self.premium_embed("Member Banned", f"{member.mention} has been banned.\n**Reason:** {reason}", discord.Color.red())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not ban {member.mention}.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- TEMP BAN (Hybrid - Improved) -----------------
    @commands.hybrid_command(name="tempban", description="Temporarily ban a member")
    @app_commands.describe(member="Member to tempban", duration="Duration (e.g., 5m, 2h, 1d)", reason="Reason for tempban")
    @commands.has_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    async def tempban(self, ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
        # Defer for time parsing and the asyncio.sleep, making sure to handle hybrid context
        if ctx.interaction:
            await ctx.defer(ephemeral=True) 

        if not ctx.guild.me.guild_permissions.ban_members:
             reply_func = ctx.followup.send if ctx.interaction else ctx.reply
             return await reply_func(embed=self.premium_embed("Bot Permission Error", "I don't have permission to ban members.", discord.Color.red()), ephemeral=True)
        
        # Hierarchy checks
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             reply_func = ctx.followup.send if ctx.interaction else ctx.reply
             return await reply_func(embed=self.premium_embed("Hierarchy Error", "You cannot ban someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.guild.me.top_role:
             reply_func = ctx.followup.send if ctx.interaction else ctx.reply
             return await reply_func(embed=self.premium_embed("Hierarchy Error", "I cannot ban someone with a higher or equal role than mine.", discord.Color.red()), ephemeral=True)
        if member == ctx.author or member == ctx.guild.owner:
             reply_func = ctx.followup.send if ctx.interaction else ctx.reply
             return await reply_func(embed=self.premium_embed("Error", "You cannot temp-ban yourself or the server owner.", discord.Color.red()), ephemeral=True)

        # Time parsing
        unit = duration[-1].lower() # Handle case sensitivity
        if not duration[:-1].isdigit() or unit not in ["s", "m", "h", "d"]:
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            return await reply_func(embed=self.premium_embed("Invalid Format", "❌ Please use a format like `10s`, `5m`, `2h`, or `1d`.", discord.Color.red()), ephemeral=True)
            
        amount = int(duration[:-1])
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit] * amount

        if seconds > 86400 * 30: # Max 30 days tempban for safety
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            return await reply_func(embed=self.premium_embed("Duration Too Long", "Temporary bans cannot exceed 30 days.", discord.Color.red()), ephemeral=True)
            
        try:
            await member.ban(reason=f"{reason} (Temp-banned by {ctx.author} for {duration})")
            unban_time_ts = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp())
            embed = self.premium_embed("Member Temp-Banned", f"{member.mention} has been banned for **{duration}** (until <t:{unban_time_ts}:F>).\n**Reason:** {reason}", discord.Color.red())
            
            # Use appropriate reply function
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            await reply_func(embed=embed) 

            # Unban logic (runs in the background)
            await asyncio.sleep(seconds)
            
            # Check if the guild still exists and the bot is still a member
            if ctx.guild:
                # Fetch user object since member might not be in cache
                try:
                    user = await self.bot.fetch_user(member.id) 
                except discord.NotFound:
                    # User was deleted or is a bot that left, just proceed.
                    user = None

                if user:
                    try:
                        # Check if the user is still banned before attempting unban
                        # This prevents unnecessary errors if they were manually unbanned
                        ban_entry = await ctx.guild.fetch_ban(user)
                        
                        await ctx.guild.unban(user, reason=f"Tempban duration ({duration}) expired. (Automatic unban)")
                        print(f"Unbanned {user} after tempban in {ctx.guild.name}.")
                        
                        # Optionally send an unban message to a modlog channel
                        modlog = discord.utils.get(ctx.guild.text_channels, name="mod-logs")
                        if modlog:
                            unban_embed = self.premium_embed(
                                "✅ Automatic Unban",
                                f"**Member:** {user.mention} ({user.id})\n**Reason:** Tempban duration ({duration}) expired.",
                                discord.Color.green()
                            )
                            await modlog.send(embed=unban_embed)

                    except discord.NotFound:
                         print(f"User {member.id} was already unbanned or not found in ban list for automatic unban.")
                    except discord.Forbidden:
                         print(f"Missing permissions to unban {member} in {ctx.guild.name}.")
                    except Exception as e_unban:
                         print(f"Error unbanning {member} after tempban: {e_unban}")
            else:
                 print(f"Guild {ctx.guild.id} not found for tempban cleanup.")

        except Exception as e:
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            await reply_func(embed=self.premium_embed("Error", f"Could not temp-ban {member.mention}.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- MUTE (Hybrid - Timeout Based) -----------------
    # Uses Discord's built-in Timeout feature which is much better than role-based mute.
    @commands.hybrid_command(name="mute", description="Timeout a member for a specified duration.")
    @app_commands.describe(member="Member to mute/timeout", duration="Duration (e.g., 5m, 2h, 1d, max 28d)", reason="Reason for mute")
    @commands.has_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if not ctx.guild.me.guild_permissions.moderate_members:
             return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to timeout members.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot mute someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.guild.me.top_role:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "I cannot mute someone with a higher or equal role than mine.", discord.Color.red()), ephemeral=True)
        if member == ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot mute the server owner.", discord.Color.red()), ephemeral=True)
        if member == ctx.author:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot mute yourself.", discord.Color.red()), ephemeral=True)
             
        # Time parsing
        unit = duration[-1].lower() # Handle case sensitivity
        if not duration[:-1].isdigit() or unit not in ["s", "m", "h", "d"]:
            return await ctx.reply(embed=self.premium_embed("Invalid Format", "❌ Please use a format like `10s`, `5m`, `2h`, or `1d`.", discord.Color.red()))
        amount = int(duration[:-1])
        seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit] * amount

        # Discord Timeout Limit is 28 days
        max_seconds = 28 * 86400
        if seconds <= 0 or seconds > max_seconds:
             return await ctx.reply(embed=self.premium_embed("Invalid Duration", "Duration must be between 1 second and 28 days.", discord.Color.red()))

        until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        
        try:
            await member.timeout(until, reason=f"{reason} (Muted by {ctx.author} for {duration})")
            msg = f"{member.mention} has been muted until <t:{int(until.timestamp())}:R>.\n**Reason:** {reason}"
            embed = self.premium_embed("Member Muted (Timeout)", msg, discord.Color.orange())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not mute {member.mention}.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- UNMUTE (Hybrid - Timeout Based) -----------------
    @commands.hybrid_command(name="unmute", description="Remove timeout from a member")
    @app_commands.describe(member="Member to unmute")
    @commands.has_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        if not ctx.guild.me.guild_permissions.moderate_members:
             return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to remove timeouts.", discord.Color.red()), ephemeral=True)
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot unmute someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        if member == ctx.author:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot unmute yourself.", discord.Color.red()), ephemeral=True)
        
        # Check if the member is actually timed out (timed_out_until returns a datetime object if timed out)
        if member.timed_out_until is None or member.timed_out_until < datetime.now(timezone.utc):
            return await ctx.reply(embed=self.premium_embed("Not Muted", f"{member.mention} is not currently muted (timed out).", discord.Color.orange()), ephemeral=True)
            
        try:
            await member.timeout(None, reason=f"Unmuted by {ctx.author}") # Pass None to remove timeout
            embed = self.premium_embed("Member Unmuted", f"{member.mention} has been unmuted (timeout removed).", discord.Color.green())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not unmute {member.mention}.\nError: {e}", discord.Color.red()), ephemeral=True)
            
    # --- Temp Mute (Role-Based) Cleanup - Runs in background ---
    @tasks.loop(minutes=1) # Check every minute
    async def check_mutes(self):
        # This function is removed as we now use Discord's native timeout feature.
        # It is kept as a loop for initialization/startup but performs no action.
        pass

    @check_mutes.before_loop
    async def before_check_mutes(self):
        await self.bot.wait_until_ready()
            
    # ----------------- WARN (Hybrid) -----------------
    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @commands.has_permissions(kick_members=True) # Usually mods who can kick can warn
    @app_commands.checks.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot warn someone with a higher or equal role.", discord.Color.red()), ephemeral=True)
        if member == ctx.author:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot warn yourself.", discord.Color.red()), ephemeral=True)

        # Ensure warns_dict exists on the bot object
        if not hasattr(self.bot, "warns_dict"):
            self.bot.warns_dict = {} # Initialize if not present

        guild_id_str = str(ctx.guild.id)
        member_id_str = str(member.id)

        # Structure: {guild_id: {user_id: [ {reason: str, moderator: int, timestamp: str} ]}}
        self.bot.warns_dict.setdefault(guild_id_str, {})
        self.bot.warns_dict[guild_id_str].setdefault(member_id_str, [])
        
        warn_entry = {
            "reason": reason,
            "moderator": ctx.author.id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.bot.warns_dict[guild_id_str][member_id_str].append(warn_entry)
        
        # You should ideally save self.bot.warns_dict to a file periodically or on bot shutdown.

        # Send premium embed
        total_warnings = len(self.bot.warns_dict[guild_id_str][member_id_str])
        embed = self.premium_embed(
            "Member Warned",
            f"{member.mention} has been warned.\n**Reason:** {reason}\n**Total Warnings:** {total_warnings}",
            discord.Color.orange()
        )
        await ctx.reply(embed=embed)

        # Optional mod-log channel
        modlog = discord.utils.get(ctx.guild.text_channels, name="mod-logs")
        if modlog:
            log_embed = self.premium_embed(
                "⚠️ Warning Issued",
                f"**Member:** {member.mention} ({member.id})\n**By:** {ctx.author.mention}\n**Reason:** {reason}\n**Total Warnings:** {total_warnings}",
                discord.Color.orange()
            )
            try:
                await modlog.send(embed=log_embed)
            except Exception as e:
                print(f"Failed to send warn to modlog: {e}")

    # ----------------- VIEW WARNINGS (Hybrid - New Command) -----------------
    @commands.hybrid_command(name="warnings", description="View warnings for a member.")
    @app_commands.describe(member="Member whose warnings to view")
    @commands.has_permissions(kick_members=True) # Permission to view warns
    @app_commands.checks.has_permissions(kick_members=True)
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        if not hasattr(self.bot, "warns_dict"):
             self.bot.warns_dict = {}

        guild_id_str = str(ctx.guild.id)
        member_id_str = str(member.id)

        user_warnings = self.bot.warns_dict.get(guild_id_str, {}).get(member_id_str, [])

        if not user_warnings:
             # Using reply for both prefix and slash is fine here as no defer is needed
             return await ctx.reply(embed=self.premium_embed("No Warnings", f"{member.mention} has no warnings on record.", discord.Color.green()), ephemeral=True)

        embed = self.premium_embed(f"Warnings for {member.display_name}", f"Total Warnings: **{len(user_warnings)}**", discord.Color.orange())
        
        # Display latest 5 warnings for brevity
        # Correctly iterate through the last 5 elements and calculate the correct index for display
        warnings_to_display = user_warnings[-5:]
        total_warnings = len(user_warnings)
        
        for i, warn in enumerate(reversed(warnings_to_display)):
            # The warning number is total_warnings - (index_in_reversed_list)
            warning_number = total_warnings - (len(warnings_to_display) - 1 - i)
            
            # Use bot.get_user for moderators who may have left the guild
            moderator = self.bot.get_user(warn.get("moderator", 0))
            moderator_display = moderator.mention if moderator else f"ID: {warn.get('moderator', 'Unknown')}"
            
            timestamp_str = warn.get("timestamp")
            timestamp_dt = datetime.fromisoformat(timestamp_str) if timestamp_str else None
            time_display = f"<t:{int(timestamp_dt.timestamp())}:R>" if timestamp_dt else "Unknown Time"
            
            embed.add_field(
                name=f"Warning #{warning_number} ({time_display})",
                value=f"**Reason:** {warn.get('reason', 'N/A')}\n**Moderator:** {moderator_display}",
                inline=False
            )
            
        await ctx.reply(embed=embed, ephemeral=True)

    # ----------------- CLEAR MESSAGES (Hybrid) -----------------
    @commands.hybrid_command(name="clear", aliases=["purge"], description="Delete messages from the channel")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @commands.has_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int = 5):
        if not ctx.guild.me.guild_permissions.manage_messages:
             return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to manage messages.", discord.Color.red()), ephemeral=True)
             
        if amount < 1 or amount > 100:
            return await ctx.reply(embed=self.premium_embed("Invalid Amount", "You can delete between 1 and 100 messages at a time.", discord.Color.gold()), ephemeral=True)
        
        try:
            # Always defer if it's a slash command to prevent timeout
            if ctx.interaction:
                await ctx.defer(ephemeral=True)
            
            # Fetch and delete. The limit should only be 'amount' as purge handles the command message differently
            # or not at all depending on the command type and discord.py version.
            # Using limit=amount generally works best, and we rely on the command context for the reply.
            deleted = await ctx.channel.purge(limit=amount)
            
            final_deleted_count = len(deleted)
            
            embed = self.premium_embed("Messages Deleted", f"🧹 Successfully deleted {final_deleted_count} message(s).", discord.Color.green())
            
            # Use followup for slash commands, reply for prefix commands.
            if ctx.interaction:
                await ctx.followup.send(embed=embed, ephemeral=True)
            else:
                # For prefix commands, the command message itself might be in 'deleted'.
                # The user's original logic was attempting to correct for this.
                # A simple correction is to delete 'amount' + 1 and report 'amount'.
                # A simpler approach is to use the actual count and rely on the bot's auto-deletion of the command message.
                # For simplicity and reliability with purge, we'll stick to 'amount' and use the follow-up/reply correctly.
                # If the prefix command invocation *wasn't* deleted, we'll try to delete it manually.
                try:
                    await ctx.message.delete()
                except discord.NotFound:
                    pass # Already deleted by purge
                except discord.Forbidden:
                    pass # Cannot delete

                # Send the final confirmation as a regular message, then delete it after a delay
                confirmation = await ctx.send(embed=embed)
                await asyncio.sleep(5)
                await confirmation.delete()
            
        except discord.Forbidden:
            # Use followup if deferred, otherwise reply
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            await reply_func(embed=self.premium_embed("Error", "I don't have permission to delete messages in this channel.", discord.Color.red()), ephemeral=True)
        except Exception as e:
            reply_func = ctx.followup.send if ctx.interaction else ctx.reply
            await reply_func(embed=self.premium_embed("Error", f"Could not delete messages.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- LOCK / UNLOCK CHANNEL (Hybrid) -----------------
    @commands.hybrid_command(name="lock", description="Lock the current channel for @everyone")
    @commands.has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        if not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to manage channel permissions.", discord.Color.red()), ephemeral=True)
            
        try:
            # Create a copy of the current overwrites for the default role
            overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
            
            # Check if send_messages is explicitly False, or if it is None and the channel default denies it.
            # Checking overwrite.send_messages is False is the clearest check for a lock.
            if overwrite.send_messages is False:
                return await ctx.reply(embed=self.premium_embed("Already Locked", f"{ctx.channel.mention} is already locked (send messages denied).", discord.Color.orange()))

            overwrite.send_messages = False
            await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Channel locked by {ctx.author}")
            embed = self.premium_embed("Channel Locked", f"🔒 {ctx.channel.mention} has been locked for @everyone.", discord.Color.orange())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not lock the channel.\nError: {e}", discord.Color.red()), ephemeral=True)

    @commands.hybrid_command(name="unlock", description="Unlock the current channel for @everyone")
    @commands.has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        if not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to manage channel permissions.", discord.Color.red()), ephemeral=True)
            
        try:
            overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
            # Check if send_messages is explicitly False, indicating a lock.
            if overwrite.send_messages is not False: 
                 return await ctx.reply(embed=self.premium_embed("Already Unlocked", f"{ctx.channel.mention} is not locked (send messages is not explicitly denied).", discord.Color.orange()))

            # Set to None to remove the explicit deny, allowing it to inherit from server/category.
            overwrite.send_messages = None 
            await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=f"Channel unlocked by {ctx.author}")
            embed = self.premium_embed("Channel Unlocked", f"🔓 {ctx.channel.mention} has been unlocked for @everyone.", discord.Color.green())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not unlock the channel.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- GIVE ROLE (Hybrid) -----------------
    @commands.hybrid_command(name="giverole", description="Give a role to a member")
    @app_commands.describe(member="Member to give role", role="Role to assign")
    @commands.has_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def giverole(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to manage roles.", discord.Color.red()), ephemeral=True)
        # Check if the role is higher than the *moderator's* top role (cannot manage roles higher than your own unless you are owner)
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot assign a role higher than or equal to your own top role.", discord.Color.red()), ephemeral=True)
        # Check if the role is higher than the *bot's* top role (bot cannot assign roles higher than its own)
        if role >= ctx.guild.me.top_role:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "I cannot assign a role higher than or equal to my own top role.", discord.Color.red()), ephemeral=True)
        if member == ctx.author:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot give a role to yourself with this command.", discord.Color.red()), ephemeral=True)

        try:
            if role in member.roles:
                 return await ctx.reply(embed=self.premium_embed("Already Has Role", f"{member.mention} already has the {role.mention} role.", discord.Color.orange()))
                 
            await member.add_roles(role, reason=f"Role assigned by {ctx.author}")
            embed = self.premium_embed("Role Given", f"{member.mention} has been assigned the role {role.mention}.", discord.Color.green())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not assign role.\nError: {e}", discord.Color.red()), ephemeral=True)

    # ----------------- REMOVE ROLE (Hybrid) -----------------
    @commands.hybrid_command(name="takerole", description="Remove a role from a member")
    @app_commands.describe(member="Member to remove role from", role="Role to remove")
    @commands.has_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def takerole(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.reply(embed=self.premium_embed("Bot Permission Error", "I don't have permission to manage roles.", discord.Color.red()), ephemeral=True)
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "You cannot remove a role higher than or equal to your own top role.", discord.Color.red()), ephemeral=True)
        if role >= ctx.guild.me.top_role:
             return await ctx.reply(embed=self.premium_embed("Hierarchy Error", "I cannot remove a role higher than or equal to my own top role.", discord.Color.red()), ephemeral=True)
        if member == ctx.author:
             return await ctx.reply(embed=self.premium_embed("Error", "You cannot remove a role from yourself with this command.", discord.Color.red()), ephemeral=True)

        try:
            if role not in member.roles:
                 return await ctx.reply(embed=self.premium_embed("Does Not Have Role", f"{member.mention} does not have the {role.mention} role.", discord.Color.orange()))

            await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
            embed = self.premium_embed("Role Removed", f"{role.mention} has been removed from {member.mention}.", discord.Color.orange())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(embed=self.premium_embed("Error", f"Could not remove role.\nError: {e}", discord.Color.red()), ephemeral=True)

# ----------------- COG SETUP -----------------
async def setup(bot):
    await bot.add_cog(Moderation(bot))
