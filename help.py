import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from typing import Dict, List, Optional

CATEGORIES: Dict[str, Dict] = {
    "fun": {
        "name": "Fun & Games",
        "emoji": "🎮",
        "description": "Entertainment commands for fun interactions",
        "commands": [
            {"name": "8ball", "usage": "[question]", "description": "Ask the magic 8-ball a question"},
            {"name": "coinflip", "usage": "", "description": "Flip a virtual coin"},
            {"name": "roll", "usage": "[sides]", "description": "Roll a dice (default 6 sides)"},
            {"name": "rps", "usage": "[rock/paper/scissors]", "description": "Play Rock Paper Scissors"},
            {"name": "truth", "usage": "", "description": "Get a random truth question"},
            {"name": "dare", "usage": "", "description": "Get a random dare challenge"},
            {"name": "meme", "usage": "", "description": "Get a random meme from Reddit"},
            {"name": "joke", "usage": "", "description": "Get a random joke"},
            {"name": "dadjoke", "usage": "", "description": "Get a random dad joke"},
            {"name": "fact", "usage": "", "description": "Get a random interesting fact"},
            {"name": "quote", "usage": "", "description": "Get an inspirational quote"},
            {"name": "luck", "usage": "[member]", "description": "Check someone's luck percentage"},
            {"name": "rate", "usage": "[thing]", "description": "Rate something out of 10"},
            {"name": "say", "usage": "[message]", "description": "Make the bot say something"},
            {"name": "reverse", "usage": "[text]", "description": "Reverse your text"},
            {"name": "mock", "usage": "[text]", "description": "SpOnGeBoB mOcK text"},
            {"name": "choose", "usage": "[option1] [option2] ...", "description": "Choose between options"},
            {"name": "ship", "usage": "[user1] [user2]", "description": "Ship two users together"},
            {"name": "howgay", "usage": "[member]", "description": "Check the gay-o-meter (for fun)"},
            {"name": "iq", "usage": "[member]", "description": "Check someone's IQ (for fun)"},
        ]
    },
    "utility": {
        "name": "Utility",
        "emoji": "🛠️",
        "description": "Helpful utility commands",
        "commands": [
            {"name": "ping", "usage": "", "description": "Check bot latency"},
            {"name": "botinfo", "usage": "", "description": "Display bot statistics"},
            {"name": "serverinfo", "usage": "", "description": "Get server information"},
            {"name": "userinfo", "usage": "[member]", "description": "Get user information"},
            {"name": "avatar", "usage": "[member]", "description": "Get someone's avatar"},
            {"name": "banner", "usage": "[member]", "description": "Get someone's banner"},
            {"name": "roleinfo", "usage": "[role]", "description": "Get role information"},
            {"name": "channelinfo", "usage": "[channel]", "description": "Get channel information"},
            {"name": "membercount", "usage": "", "description": "Show server member count"},
            {"name": "afk", "usage": "[reason]", "description": "Set your AFK status"},
            {"name": "remind", "usage": "[time] [message]", "description": "Set a reminder"},
            {"name": "poll", "usage": "[question]", "description": "Create a poll"},
            {"name": "snipe", "usage": "", "description": "See the last deleted message"},
            {"name": "editsnipe", "usage": "", "description": "See the last edited message"},
            {"name": "firstmessage", "usage": "", "description": "Get the first message in channel"},
        ]
    },
    "moderation": {
        "name": "Moderation",
        "emoji": "🛡️",
        "description": "Server moderation commands",
        "commands": [
            {"name": "kick", "usage": "[member] [reason]", "description": "Kick a member from the server"},
            {"name": "ban", "usage": "[member] [reason]", "description": "Ban a member from the server"},
            {"name": "unban", "usage": "[user_id]", "description": "Unban a user by ID"},
            {"name": "mute", "usage": "[member] [reason]", "description": "Timeout a member"},
            {"name": "unmute", "usage": "[member]", "description": "Remove timeout from a member"},
            {"name": "warn", "usage": "[member] [reason]", "description": "Warn a member"},
            {"name": "warnings", "usage": "[member]", "description": "View member's warnings"},
            {"name": "clearwarns", "usage": "[member]", "description": "Clear member's warnings"},
            {"name": "purge", "usage": "[amount]", "description": "Delete messages in bulk"},
            {"name": "slowmode", "usage": "[seconds]", "description": "Set channel slowmode"},
            {"name": "lock", "usage": "[channel]", "description": "Lock a channel"},
            {"name": "unlock", "usage": "[channel]", "description": "Unlock a channel"},
            {"name": "nuke", "usage": "", "description": "Clone and delete channel"},
            {"name": "nick", "usage": "[member] [nickname]", "description": "Change member's nickname"},
            {"name": "giverole", "usage": "[member] [role]", "description": "Give a role to member"},
            {"name": "removerole", "usage": "[member] [role]", "description": "Remove role from member"},
        ]
    },
    "tickets": {
        "name": "Tickets",
        "emoji": "🎫",
        "description": "Ticket system commands",
        "commands": [
            {"name": "ticketsetup", "usage": "", "description": "Setup the ticket system (easy wizard)"},
            {"name": "ticket_close", "usage": "", "description": "Close a ticket"},
            {"name": "ticket_add", "usage": "[member]", "description": "Add member to ticket"},
            {"name": "ticket_remove", "usage": "[member]", "description": "Remove member from ticket"},
            {"name": "ticket_list", "usage": "", "description": "List all open tickets"},
        ]
    },
    "leveling": {
        "name": "Leveling",
        "emoji": "📊",
        "description": "XP and leveling system",
        "commands": [
            {"name": "rank", "usage": "[member]", "description": "Check your or someone's rank"},
            {"name": "leaderboard", "usage": "", "description": "View the XP leaderboard"},
            {"name": "setxp", "usage": "[member] [amount]", "description": "Set member's XP (Admin)"},
            {"name": "setlevel", "usage": "[member] [level]", "description": "Set member's level (Admin)"},
            {"name": "resetxp", "usage": "[member]", "description": "Reset member's XP (Admin)"},
        ]
    },
    "giveaway": {
        "name": "Giveaways",
        "emoji": "🎉",
        "description": "Giveaway system commands",
        "commands": [
            {"name": "giveaway start", "usage": "[time] [winners] [prize]", "description": "Start a giveaway"},
            {"name": "giveaway end", "usage": "[message_id]", "description": "End a giveaway early"},
            {"name": "giveaway reroll", "usage": "[message_id]", "description": "Reroll giveaway winner"},
            {"name": "giveaway list", "usage": "", "description": "List active giveaways"},
        ]
    },
    "welcome": {
        "name": "Welcome System",
        "emoji": "👋",
        "description": "Welcome/leave message configuration",
        "commands": [
            {"name": "welcomeguide", "usage": "", "description": "Setup guide for welcome system"},
            {"name": "setwelcome", "usage": "[channel]", "description": "Set welcome channel"},
            {"name": "setleave", "usage": "[channel]", "description": "Set leave channel"},
            {"name": "setautorole", "usage": "[role]", "description": "Set auto-role for new members"},
            {"name": "testwelcome", "usage": "", "description": "Test the welcome message"},
        ]
    },
    "security": {
        "name": "Security",
        "emoji": "🔒",
        "description": "Server security features",
        "commands": [
            {"name": "antiraid", "usage": "[on/off]", "description": "Toggle anti-raid protection"},
            {"name": "antispam", "usage": "[on/off]", "description": "Toggle anti-spam protection"},
            {"name": "antilink", "usage": "[on/off]", "description": "Toggle anti-link filter"},
            {"name": "lockdown", "usage": "", "description": "Lock all channels"},
            {"name": "unlockdown", "usage": "", "description": "Unlock all channels"},
        ]
    },
}

