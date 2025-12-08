import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os
from typing import Dict, Any, Optional
import asyncio
from openai import AsyncOpenAI, OpenAIError 

# --- Configuration File Path ---
CONFIG_FILE = 'data/ai_config.json'

# --- 🔑 IMPORTANT: YOUR HUGGING FACE TOKEN IS USED HERE ---
# Token provided by user: Hf_gZpPFKuLqJuRvUbUtOCPLPssfdqiQGOwdM
HUGGINGFACE_API_KEY = "Hf_gZpPFKuLqJuRvUbUtOCPLPssfdqiQGOwdM" 

# --- AI Client Integration (Hugging Face Router) ---
class HuggingFaceClient:
    """Handles communication with Hugging Face via the Inference Router."""
    
    def __init__(self):
        if HUGGINGFACE_API_KEY == "YOUR_HUGGINGFACE_API_TOKEN":
            # This check will not trigger now, but good practice to keep
            print("🚨 WARNING: Hugging Face API key is missing. The bot will not reply.")
        
        # Connects the OpenAI SDK to the Hugging Face Inference Router
        self.client = AsyncOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=HUGGINGFACE_API_KEY
        )

    def get_system_prompt(self, mode: str) -> str:
        """Returns the system prompt based on the selected personality mode."""
        prompts = {
            "assistant": "You are a helpful, precise, and polite assistant.",
            "sarcastic": "You are a witty, sarcastic, and slightly rude companion.",
            "anime": "You are an energetic anime character. End your sentences with 'nya'!",
            "tech_expert": "You are a senior software engineer and tech expert. Be precise.",
            "translator": "You are a translator. Translate the user's input into English.",
            "ask_anything": "You are a creative AI, answer any question freely."
        }
        return prompts.get(mode, prompts["assistant"])

    async def chat_response(self, prompt: str, mode: str, model: str) -> str:
        """Gets a response using the Hugging Face Router."""
        system_prompt = self.get_system_prompt(mode)
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI Error: {e}")
            if "401" in str(e):
                return "❌ Error: Invalid API Token. Please check your Hugging Face API Key."
            if "503" in str(e):
                return "⏳ Model is currently loading on the server. Please wait 30 seconds and try again."
            return f"⚠️ An unknown AI error occurred: {type(e).__name__}"

    async def analyze_text(self, text: str, action: str, model: str) -> str:
        """Performs text analysis (Summarize, Translate, etc.)."""
        instructions = {
            "summarize": "Summarize the following text concisely:",
            "explain": "Explain this concept simply:",
            "improve": "Rewrite this text to be more professional:",
            "sentiment": "Analyze the sentiment (Positive/Negative) of:",
            "translate": "Translate this text into English:"
        }
        prompt = f"{instructions.get(action, 'Analyze:')} \n\n{text}"
        return await self.chat_response(prompt, "assistant", model)


# Global instance of the AI client
AI_CLIENT = HuggingFaceClient()

# --- Embed Colors and Styles ---
COLOR_NEON_PURPLE = 0x8A2BE2
COLOR_SUCCESS = 0x32CD32
COLOR_WARNING = 0xFF4500

MODE_MAP = {
    "assistant": "💼 Assistant",
    "sarcastic": "😈 Sarcastic",
    "anime": "🌸 Anime-Style",
    "tech_expert": "💻 Tech Expert",
    "translator": "🌍 Translator",
    "ask_anything": "⭐ Ask Anything",
}

# Supported Models on the Hugging Face Router (Free Tier friendly)
MODEL_MAP = {
    "meta-llama/Llama-3.1-8B-Instruct": "Llama 3.1 (Recommended)", 
    "mistralai/Mistral-7B-Instruct-v0.3": "Mistral 7B (Fast)",
    "moonshotai/Kimi-K2-Instruct-0905": "Kimi K2 (Your Model)"
}

# --- Utility Functions (Config) ---
def load_config() -> Dict[str, Any]:
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump({}, f)
    with open(CONFIG_FILE, 'r') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return {}
def save_config(config: Dict[str, Any]):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f, indent=4)
def get_guild_config(guild_id: int) -> Dict[str, Any]:
    config = load_config(); guild_id_str = str(guild_id)
    if guild_id_str not in config:
        config[guild_id_str] = {
            "ai_chat_enabled": False, "ai_channel": None, "automod": False,
            "mode": "assistant", "model": "meta-llama/Llama-3.1-8B-Instruct"
        }
        save_config(config)
    return config[guild_id_str]
def update_guild_config(guild_id: int, key: str, value: Any):
    config = load_config(); guild_id_str = str(guild_id)
    if guild_id_str not in config: get_guild_config(guild_id); config = load_config()
    config[guild_id_str][key] = value
    save_config(config)

