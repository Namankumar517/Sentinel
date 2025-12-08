import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp
from typing import Optional

class FunGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.upside_down_chars = {
            'a': 'ɐ', 'b': 'q', 'c': 'ɔ', 'd': 'p', 'e': 'ǝ', 'f': 'ɟ', 'g': 'ƃ', 'h': 'ɥ',
            'i': 'ᴉ', 'j': 'ɾ', 'k': 'ʞ', 'l': 'l', 'm': 'ɯ', 'n': 'u', 'o': 'o', 'p': 'd',
            'q': 'b', 'r': 'ɹ', 's': 's', 't': 'ʇ', 'u': 'n', 'v': 'ʌ', 'w': 'ʍ', 'x': 'x',
            'y': 'ʎ', 'z': 'z', 'A': '∀', 'B': 'q', 'C': 'Ɔ', 'D': 'p', 'E': 'Ǝ', 'F': 'Ⅎ',
            'G': 'פ', 'H': 'H', 'I': 'I', 'J': 'ſ', 'K': 'ʞ', 'L': '˥', 'M': 'W', 'N': 'N',
            'O': 'O', 'P': 'd', 'Q': 'b', 'R': 'ɹ', 'S': 'S', 'T': '┴', 'U': '∩', 'V': 'Λ',
            'W': 'M', 'X': 'X', 'Y': '⅄', 'Z': 'Z', '?': '¿', '!': '¡'
        }

    def premium_embed(self, title: str, description: str, color=discord.Color.blurple()):
        embed = discord.Embed(title=f"🎮 {title}", description=description, color=color, timestamp=discord.utils.utcnow())
        if self.bot.user:
            embed.set_footer(text=f"Fun & Games | {self.bot.user.name}", icon_url=self.bot.user.display_avatar.url)
        return embed

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question for the magic 8-ball")
    async def eightball(self, ctx: commands.Context, *, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes definitely.",
            "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
            "Yes.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.",
            "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]
        embed = self.premium_embed("Magic 8-Ball 🎱", f"**Question:** {question}\n\n**Answer:** {random.choice(responses)}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="coinflip", description="Flip a virtual coin")
    async def coinflip(self, ctx: commands.Context):
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙"
        embed = self.premium_embed("Coin Flip", f"{emoji} The coin landed on **{result}**!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roll", description="Roll a dice")
    @app_commands.describe(sides="Number of sides (default: 6)")
    async def roll(self, ctx: commands.Context, sides: int = 6):
        if sides < 2:
            sides = 6
        result = random.randint(1, sides)
        embed = self.premium_embed("Dice Roll 🎲", f"You rolled a **{result}** on a {sides}-sided dice!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rps", description="Play Rock Paper Scissors")
    @app_commands.describe(choice="Your choice: rock, paper, or scissors")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Rock", value="rock"),
        app_commands.Choice(name="Paper", value="paper"),
        app_commands.Choice(name="Scissors", value="scissors")
    ])
    async def rps(self, ctx: commands.Context, choice: str):
        choice = choice.lower()
        if choice not in ["rock", "paper", "scissors"]:
            return await ctx.send("Please choose rock, paper, or scissors!", ephemeral=True)
        
        bot_choice = random.choice(["rock", "paper", "scissors"])
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        if choice == bot_choice:
            result = "It's a tie!"
            color = discord.Color.yellow()
        elif (choice == "rock" and bot_choice == "scissors") or \
             (choice == "paper" and bot_choice == "rock") or \
             (choice == "scissors" and bot_choice == "paper"):
            result = "You win! 🎉"
            color = discord.Color.green()
        else:
            result = "You lose! 😢"
            color = discord.Color.red()
        
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors",
            description=f"You chose: {emojis[choice]} **{choice.title()}**\nI chose: {emojis[bot_choice]} **{bot_choice.title()}**\n\n**{result}**",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="truth", description="Get a random truth question")
    async def truth(self, ctx: commands.Context):
        truths = [
            "What's the most embarrassing thing you've done?",
            "What's your biggest fear?",
            "Have you ever lied to your best friend?",
            "What's your biggest regret?",
            "What's a secret you've never told anyone?",
            "Who was your first crush?",
            "What's the worst thing you've done at school/work?",
            "Have you ever cheated on a test?",
            "What's your most embarrassing memory?",
            "What's your biggest insecurity?",
            "Have you ever stolen something?",
            "What's the worst lie you've ever told?",
            "Who do you secretly dislike?",
            "What's the most childish thing you still do?",
            "What's a habit you're ashamed of?",
        ]
        embed = self.premium_embed("Truth 🤔", random.choice(truths))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="dare", description="Get a random dare challenge")
    async def dare(self, ctx: commands.Context):
        dares = [
            "Text someone you haven't talked to in years!",
            "Do 10 push-ups right now!",
            "Sing a song for 30 seconds!",
            "Talk in an accent for the next 5 minutes!",
            "Do your best celebrity impression!",
            "Send a weird selfie to someone!",
            "Let someone post on your social media!",
            "Do a silly dance!",
            "Call someone and sing happy birthday!",
            "Speak only in questions for 10 minutes!",
            "Post an embarrassing photo!",
            "Do 20 jumping jacks!",
            "Talk like a robot for 5 minutes!",
            "Let someone read your recent messages!",
            "Imitate another player until someone guesses who!",
        ]
        embed = self.premium_embed("Dare 😈", random.choice(dares))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="joke", description="Get a random joke")
    async def joke(self, ctx: commands.Context):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = self.premium_embed("Random Joke 😂", f"**{data['setup']}**\n\n||{data['punchline']}||")
                        return await ctx.send(embed=embed)
        except:
            pass
        
        jokes = [
            ("Why don't scientists trust atoms?", "Because they make up everything!"),
            ("Why did the scarecrow win an award?", "He was outstanding in his field!"),
            ("Why don't eggs tell jokes?", "They'd crack each other up!"),
            ("What do you call a fake noodle?", "An impasta!"),
            ("Why did the bicycle fall over?", "Because it was two-tired!"),
        ]
        setup, punchline = random.choice(jokes)
        embed = self.premium_embed("Random Joke 😂", f"**{setup}**\n\n||{punchline}||")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="dadjoke", description="Get a random dad joke")
    async def dadjoke(self, ctx: commands.Context):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/json"}
                async with session.get("https://icanhazdadjoke.com/", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = self.premium_embed("Dad Joke 👴", data["joke"])
                        return await ctx.send(embed=embed)
        except:
            pass
        
        jokes = [
            "I'm reading a book about anti-gravity. It's impossible to put down!",
            "I used to hate facial hair, but then it grew on me.",
            "What do you call cheese that isn't yours? Nacho cheese!",
            "I'm on a seafood diet. I see food and I eat it!",
        ]
        embed = self.premium_embed("Dad Joke 👴", random.choice(jokes))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="meme", description="Get a random meme")
    async def meme(self, ctx: commands.Context):
        await ctx.defer()
        subreddits = ["memes", "dankmemes", "me_irl", "wholesomememes"]
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://meme-api.com/gimme/{random.choice(subreddits)}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = discord.Embed(
                            title=data.get("title", "Random Meme")[:256],
                            color=discord.Color.random(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_image(url=data.get("url"))
                        embed.set_footer(text=f"👍 {data.get('ups', 0)} | r/{data.get('subreddit', 'memes')}")
                        return await ctx.send(embed=embed)
        except:
            pass
        
        embed = self.premium_embed("Meme", "Couldn't fetch a meme right now. Try again later!", discord.Color.red())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="fact", description="Get a random interesting fact")
    async def fact(self, ctx: commands.Context):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/api/v2/facts/random") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = self.premium_embed("Random Fact 🤓", data.get("text", "No fact found"))
                        return await ctx.send(embed=embed)
        except:
            pass
        
        facts = [
            "Honey never spoils. Archaeologists have found 3000-year-old honey in Egyptian tombs that was still edible!",
            "A group of flamingos is called a 'flamboyance'.",
            "The shortest war in history lasted 38 minutes between Britain and Zanzibar.",
            "Octopuses have three hearts and blue blood.",
            "Bananas are berries, but strawberries aren't.",
        ]
        embed = self.premium_embed("Random Fact 🤓", random.choice(facts))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="quote", description="Get an inspirational quote")
    async def quote(self, ctx: commands.Context):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.quotable.io/random") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embed = self.premium_embed("Inspirational Quote 💡", f"*\"{data['content']}\"*\n\n— **{data['author']}**")
                        return await ctx.send(embed=embed)
        except:
            pass
        
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
        ]
        q, a = random.choice(quotes)
        embed = self.premium_embed("Inspirational Quote 💡", f"*\"{q}\"*\n\n— **{a}**")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="choose", description="Let me choose between options for you")
    @app_commands.describe(options="Options separated by commas (e.g., pizza, burger, pasta)")
    async def choose(self, ctx: commands.Context, *, options: str):
        choices = [c.strip() for c in options.split(",") if c.strip()]
        if len(choices) < 2:
            return await ctx.send("Give me at least 2 options separated by commas!", ephemeral=True)
        
        chosen = random.choice(choices)
        embed = self.premium_embed("I Choose... 🤔", f"From: {', '.join(choices)}\n\nI pick: **{chosen}**!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rate", description="Rate something out of 10")
    @app_commands.describe(thing="What should I rate?")
    async def rate(self, ctx: commands.Context, *, thing: str):
        rating = random.randint(0, 10)
        if rating == 0:
            comment = "Absolutely terrible... 💀"
        elif rating <= 3:
            comment = "Not great... 😬"
        elif rating <= 5:
            comment = "It's okay I guess 🤷"
        elif rating <= 7:
            comment = "Pretty decent! 👍"
        elif rating <= 9:
            comment = "Very nice! 🔥"
        else:
            comment = "PERFECT! 10/10! 🌟"
        
        embed = self.premium_embed("Rating Machine 📊", f"I rate **{thing}** a **{rating}/10**!\n\n{comment}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ship", description="Ship two users together")
    @app_commands.describe(user1="First person", user2="Second person (optional, defaults to you)")
    async def ship(self, ctx: commands.Context, user1: discord.Member, user2: Optional[discord.Member] = None):
        user2 = user2 or ctx.author
        
        seed = min(user1.id, user2.id) + max(user1.id, user2.id)
        rng = random.Random(seed)
        percentage = rng.randint(0, 100)
        
        if percentage < 25:
            status = "Not a good match... 💔"
            bar = "▓░░░░░░░░░"
        elif percentage < 50:
            status = "There's potential! 💛"
            bar = "▓▓▓░░░░░░░"
        elif percentage < 75:
            status = "A great match! 💕"
            bar = "▓▓▓▓▓▓░░░░"
        elif percentage < 100:
            status = "Perfect couple! 💞"
            bar = "▓▓▓▓▓▓▓▓░░"
        else:
            status = "SOULMATES! 💖"
            bar = "▓▓▓▓▓▓▓▓▓▓"
        
        name1 = user1.display_name[:len(user1.display_name)//2]
        name2 = user2.display_name[len(user2.display_name)//2:]
        ship_name = name1 + name2
        
        embed = discord.Embed(
            title="💕 Love Calculator 💕",
            description=f"{user1.mention} ❤️ {user2.mention}\n\n"
                       f"**Ship Name:** {ship_name}\n"
                       f"**Compatibility:** {percentage}%\n"
                       f"[{bar}]\n\n"
                       f"**Status:** {status}",
            color=discord.Color.pink(),
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="howgay", description="Check the gay-o-meter (for fun)")
    @app_commands.describe(member="User to check")
    async def howgay(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        seed = str(member.id) + "gay"
        value = random.Random(seed).randint(0, 100)
        
        bar = "▓" * (value // 10) + "░" * (10 - value // 10)
        
        embed = discord.Embed(
            title="🏳️‍🌈 Gay-O-Meter",
            description=f"{member.mention} is **{value}%** gay!\n\n[{bar}]",
            color=discord.Color.random(),
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="iq", description="Check someone's IQ (for fun)")
    @app_commands.describe(member="User to check")
    async def iq(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        seed = str(member.id) + "iq"
        value = random.Random(seed).randint(50, 180)
        
        if value < 70:
            comment = "Hmm... 🤔"
        elif value < 100:
            comment = "Average!"
        elif value < 130:
            comment = "Smart! 🧠"
        elif value < 150:
            comment = "Genius! 🌟"
        else:
            comment = "Big brain! 🧠✨"
        
        embed = self.premium_embed("IQ Test 🧠", f"{member.mention}'s IQ is **{value}**!\n\n{comment}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="luck", description="Check someone's luck percentage")
    @app_commands.describe(member="User to check")
    async def luck(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        seed = str(member.id) + "luck"
        value = random.Random(seed).randint(0, 100)
        
        if value < 25:
            comment = "Unlucky... 🍀"
        elif value < 50:
            comment = "Could be better!"
        elif value < 75:
            comment = "Pretty lucky! 🍀"
        else:
            comment = "Super lucky! 🍀✨"
        
        embed = self.premium_embed("Luck-O-Meter 🍀", f"{member.mention} has **{value}%** luck!\n\n{comment}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="say", description="Make the bot say something")
    @app_commands.describe(message="What should I say?")
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, *, message: str):
        try:
            if ctx.interaction is None:
                await ctx.message.delete()
        except:
            pass
        await ctx.send(message)

    @commands.hybrid_command(name="reverse", description="Reverse your text")
    @app_commands.describe(text="Text to reverse")
    async def reverse(self, ctx: commands.Context, *, text: str):
        embed = self.premium_embed("Reversed Text 🔄", f"Original: `{text}`\nReversed: `{text[::-1]}`")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="mock", description="SpOnGeBoB mOcK text")
    @app_commands.describe(text="Text to mock")
    async def mock(self, ctx: commands.Context, *, text: str):
        mocked = ''.join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text))
        embed = self.premium_embed("Mocking SpongeBob 🧽", mocked)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="flip", description="Flip text upside down")
    @app_commands.describe(text="Text to flip")
    async def flip(self, ctx: commands.Context, *, text: str):
        flipped = ''.join(self.upside_down_chars.get(c, c) for c in text[::-1])
        embed = self.premium_embed("Flipped Text 🙃", f"Original: `{text}`\nFlipped: `{flipped}`")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clap", description="Add clap emojis between words")
    @app_commands.describe(text="Text to clapify")
    async def clap(self, ctx: commands.Context, *, text: str):
        clapped = " 👏 ".join(text.split())
        embed = self.premium_embed("Clapified 👏", clapped)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="wyr", description="Would you rather...")
    async def wyr(self, ctx: commands.Context):
        scenarios = [
            ("Be able to fly", "Be able to turn invisible"),
            ("Live without music", "Live without movies"),
            ("Have unlimited money", "Have unlimited time"),
            ("Be too hot", "Be too cold"),
            ("Know how you'll die", "Know when you'll die"),
            ("Never use social media again", "Never watch TV again"),
            ("Have a rewind button", "Have a pause button"),
            ("Be famous but unhappy", "Be unknown but happy"),
            ("Live in the past", "Live in the future"),
            ("Have super strength", "Have super speed"),
        ]
        opt1, opt2 = random.choice(scenarios)
        
        embed = discord.Embed(
            title="Would You Rather? 🤔",
            description=f"**A)** {opt1}\n\n**or**\n\n**B)** {opt2}",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="Reply with A or B!")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roast", description="Get a random roast")
    @app_commands.describe(member="User to roast")
    async def roast(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        roasts = [
            f"{member.mention}, you're like a cloud. When you disappear, it's a beautiful day.",
            f"I'd agree with you {member.mention}, but then we'd both be wrong.",
            f"{member.mention}, you bring everyone so much joy when you leave.",
            f"I'm not saying I hate you {member.mention}, but I would unplug your life support to charge my phone.",
            f"{member.mention}, if you were any more inbred, you'd be a sandwich.",
            f"{member.mention}, you're the reason God created the middle finger.",
            f"I'd explain it to you {member.mention}, but I don't have any crayons.",
            f"{member.mention}, somewhere out there is a tree working hard to produce oxygen for you. I think you owe it an apology.",
        ]
        embed = self.premium_embed("Roasted 🔥", random.choice(roasts))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="compliment", description="Get a random compliment")
    @app_commands.describe(member="User to compliment")
    async def compliment(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        compliments = [
            f"{member.mention}, you're more helpful than you realize!",
            f"{member.mention}, you have the best laugh!",
            f"{member.mention}, you light up any room you enter!",
            f"{member.mention}, you're someone's reason to smile!",
            f"{member.mention}, you're more fun than bubble wrap!",
            f"{member.mention}, your creativity is inspiring!",
            f"{member.mention}, you make the world a better place!",
            f"{member.mention}, you're like a ray of sunshine!",
        ]
        embed = self.premium_embed("Compliment 💕", random.choice(compliments))
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="affirmation", description="Get a positive affirmation")
    async def affirmation(self, ctx: commands.Context):
        affirmations = [
            "You are capable of amazing things!",
            "You are worthy of love and respect!",
            "You have the power to create change!",
            "You are stronger than you think!",
            "Today is going to be a great day!",
            "You are enough, just as you are!",
            "Your potential is limitless!",
            "You deserve all the good things coming your way!",
            "You are brave, strong, and capable!",
            "You make a difference in this world!",
        ]
        embed = self.premium_embed("Daily Affirmation ✨", f"💫 {random.choice(affirmations)}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="slots", description="Play the slot machine")
    async def slots(self, ctx: commands.Context):
        emojis = ["🍎", "🍊", "🍋", "🍇", "🍒", "💎", "7️⃣", "⭐"]
        result = [random.choice(emojis) for _ in range(3)]
        
        if result[0] == result[1] == result[2]:
            if result[0] == "7️⃣":
                outcome = "🎰 JACKPOT! You hit 777! 🎰"
                color = discord.Color.gold()
            elif result[0] == "💎":
                outcome = "💎 DIAMOND WIN! Amazing! 💎"
                color = discord.Color.blue()
            else:
                outcome = "🎉 THREE OF A KIND! You win! 🎉"
                color = discord.Color.green()
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            outcome = "Nice! You got a pair! 👍"
            color = discord.Color.yellow()
        else:
            outcome = "Better luck next time! 😔"
            color = discord.Color.red()
        
        display = f"┃ {result[0]} ┃ {result[1]} ┃ {result[2]} ┃"
        
        embed = discord.Embed(
            title="🎰 Slot Machine 🎰",
            description=f"```\n{display}\n```\n{outcome}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FunGames(bot))