class CategorySelect(Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(
                label=cat_data["name"],
                value=cat_key,
                emoji=cat_data["emoji"],
                description=cat_data["description"][:50]
            )
            for cat_key, cat_data in CATEGORIES.items()
        ]
        super().__init__(
            placeholder="Select a command category...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        cat_data = CATEGORIES[selected]
        embed = self.cog.create_category_embed(cat_data)
        await interaction.response.edit_message(embed=embed, view=self.view)

class HelpView(View):
    def __init__(self, cog, author_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.author_id = author_id
        self.add_item(CategorySelect(cog))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This menu belongs to someone else. Use `/help` to get your own!",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Home", style=discord.ButtonStyle.primary, emoji="🏠", row=1)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        embed = self.cog.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="All Commands", style=discord.ButtonStyle.secondary, emoji="📜", row=1)
    async def all_commands_button(self, interaction: discord.Interaction, button: Button):
        embed = self.cog.create_all_commands_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="✖️", row=1)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        await interaction.message.delete()

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.prefix = getattr(bot, 'PREFIX', '~')

    def create_main_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Help Menu",
            description=(
                f"Welcome to **{self.bot.user.name}**! I'm a feature-packed Discord bot.\n\n"
                f"**How to use:**\n"
                f"> Use the dropdown below to browse commands by category\n"
                f"> Both slash (`/`) and prefix (`{self.prefix}`) commands work\n\n"
                f"**Quick Links:**\n"
                f"> `{self.prefix}help` or `/help` - This menu\n"
                f"> `/ticketsetup` - Setup ticket system\n"
                f"> `/welcomeguide` - Setup welcome messages\n\n"
                f"**Categories Available:**"
            ),
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        )
        
        for cat_key, cat_data in CATEGORIES.items():
            cmd_count = len(cat_data["commands"])
            embed.add_field(
                name=f"{cat_data['emoji']} {cat_data['name']}",
                value=f"`{cmd_count}` commands",
                inline=True
            )
        
        total_cmds = sum(len(cat["commands"]) for cat in CATEGORIES.values())
        embed.set_footer(
            text=f"Total: {total_cmds} commands | Made with care",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        return embed

    def create_category_embed(self, cat_data: Dict) -> discord.Embed:
        embed = discord.Embed(
            title=f"{cat_data['emoji']} {cat_data['name']} Commands",
            description=f"{cat_data['description']}\n\n**Available Commands:**",
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        )

        for cmd in cat_data["commands"]:
            usage = f" {cmd['usage']}" if cmd['usage'] else ""
            embed.add_field(
                name=f"`/{cmd['name']}{usage}`",
                value=cmd["description"],
                inline=True
            )

        embed.set_footer(
            text=f"{len(cat_data['commands'])} commands in this category",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        return embed

    def create_all_commands_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="All Commands Overview",
            description="Here's a quick overview of all command categories:",
            color=0x5865F2,
            timestamp=discord.utils.utcnow()
        )

        for cat_key, cat_data in CATEGORIES.items():
            cmd_names = [f"`{cmd['name']}`" for cmd in cat_data["commands"][:8]]
            if len(cat_data["commands"]) > 8:
                cmd_names.append(f"... +{len(cat_data['commands']) - 8} more")
            
            embed.add_field(
                name=f"{cat_data['emoji']} {cat_data['name']}",
                value=" ".join(cmd_names),
                inline=False
            )

        total_cmds = sum(len(cat["commands"]) for cat in CATEGORIES.values())
        embed.set_footer(
            text=f"Total: {total_cmds} commands | Use dropdown for details",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        return embed

    @commands.hybrid_command(name="help", description="Show all bot commands with interactive menu")
    async def help(self, ctx: commands.Context, command: Optional[str] = None):
        if command:
            found = None
            for cat_data in CATEGORIES.values():
                for cmd in cat_data["commands"]:
                    if cmd["name"].lower() == command.lower():
                        found = (cat_data, cmd)
                        break
                if found:
                    break

            if found:
                cat_data, cmd = found
                usage = f" {cmd['usage']}" if cmd['usage'] else ""
                embed = discord.Embed(
                    title=f"Command: {cmd['name']}",
                    description=cmd["description"],
                    color=0x5865F2,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Category", value=f"{cat_data['emoji']} {cat_data['name']}", inline=True)
                embed.add_field(name="Slash Usage", value=f"`/{cmd['name']}{usage}`", inline=True)
                embed.add_field(name="Prefix Usage", value=f"`{self.prefix}{cmd['name']}{usage}`", inline=True)
                embed.set_footer(
                    text=f"Requested by {ctx.author}",
                    icon_url=ctx.author.display_avatar.url
                )
                return await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Command Not Found",
                    description=f"Could not find a command named `{command}`.\nUse `/help` to see all available commands.",
                    color=0xED4245
                )
                return await ctx.send(embed=embed, ephemeral=True)

        embed = self.create_main_embed()
        view = HelpView(self, ctx.author.id)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="commands", description="Quick list of all command categories")
    async def commands_list(self, interaction: discord.Interaction):
        embed = self.create_all_commands_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
