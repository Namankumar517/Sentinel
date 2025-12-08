# shop.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
from typing import Optional, Dict, Any
from discord.ext.commands import Context

# ------------------------------------------------------
# 📁 File Path & Configuration Setup
# ------------------------------------------------------
SHOP_FILE = "data/shop.json"
SHOP_CATEGORY_NAME = "🛒 Transactions"  
PERMISSION_ROLE_NAME = "Shop Staff"    

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# Define the default structure for safety
DEFAULT_SHOP_DATA: Dict[str, Any] = {
    "next_item_id": 1,
    "items": {} 
}

# Load shop data or initialize empty 
shop_data = DEFAULT_SHOP_DATA.copy() 

def load_data():
    """Loads data from the JSON file into the global shop_data."""
    global shop_data
    if os.path.exists(SHOP_FILE):
        try:
            with open(SHOP_FILE, "r") as f:
                loaded_data = json.load(f)
                if all(key in loaded_data for key in DEFAULT_SHOP_DATA):
                    shop_data = loaded_data
                else:
                    shop_data = DEFAULT_SHOP_DATA.copy()
        except (json.JSONDecodeError, Exception):
            shop_data = DEFAULT_SHOP_DATA.copy()
    else:
        shop_data = DEFAULT_SHOP_DATA.copy()
        
load_data() # Initial load

def save_data():
    """Saves the current global shop_data to the JSON file."""
    global shop_data
    with open(SHOP_FILE, "w") as f:
        json.dump(shop_data, f, indent=4)

