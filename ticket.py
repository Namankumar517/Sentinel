import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import json
from typing import Optional, Union, List

os.makedirs("data/transcripts", exist_ok=True)
TICKET_SETUP_FILE = "data/ticket_setup.json"

def load_setup_data():
    if os.path.exists(TICKET_SETUP_FILE):
        try:
            with open(TICKET_SETUP_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_setup_data(data):
    with open(TICKET_SETUP_FILE, "w") as f:
        json.dump(data, f, indent=4)

class TicketSetupModal(discord.ui.Modal, title="Ticket Panel Setup"):
    panel_title = discord.ui.TextInput(
        label="Panel Title",
        placeholder="e.g., Support Tickets",
        default="Support Tickets",
        max_length=100
    )
    panel_description = discord.ui.TextInput(
        label="Panel Description",
        placeholder="Click a button below to create a ticket",
        default="Click a button below to create a support ticket. Our team will assist you shortly!",
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    ticket_name = discord.ui.TextInput(
        label="Ticket Type Name",
        placeholder="e.g., General Support",
        default="General Support",
        max_length=50
    )
    ticket_emoji = discord.ui.TextInput(
        label="Button Emoji",
        placeholder="e.g., 🎫 or 📩",
        default="🎫",
        max_length=5
    )
    embed_color = discord.ui.TextInput(
        label="Embed Color (HEX)",
        placeholder="e.g., #5865F2",
        default="#5865F2",
        max_length=7
    )

    def __init__(self, cog, channel: discord.TextChannel, category: discord.CategoryChannel, role: discord.Role):
        super().__init__()
        self.cog = cog
        self.target_channel = channel
        self.category = category
        self.support_role = role

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        setup_data = {
            "panel_channel_id": self.target_channel.id,
            "embed_color": str(self.embed_color),
            "panel_title": str(self.panel_title),
            "panel_description": str(self.panel_description),
            "selection_type": "button",
            "options": [{
                "name": str(self.ticket_name),
                "emoji": str(self.ticket_emoji),
                "category_id": self.category.id,
                "role_id": self.support_role.id
            }]
        }

        try:
            color = discord.Color.from_str(str(self.embed_color))
        except:
            color = discord.Color.blurple()

        embed = discord.Embed(
            title=f"✨ {self.panel_title}",
            description=str(self.panel_description),
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(
            text="Click the button below to create a ticket",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        view = SimpleTicketButtonView(self.cog, setup_data)
        panel_msg = await self.target_channel.send(embed=embed, view=view)
        setup_data["panel_message_id"] = panel_msg.id

        all_data = load_setup_data()
        all_data[str(interaction.guild.id)] = setup_data
        save_setup_data(all_data)
        self.cog.ticket_setup_data = all_data

        success_embed = discord.Embed(
            title="Ticket System Setup Complete!",
            description=f"The ticket panel has been sent to {self.target_channel.mention}\n\n"
                       f"**Configuration:**\n"
                       f"> **Category:** {self.category.name}\n"
                       f"> **Support Role:** {self.support_role.mention}\n"
                       f"> **Ticket Type:** {self.ticket_name}\n\n"
                       f"Users can now click the button to create tickets!",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

class SimpleTicketButton(discord.ui.Button):
    def __init__(self, cog, label: str, emoji: str):
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            custom_id="simple_ticket_create_v1"
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        setup_data = self.cog.ticket_setup_data.get(guild_id)
        
        if not setup_data or not setup_data.get("options"):
            return await interaction.followup.send(
                "Ticket system not configured. Please ask an admin to run `/ticketsetup`.",
                ephemeral=True
            )

        ticket_info = setup_data["options"][0]
        await self.cog._create_ticket_channel(interaction, ticket_info)

class SimpleTicketButtonView(discord.ui.View):
    def __init__(self, cog, setup_data: dict = None):
        super().__init__(timeout=None)
        self.cog = cog
        
        if setup_data and setup_data.get("options"):
            opt = setup_data["options"][0]
            label = opt.get("name", "Create Ticket")
            emoji = opt.get("emoji", "🎫")
        else:
            label = "Create Ticket"
            emoji = "🎫"
        
        self.add_item(SimpleTicketButton(cog, label, emoji))

class TicketControlView(discord.ui.View):
    def __init__(self, cog, owner_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_info = self.cog.bot.tickets_dict.get(interaction.channel.id)
        
        if not ticket_info:
            return await interaction.response.send_message("This is not a valid ticket.", ephemeral=True)
        
        if interaction.user.id != ticket_info.get("owner_id") and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You cannot close this ticket.", ephemeral=True)
        
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send(
            embed=discord.Embed(
                title="Closing Ticket",
                description="Generating transcript... Channel will be deleted in 5 seconds.",
                color=discord.Color.red()
            )
        )
        await self.cog.close_ticket(interaction.channel, interaction.user)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success, emoji="✋", custom_id="ticket_claim_btn")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)
        
        ticket_info = self.cog.bot.tickets_dict.get(interaction.channel.id)
        if ticket_info:
            ticket_info["claimed_by"] = interaction.user.id
            
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.response.edit_message(view=self)
        
        await interaction.channel.send(
            embed=discord.Embed(
                title="Ticket Claimed",
                description=f"{interaction.user.mention} will be handling this ticket.",
                color=discord.Color.green()
            )
        )

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "tickets_dict"):
            self.bot.tickets_dict = {}
        
        self.ticket_setup_data = load_setup_data()
        
        if not hasattr(bot, "ticket_views_registered"):
            bot.add_view(SimpleTicketButtonView(self))
            bot.add_view(TicketControlView(self, 0))
            bot.ticket_views_registered = True

    def premium_embed(self, title: str, description: str, color_hex: str = "#5865F2"):
        try:
            color = discord.Color.from_str(color_hex)
        except:
            color = discord.Color.blurple()

        embed = discord.Embed(
            title=f"✨ {title}",
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )
        if self.bot.user:
            embed.set_footer(text="Ticket System", icon_url=self.bot.user.display_avatar.url)
        return embed

    @app_commands.command(name="ticketsetup", description="Easy wizard to setup the ticket system")
    @app_commands.describe(
        channel="Channel where the ticket panel will be sent",
        category="Category where new tickets will be created",
        support_role="Role that will be pinged for new tickets"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticketsetup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        category: discord.CategoryChannel,
        support_role: discord.Role
    ):
        modal = TicketSetupModal(self, channel, category, support_role)
        await interaction.response.send_modal(modal)

    @commands.command(name="ticketsetup", aliases=["setupticket", "tsetup"])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def ticketsetup_prefix(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Ticket Setup",
            description=(
                "To set up the ticket system, please use the slash command:\n\n"
                "`/ticketsetup channel:#channel category:#category support_role:@role`\n\n"
                "**Parameters:**\n"
                "> `channel` - Where the ticket panel will appear\n"
                "> `category` - Category for new ticket channels\n"
                "> `support_role` - Role to ping for tickets\n\n"
                "The slash command provides an easy form to fill out!"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    async def _create_ticket_channel(self, interaction: discord.Interaction, ticket_info: dict):
        guild = interaction.guild
        author = interaction.user

        for channel_id, info in self.bot.tickets_dict.items():
            if info.get("owner_id") == author.id and info.get("status") == "open":
                existing = guild.get_channel(channel_id)
                if existing:
                    return await interaction.followup.send(
                        f"You already have an open ticket: {existing.mention}",
                        ephemeral=True
                    )

        category = guild.get_channel(ticket_info.get("category_id"))
        if not category or not isinstance(category, discord.CategoryChannel):
            category = None

        support_role = guild.get_role(ticket_info.get("role_id"))

        channel_name = f"ticket-{author.name}".lower().replace(" ", "-")[:95]
        
        counter = 1
        base_name = channel_name
        while discord.utils.get(guild.text_channels, name=channel_name):
            channel_name = f"{base_name}-{counter}"
            counter += 1

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            author: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, 
                send_messages=True, 
                read_message_history=True,
                manage_messages=True
            )

        try:
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket by {author}"
            )
        except discord.Forbidden:
            return await interaction.followup.send("I don't have permission to create channels.", ephemeral=True)
        except Exception as e:
            return await interaction.followup.send(f"Failed to create ticket: {e}", ephemeral=True)

        self.bot.tickets_dict[channel.id] = {
            "owner_id": author.id,
            "created_at": discord.utils.utcnow().isoformat(),
            "type": ticket_info.get("name", "Support"),
            "status": "open"
        }

        setup_data = self.ticket_setup_data.get(str(guild.id), {})
        color_hex = setup_data.get("embed_color", "#5865F2")

        embed = self.premium_embed(
            f"Ticket: {ticket_info.get('name', 'Support')}",
            f"Hello {author.mention}!\n\n"
            f"Thank you for creating a ticket. Please describe your issue and our team will assist you shortly.\n\n"
            f"**Ticket Owner:** {author.mention}\n"
            f"**Created:** {discord.utils.format_dt(discord.utils.utcnow(), 'R')}",
            color_hex
        )

        view = TicketControlView(self, author.id)
        
        ping_msg = f"{author.mention}"
        if support_role:
            ping_msg += f" {support_role.mention}"

        try:
            await channel.send(content=ping_msg, embed=embed, view=view)
        except:
            pass

        await interaction.followup.send(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )

    async def close_ticket(self, channel: discord.TextChannel, closed_by: discord.Member):
        ticket = self.bot.tickets_dict.get(channel.id)
        if not ticket or ticket.get("status") == "closed":
            return

        ticket["status"] = "closed"
        ticket["closed_at"] = discord.utils.utcnow().isoformat()
        ticket["closed_by"] = closed_by.id

        transcript_path = await self._generate_transcript(channel, ticket)

        try:
            await channel.send(
                embed=discord.Embed(
                    title="Ticket Closed",
                    description=f"Closed by: {closed_by.mention}",
                    color=discord.Color.red()
                ),
                file=discord.File(transcript_path)
            )
        except:
            pass

        await asyncio.sleep(5)
        
        try:
            await channel.delete(reason=f"Ticket closed by {closed_by}")
        except:
            pass
        
        self.bot.tickets_dict.pop(channel.id, None)

    async def _generate_transcript(self, channel: discord.TextChannel, ticket_info: dict):
        messages = []
        try:
            async for msg in channel.history(limit=500, oldest_first=True):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = msg.content or "[No text content]"
                if msg.attachments:
                    content += f" [Attachments: {len(msg.attachments)}]"
                messages.append(f"[{timestamp}] {msg.author}: {content}")
        except:
            messages.append("[Could not fetch full history]")

        filename = f"data/transcripts/ticket_{channel.guild.id}_{channel.id}.txt"
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"=== Ticket Transcript ===\n")
                f.write(f"Channel: {channel.name}\n")
                f.write(f"Guild: {channel.guild.name}\n")
                f.write(f"Owner ID: {ticket_info.get('owner_id')}\n")
                f.write(f"Type: {ticket_info.get('type')}\n")
                f.write(f"Created: {ticket_info.get('created_at')}\n")
                f.write(f"Closed: {ticket_info.get('closed_at')}\n")
                f.write(f"Closed By: {ticket_info.get('closed_by')}\n\n")
                f.write("=== Messages ===\n")
                f.write("\n".join(messages))
        except:
            filename = f"data/transcripts/error_{channel.id}.txt"
            with open(filename, "w") as f:
                f.write("Failed to generate transcript")
        
        return filename

    @app_commands.command(name="ticket_close", description="Close a ticket channel")
    @app_commands.describe(channel="Ticket channel to close (default: current)")
    async def ticket_close_slash(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        target = channel or interaction.channel
        
        if target.id not in self.bot.tickets_dict:
            return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        
        ticket = self.bot.tickets_dict[target.id]
        
        if interaction.user.id != ticket.get("owner_id") and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You cannot close this ticket.", ephemeral=True)
        
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await self.close_ticket(target, interaction.user)

    @app_commands.command(name="ticket_add", description="Add a member to a ticket")
    @app_commands.describe(member="Member to add", channel="Ticket channel (default: current)")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_add_slash(self, interaction: discord.Interaction, member: discord.Member, channel: Optional[discord.TextChannel] = None):
        target = channel or interaction.channel
        
        if target.id not in self.bot.tickets_dict:
            return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        
        try:
            await target.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(f"Added {member.mention} to {target.mention}", ephemeral=True)
            await target.send(f"{member.mention} has been added to this ticket by {interaction.user.mention}")
        except Exception as e:
            await interaction.response.send_message(f"Failed to add member: {e}", ephemeral=True)

    @app_commands.command(name="ticket_remove", description="Remove a member from a ticket")
    @app_commands.describe(member="Member to remove", channel="Ticket channel (default: current)")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_remove_slash(self, interaction: discord.Interaction, member: discord.Member, channel: Optional[discord.TextChannel] = None):
        target = channel or interaction.channel
        
        if target.id not in self.bot.tickets_dict:
            return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        
        ticket = self.bot.tickets_dict[target.id]
        if member.id == ticket.get("owner_id"):
            return await interaction.response.send_message("Cannot remove the ticket owner.", ephemeral=True)
        
        try:
            await target.set_permissions(member, overwrite=None)
            await interaction.response.send_message(f"Removed {member.mention} from {target.mention}", ephemeral=True)
            await target.send(f"{member.mention} has been removed from this ticket by {interaction.user.mention}")
        except Exception as e:
            await interaction.response.send_message(f"Failed to remove member: {e}", ephemeral=True)

    @app_commands.command(name="ticket_list", description="List all open tickets")
    async def ticket_list_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        if interaction.user.guild_permissions.manage_guild:
            tickets = []
            for ch_id, info in self.bot.tickets_dict.items():
                if info.get("status") == "open":
                    ch = guild.get_channel(ch_id)
                    if ch:
                        owner = guild.get_member(info.get("owner_id"))
                        owner_text = owner.mention if owner else f"ID: {info.get('owner_id')}"
                        tickets.append(f"• {ch.mention} - {owner_text}")
            
            if not tickets:
                return await interaction.followup.send("No open tickets.", ephemeral=True)
            
            embed = discord.Embed(
                title=f"Open Tickets ({len(tickets)})",
                description="\n".join(tickets[:20]),
                color=discord.Color.blurple()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            tickets = []
            for ch_id, info in self.bot.tickets_dict.items():
                if info.get("owner_id") == interaction.user.id and info.get("status") == "open":
                    ch = guild.get_channel(ch_id)
                    if ch:
                        tickets.append(f"• {ch.mention}")
            
            if not tickets:
                return await interaction.followup.send("You have no open tickets.", ephemeral=True)
            
            embed = discord.Embed(
                title="Your Open Tickets",
                description="\n".join(tickets),
                color=discord.Color.blurple()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Ticket Cog loaded. Tracking {len(self.bot.tickets_dict)} tickets")

async def setup(bot):
    await bot.add_cog(Ticket(bot))