# --- UI Components ---

class SettingsDropdown(ui.Select):
    def __init__(self, guild_id: int, config_key: str, options: Dict[str, str], placeholder: str, row: int):
        self.guild_id = guild_id
        self.config_key = config_key
        current_value = get_guild_config(guild_id).get(config_key)
        
        select_options = []
        for value, label in options.items():
            select_options.append(discord.SelectOption(
                label=label, value=value, default=(value == current_value)
            ))
        super().__init__(placeholder=placeholder, options=select_options, row=row)

    async def callback(self, interaction: discord.Interaction):
        update_guild_config(self.guild_id, self.config_key, self.values[0])
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ Setting updated.", ephemeral=True)

class AIPanelView(ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id

    def create_dashboard_embed(self) -> discord.Embed:
        config = get_guild_config(self.guild_id)
        status = "✅ Enabled" if config['ai_chat_enabled'] else "❌ Disabled"
        channel = f"<#{config['ai_channel']}>" if config['ai_channel'] else "Not Set"
        
        embed = discord.Embed(
            title="✨ AI CONTROL PANEL", 
            description="Manage your AI Chatbot settings.", 
            color=COLOR_NEON_PURPLE
        )
        embed.add_field(name="Chat Status", value=status, inline=True)
        embed.add_field(name="Active Channel", value=channel, inline=True)
        embed.add_field(name="Current Model", value=f"`{config['model']}` (Hugging Face Free)", inline=False)
        return embed

    @ui.button(label="Toggle Chat", style=discord.ButtonStyle.primary, emoji="💬", row=1)
    async def toggle_chat(self, interaction: discord.Interaction, button: ui.Button):
        config = get_guild_config(self.guild_id)
        update_guild_config(self.guild_id, 'ai_chat_enabled', not config['ai_chat_enabled'])
        await interaction.response.edit_message(embed=self.create_dashboard_embed(), view=self)

    @ui.button(label="AI Settings", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
    async def config_menu(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            embed=self.create_dashboard_embed(), 
            view=AISettingsView(self.bot, self.guild_id)
        )

    @ui.button(label="Set Channel", style=discord.ButtonStyle.success, emoji="#️⃣", row=2)
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ChannelSetterModal(self.guild_id))

class AISettingsView(ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild_id = guild_id
        
        self.add_item(SettingsDropdown(guild_id, 'mode', MODE_MAP, "Select Personality", 0))
        self.add_item(SettingsDropdown(guild_id, 'model', MODEL_MAP, "Select AI Model", 1))

    @ui.button(label="Back", style=discord.ButtonStyle.grey, row=2)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        dashboard = AIPanelView(interaction.client, self.guild_id)
        await interaction.response.edit_message(embed=dashboard.create_dashboard_embed(), view=dashboard)

class ChannelSetterModal(ui.Modal, title='Set Chat Channel'):
    channel_input = ui.TextInput(label="Channel ID", placeholder="Paste the Channel ID here", min_length=15, max_length=20)
    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            cid = int(self.channel_input.value)
            channel = interaction.guild.get_channel(cid)
            if channel:
                update_guild_config(self.guild_id, 'ai_channel', cid)
                await interaction.response.send_message(f"✅ AI Chat bound to {channel.mention}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Channel not found in this server.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid ID format.", ephemeral=True)

# --- Cog Implementation ---
class SentinelAI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.exists('data'): os.makedirs('data')
        load_config()

    @commands.command(name="aipanel")
    @commands.has_permissions(manage_guild=True)
    async def aipanel_prefix(self, ctx):
        if not ctx.guild: return
        dashboard = AIPanelView(self.bot, ctx.guild.id)
        await ctx.send(embed=dashboard.create_dashboard_embed(), view=dashboard)

    @app_commands.command(name="aipanel", description="Open AI Dashboard")
    @app_commands.default_permissions(manage_guild=True)
    async def aipanel_slash(self, interaction: discord.Interaction):
        if not interaction.guild: return
        dashboard = AIPanelView(self.bot, interaction.guild_id)
        await interaction.response.send_message(embed=dashboard.create_dashboard_embed(), view=dashboard, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        
        config = get_guild_config(message.guild.id)
        
        # Check if chat is enabled and correct channel
        if config.get('ai_chat_enabled') and config.get('ai_channel') == message.channel.id:
            async with message.channel.typing():
                try:
                    response = await AI_CLIENT.chat_response(message.content, config['mode'], config['model'])
                    await message.reply(response, mention_author=False)
                except Exception as e:
                    print(f"Error: {e}") 

async def setup(bot: commands.Bot):
    await bot.add_cog(SentinelAI(bot))