# ------------------------------------------------------
# --- Shop Cog Implementation ---
# ------------------------------------------------------
class Shop(commands.Cog):
    """The Shop system for buying and selling items."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def premium_embed(self, title: str, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        """Standardized embed creator for the shop module."""
        embed = discord.Embed(
            title=f"🛒 {title}",
            description=description,
            color=color
        )
        embed.set_footer(text="Sentinel Marketplace Protocol")
        return embed

    def get_transaction_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """Finds the dedicated transaction category."""
        for category in guild.categories:
            if category.name == SHOP_CATEGORY_NAME:
                return category
        return None 
        
    # --- Helper for Response Context ---
    async def _send_response(self, context: discord.Interaction | commands.Context, content: Optional[str] = None, embed: Optional[discord.Embed] = None, ephemeral: bool = False):
        """Sends the response based on whether it's a slash or prefix context."""
        if isinstance(context, discord.Interaction):
            if context.response.is_done():
                await context.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            else:
                await context.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        else:
            await context.reply(content=content, embed=embed)

    # ------------------------------------------------------
    # 1. LIST ITEM COMMAND (Seller Command - /list, !list)
    # ------------------------------------------------------

    @app_commands.command(name="list", description="List an item for sale in the shop.")
    @app_commands.describe(name="The name of the item you are selling.", price="The price in credits/currency.", description="A detailed description of the item.", image_url="Optional link to an image of the item.")
    async def list_item_slash(self, interaction: discord.Interaction, name: str, price: int, description: str, image_url: Optional[str] = None):
        """Slash command version."""
        await self._list_item_logic(interaction, name, price, description, image_url)
    
    @commands.command(name="list", help="List an item for sale in the shop.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def list_item_prefix(self, ctx: commands.Context, name: str, price: int, description: str, image_url: Optional[str] = None):
        """Prefix command version."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        await self._list_item_logic(ctx, name, price, description, image_url)
    
    async def _list_item_logic(self, context: discord.Interaction | commands.Context, name: str, price: int, description: str, image_url: Optional[str]):
        """Core logic for listing an item."""
        global shop_data 
        
        is_slash = isinstance(context, discord.Interaction)
        user = context.user if is_slash else context.author
        
        if price <= 0:
            embed = self.premium_embed("Listing Error", "Price must be a positive number.", discord.Color.red())
            await self._send_response(context, embed=embed, ephemeral=is_slash)
            return

        if image_url and not (image_url.startswith('http://') or image_url.startswith('https://')):
            embed = self.premium_embed("Listing Error", "Image URL must be a valid HTTP/HTTPS link.", discord.Color.red())
            await self._send_response(context, embed=embed, ephemeral=is_slash)
            return

        item_id = str(shop_data["next_item_id"])
        
        # Add item data
        shop_data["items"][item_id] = {
            "seller_id": str(user.id),
            "name": name,
            "price": price,
            "description": description,
            "image_url": image_url,
            "timestamp": datetime.datetime.now().isoformat(),
            "transaction_channel_id": None
        }

        # Increment next item ID
        shop_data["next_item_id"] += 1
        save_data() 

        embed = self.premium_embed(
            f"Item Listed! | ID: #{item_id}",
            f"**{name}** has been added to the shop for **${price:,}** credits.",
            discord.Color.green()
        )
        embed.add_field(name="Description", value=description, inline=False)
        embed.set_thumbnail(url=image_url or user.display_avatar.url)

        await self._send_response(context, embed=embed)
    
    # ------------------------------------------------------
    # 2. SHOP DISPLAY COMMAND (Buyer Command - /shop, !shop)
    # ------------------------------------------------------

    @app_commands.command(name="shop", description="Displays all items currently listed for sale.")
    async def shop_display_slash(self, interaction: discord.Interaction):
        """Slash command version."""
        await self._shop_display_logic(interaction)
        
    @commands.command(name="shop", help="Displays all items currently listed for sale.")
    async def shop_display_prefix(self, ctx: commands.Context):
        """Prefix command version."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        await self._shop_display_logic(ctx)

    async def _shop_display_logic(self, context: discord.Interaction | commands.Context):
        """Core logic for displaying the shop."""
        global shop_data
        
        is_slash = isinstance(context, discord.Interaction)
        
        items = shop_data["items"]
        if not items:
            embed = self.premium_embed("Shop is Empty", "No items are currently listed for sale.", discord.Color.orange())
            await self._send_response(context, embed=embed, ephemeral=is_slash)
            return
            
        embed = self.premium_embed(
            "Welcome to the Sentinel Marketplace",
            f"There are **{len(items)}** active listings. Use `/buy <ID>` or `!buy <ID>` to initiate a purchase."
        )
        embed.set_thumbnail(url=context.client.user.display_avatar.url)

        current_description = ""
        items_count = 0
        
        for item_id, item in items.items():
            guild = context.guild if context.guild else self.bot.get_guild(context.guild_id) # Safe access
            seller = guild.get_member(int(item['seller_id'])) if guild else None
            seller_name = seller.mention if seller else f"Unknown User (`{item['seller_id']}`)"

            item_block = (
                f"**ID: #{item_id}**\n"
                f"**Item:** `{item['name']}`\n"
                f"**Price:** **${item['price']:,}**\n"
                f"**Seller:** {seller_name}\n"
                f"**Description:** *{item['description']}*\n"
                f"{'Image: [Link]' if item['image_url'] else ''}\n"
            )
            
            # Use a reasonable limit for a single message description
            if len(current_description) + len(item_block) > 3500 or items_count >= 10:
                break
            
            current_description += item_block + "\n"
            items_count += 1

        embed.description = current_description or "No items could be displayed."
        
        await self._send_response(context, embed=embed)


    # ------------------------------------------------------
    # 3. BUY ITEM COMMAND (Buyer Command - /buy, !buy)
    # ------------------------------------------------------

    @app_commands.command(name="buy", description="Initiates a purchase of a listed item.")
    @app_commands.describe(item_id="The ID of the item to purchase (e.g., 5).")
    async def buy_item_slash(self, interaction: discord.Interaction, item_id: str):
        """Slash command version."""
        await self._buy_item_logic(interaction, item_id)
        
    @commands.command(name="buy", help="Initiates a purchase of a listed item.")
    async def buy_item_prefix(self, ctx: commands.Context, item_id: str):
        """Prefix command version."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        await self._buy_item_logic(ctx, item_id)
        
    async def _buy_item_logic(self, context: discord.Interaction | commands.Context, item_id: str):
        """Core logic for buying an item."""
        global shop_data
        is_slash = isinstance(context, discord.Interaction)
        
        guild = context.guild
        buyer = context.user if is_slash else context.author
        
        # 1. Validation Checks
        if item_id not in shop_data["items"]:
            embed = self.premium_embed("Transaction Failed", f"Item ID **#{item_id}** not found.", discord.Color.red())
            await self._send_response(context, embed=embed, ephemeral=is_slash)
            return

        item = shop_data["items"][item_id]
        seller_id = int(item['seller_id'])

        if buyer.id == seller_id:
            embed = self.premium_embed("Transaction Failed", "You cannot purchase your own item!", discord.Color.red())
            await self._send_response(context, embed=embed, ephemeral=is_slash)
            return
        
        if item['transaction_channel_id']:
            existing_channel = guild.get_channel(item['transaction_channel_id'])
            if existing_channel:
                embed = self.premium_embed("Transaction In Progress", f"A transaction channel for this item already exists: {existing_channel.mention}", discord.Color.orange())
                await self._send_response(context, embed=embed, ephemeral=is_slash)
                return

        # 2. Get/Create Category
        category = self.get_transaction_category(guild)
        if not category:
            try:
                category = await guild.create_category(
                    SHOP_CATEGORY_NAME, 
                    reason="Shop Transaction Category"
                )
            except discord.Forbidden:
                embed = self.premium_embed("Permission Error", "I lack the `Manage Channels` permission to create the transaction category.", discord.Color.red())
                await self._send_response(context, embed=embed, ephemeral=is_slash)
                return
        
        # 3. Create Permissions (Allow Seller, Buyer, and Staff role)
        seller = guild.get_member(seller_id)
        shop_staff_role = discord.utils.get(guild.roles, name=PERMISSION_ROLE_NAME)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            buyer: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        if seller:
             overwrites[seller] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if shop_staff_role:
             overwrites[shop_staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # 4. Create Channel
        try:
            channel = await guild.create_text_channel(
                name=f"t-{item_id}-{item['name'].lower().replace(' ', '-')[:20]}",
                category=category,
                overwrites=overwrites,
                reason=f"Transaction for item {item_id} requested by {buyer.name}"
            )
            
            # 5. Update Data
            shop_data["items"][item_id]['transaction_channel_id'] = channel.id
            save_data()

            # 6. Send Initial Messages
            seller_mention = seller.mention if seller else f"<@{seller_id}>"
            
            embed = self.premium_embed(
                f"Transaction Channel for #{item_id} Created!",
                f"**{buyer.mention}** has expressed interest in buying **{item['name']}** from **{seller_mention}** for **${item['price']:,}** credits."
            )
            embed.add_field(name="Next Steps", value="Both parties should discuss the final price, delivery method, and payment. Staff may monitor for issues.")
            embed.add_field(name="Close Command", value=f"**{seller_mention}** or Staff can run `/sold {item_id}` or `!sold {item_id}` to close this channel once the trade is complete.", inline=False)
            
            await channel.send(f"{buyer.mention} {seller_mention} {shop_staff_role.mention if shop_staff_role else ''}", embed=embed)
            
            # 7. Confirmation Response
            confirm_embed = self.premium_embed("Transaction Channel Opened", f"The transaction channel is ready! Go to {channel.mention} to proceed with the purchase.", discord.Color.blue())
            await self._send_response(context, embed=confirm_embed, ephemeral=is_slash)

        except discord.Forbidden:
            error_embed = self.premium_embed("Permission Error", "I lack the permissions to create channels or manage permissions within the category.", discord.Color.red())
            await self._send_response(context, embed=error_embed, ephemeral=is_slash)
            
    # ------------------------------------------------------
    # 4. SOLD COMMAND (Seller/Staff Command - /sold, !sold)
    # ------------------------------------------------------

    @commands.command(name="sold", help="Marks an item as sold and closes the transaction channel.")
    @commands.has_permissions(manage_channels=True)
    async def sold_prefix(self, ctx: commands.Context, item_id: str):
        """Prefix command version."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server.")
            return
        await self._sold_logic(ctx, item_id)

    @app_commands.command(name="sold", description="Marks an item as sold and closes the transaction channel.")
    @app_commands.describe(item_id="The ID of the item that was sold (e.g., 5).")
    @app_commands.default_permissions(manage_channels=True)
    async def sold_slash(self, interaction: discord.Interaction, item_id: str):
        """Slash command version."""
        await self._sold_logic(interaction, item_id)
        
    async def _sold_logic(self, context: discord.Interaction | commands.Context, item_id: str):
        """Core logic for marking an item as sold."""
        global shop_data
        is_slash = isinstance(context, discord.Interaction)
        
        guild = context.guild
        author = context.user if is_slash else context.author
        
        # Defer the slash interaction immediately as channel deletion takes time
        if is_slash and not context.response.is_done():
            await context.response.defer(thinking=True, ephemeral=True) 
        
        # 1. Validation Checks
        if item_id not in shop_data["items"]:
            embed = self.premium_embed("Completion Failed", f"Item ID **#{item_id}** not found in active listings.", discord.Color.red())
            await self._send_response(context, embed=embed)
            return

        item = shop_data["items"][item_id]
        seller_id = int(item['seller_id'])
        
        member = guild.get_member(author.id) if guild else None
        
        is_seller = author.id == seller_id
        is_staff = member and member.guild_permissions.manage_channels
        
        if not (is_seller or is_staff):
            embed = self.premium_embed("Permission Denied", "Only the original seller or a Staff member can mark this item as sold.", discord.Color.red())
            await self._send_response(context, embed=embed)
            return
            
        # 2. Channel Deletion Logic
        channel_id = item["transaction_channel_id"]

        if not channel_id:
            embed = self.premium_embed("Completion Failed", f"Item **#{item_id}** does not have an active transaction channel.", discord.Color.orange())
            await self._send_response(context, embed=embed)
            return
            
        transaction_channel = None
        try:
             # Use fetch_channel for reliability
             transaction_channel = await self.bot.fetch_channel(channel_id)
        except discord.NotFound:
             pass # Channel was already deleted

        if transaction_channel:
            # Send a final message before deleting
            final_embed = self.premium_embed(
                "✅ Transaction Complete",
                f"Item **{item['name']}** has been marked as sold by **{author.name}**. This channel will close in a few seconds.",
                discord.Color.dark_green()
            )
            
            try:
                await transaction_channel.send(embed=final_embed)
            except: 
                pass # Ignore if channel is inaccessible

            # Delete the channel
            try:
                await transaction_channel.delete(reason=f"Item #{item_id} sold by {author.name}")
            except discord.Forbidden:
                error_embed = self.premium_embed("Permission Error", "I lack `Manage Channels` permission to delete the transaction channel.", discord.Color.red())
                await self._send_response(context, embed=error_embed)
                return 

        # 3. Data update: Permanently remove the item from the listings
        del shop_data["items"][item_id]
        save_data()
        
        # 4. Public confirmation
        final_confirmation_embed = self.premium_embed(
            "Item Sold & Channel Closed",
            f"Item **#{item_id} ({item['name']})** has been removed from the shop and the transaction channel is closed.",
            discord.Color.dark_green()
        )
        await self._send_response(context, embed=final_confirmation_embed)


# ------------------------------------------------------
# 🔧 SETUP FUNCTION
# ------------------------------------------------------
async def setup(bot):
    """Adds the Shop cog to the bot."""
    await bot.add_cog(Shop(bot))
