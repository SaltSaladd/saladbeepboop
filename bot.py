import discord
from discord.ext import commands, tasks
import random
import time
import aiohttp
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import os  # For environment variables

# Setup intents and bot instance
intents = discord.Intents.default()
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Securely load the bot token from environment variables
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Bot token not found. Set it in the environment variables.")

CAT_API_URL = 'https://api.thecatapi.com/v1/images/search'

# Define spam settings
SPAM_THRESHOLD = 5
SPAM_INTERVAL = 10
TIMEOUT_DURATION = 60
COOLDOWN_DURATION = 20
SPAM_ALERT_INTERVAL = 120
USER_TIMEOUT_COOLDOWN = 180

# Define wall of text settings
TEXT_LIMIT = 500

# Track user messages, timeouts, and cooldowns
user_messages = defaultdict(lambda: deque(maxlen=SPAM_THRESHOLD))
cooldowns = {}
spam_alert_cooldowns = defaultdict(int)
user_timeout_cooldowns = defaultdict(int)

QUIET_CHANNEL_ID = 1231007921526280295  # Replace with your channel ID
QUIET_THRESHOLD = 5

# Minigame states
hangman_games = {}
wordle_games = {}
anagram_games = {}

WORD_LIST = ['python', 'hangman', 'discord', 'bot', 'wordle', 'anagram']

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_activity.start()

@tasks.loop(minutes=1)
async def check_activity():
    channel = bot.get_channel(QUIET_CHANNEL_ID)
    if not channel:
        return

    async for message in channel.history(limit=1):
        if datetime.now(timezone.utc) - message.created_at >= timedelta(minutes=QUIET_THRESHOLD):
            await channel.send("It seems quiet in here.....")
            break

@bot.event
async def on_member_join(member):
    if 'bernd' in member.name.lower() or 'bernd' in member.display_name.lower() or '✔' in member.name or '✔' in member.display_name:
        await member.ban(reason="Flagged activities")
        guild = bot.get_guild(SEVER_ID)  # Replace with your sever ID
        channel = guild.get_channel(QUIET_CHANNEL_ID)  # Replace with your channel ID
        await channel.send(f"{member.name} was banned for flagged activities.")

@bot.event
async def on_member_update(before, after):
    if 'bernd' in after.name.lower() or 'bernd' in after.display_name.lower() or '✔' in after.name or '✔' in after.display_name:
        await after.ban(reason="Flagged activities")
        guild = bot.get_guild(SERVER_ID)  # Replace with your server ID
        channel = guild.get_channel(QUIET_CHANNEL_ID)  # Replace with your channel ID
        await channel.send(f"{after.name} was banned for flagged activities.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    current_time = time.time()
    user_id = message.author.id

    # Check for wall of text
    if len(message.content) > TEXT_LIMIT:
        await message.delete()
        await message.channel.send(f"{message.author.mention} Too much text ;(")
        return

    # Check if bot is mentioned and handle commands
    if bot.user in message.mentions:
        command = message.content.lower().split()
        if len(command) > 1:
            await handle_mention_commands(message, command)

    # Append current message timestamp
    user_messages[user_id].append(current_time)

    # Check for spam
    await check_for_spam(message, current_time, user_id)

    await bot.process_commands(message)

async def handle_mention_commands(message, command):
    if command[1] == "ping":
        start_time = time.time()
        response_message = await message.channel.send("PONG!")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        await response_message.edit(content=f"PONG! {response_time} ms")
    elif command[1] == "rps":
        await handle_rps_command(message, command)
    elif command[1] == "cat":
        await handle_cat_command(message)
    elif command[1] == "hangman":
        await start_hangman(message.channel)
    elif command[1] == "wordle":
        await start_wordle(message.channel)
    elif command[1] == "anagram":
        await start_anagram(message.channel)
    elif command[1] == "debug" and message.author.id == 1193303506057183272:
        await message.channel.send(
            f"**Debug Info**:\n"
            f"Spam Threshold: {SPAM_THRESHOLD}\n"
            f"Spam Interval: {SPAM_INTERVAL} seconds\n"
            f"Timeout Duration: {TIMEOUT_DURATION} seconds\n"
            f"Cooldown Duration: {COOLDOWN_DURATION} seconds\n"
            f"Spam Alert Interval: {SPAM_ALERT_INTERVAL} seconds\n"
            f"User Timeout Cooldown: {USER_TIMEOUT_COOLDOWN} seconds\n"
            f"Text Limit: {TEXT_LIMIT} characters\n"
            f"Cat API URL: {CAT_API_URL}\n"
        )

async def handle_rps_command(message, command):
    if len(command) == 3:
        user_choice = command[2].lower()
        if user_choice in ["rock", "paper", "scissors"]:
            bot_choice = random.choice(["rock", "paper", "scissors"])
            result = determine_rps_winner(user_choice, bot_choice)
            await message.channel.send(f"You chose {user_choice}, I chose {bot_choice}. {result}")
        else:
            await message.channel.send("Invalid choice! Choose rock, paper, or scissors.")

async def handle_cat_command(message):
    async with aiohttp.ClientSession() as session:
        async with session.get(CAT_API_URL) as resp:
            if resp.status == 200:
                data = await resp.json()
                cat_image_url = data[0]['url']
                await message.channel.send(cat_image_url)
            else:
                await message.channel.send("Could not fetch a cat image at the moment. Please try again later.")

async def check_for_spam(message, current_time, user_id):
    if len(user_messages[user_id]) == SPAM_THRESHOLD:
        if (current_time - user_messages[user_id][0]) <= SPAM_INTERVAL:
            if user_id not in cooldowns or current_time - cooldowns[user_id] >= COOLDOWN_DURATION:
                await message.channel.edit(slowmode_delay=10)
                if current_time - spam_alert_cooldowns[message.channel.id] >= SPAM_ALERT_INTERVAL:
                    await message.channel.send("Spam detected. Slowmode set to 10 seconds.")
                    spam_alert_cooldowns[message.channel.id] = current_time

                if current_time - user_timeout_cooldowns[user_id] >= USER_TIMEOUT_COOLDOWN:
                    try:
                        timeout_until = datetime.now(timezone.utc) + timedelta(seconds=TIMEOUT_DURATION)
                        await message.author.edit(timed_out_until=timeout_until)
                        await message.channel.send(f"{message.author.mention} was timed out for {TIMEOUT_DURATION} seconds. Reason: Spamming")
                        user_timeout_cooldowns[user_id] = current_time
                    except discord.Forbidden:
                        await message.channel.send(f"{message.author.mention} attempted to be timed out but the bot lacks permissions.")
                cooldowns[user_id] = current_time

def determine_rps_winner(user_choice, bot_choice):
    if user_choice == bot_choice:
        return "It's a tie!"
    elif (user_choice == "rock" and bot_choice == "scissors") or \
         (user_choice == "paper" and bot_choice == "rock") or \
         (user_choice == "scissors" and bot_choice == "paper"):
        return "You win!"
    else:
        return "I win!"

@bot.command()
@commands.has_permissions(administrator=True)
async def ban_bernd(ctx):
    for member in ctx.guild.members:
        if 'bernd' in member.name.lower() or 'bernd' in member.display_name.lower() or '✔' in member.name or '✔' in member.display_name:
            await member.ban(reason="Flagged activities")
            guild = bot.get_guild(SERVER_ID)  # Replace with your server ID
            channel = guild.get_channel(QUIET_CHANNEL_ID)  # Replace with your channel ID
            await channel.send(f'{member.name} was banned for flagged activities.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_spam_threshold(ctx, threshold: int):
    global SPAM_THRESHOLD
    SPAM_THRESHOLD = threshold
    await ctx.send(f'Spam threshold set to {SPAM_THRESHOLD} messages.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_spam_interval(ctx, interval: int):
    global SPAM_INTERVAL
    SPAM_INTERVAL = interval
    await ctx.send(f'Spam interval set to {SPAM_INTERVAL} seconds.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_timeout_duration(ctx, duration: int):
    global TIMEOUT_DURATION
    TIMEOUT_DURATION = duration
    await ctx.send(f'Timeout duration set to {TIMEOUT_DURATION} seconds.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_cooldown_duration(ctx, duration: int):
    global COOLDOWN_DURATION
    COOLDOWN_DURATION = duration
    await ctx.send(f'Cooldown duration set to {COOLDOWN_DURATION} seconds.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_spam_alert_interval(ctx, interval: int):
    global SPAM_ALERT_INTERVAL
    SPAM_ALERT_INTERVAL = interval
    await ctx.send(f'Spam alert interval set to {SPAM_ALERT_INTERVAL} seconds.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_user_timeout_cooldown(ctx, cooldown: int):
    global USER_TIMEOUT_COOLDOWN
    USER_TIMEOUT_COOLDOWN = cooldown
    await ctx.send(f'User timeout cooldown set to {USER_TIMEOUT_COOLDOWN} seconds.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_text_limit(ctx, limit: int):
    global TEXT_LIMIT
    TEXT_LIMIT = limit
    await ctx.send(f'Text limit set to {TEXT_LIMIT} characters.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_quiet_channel(ctx, channel_id: int):
    global QUIET_CHANNEL_ID
    QUIET_CHANNEL_ID = channel_id
    await ctx.send(f'Quiet channel set to {QUIET_CHANNEL_ID}.')

@bot.command()
@commands.has_permissions(administrator=True)
async def set_quiet_threshold(ctx, threshold: int):
    global QUIET_THRESHOLD
    QUIET_THRESHOLD = threshold
    await ctx.send(f'Quiet threshold set to {QUIET_THRESHOLD} minutes.')

# Minigames
async def start_hangman(channel):
    word = random.choice(WORD_LIST)
    state = ['_'] * len(word)
    attempts = 6
    hangman_games[channel.id] = {'word': word, 'state': state, 'attempts': attempts}
    await channel.send(f"Starting Hangman! Word: {' '.join(state)}\nAttempts left: {attempts}")

@bot.command()
async def guess(ctx, letter: str):
    game = hangman_games.get(ctx.channel.id)
    if not game:
        await ctx.send("No hangman game is running.")
        return
    
    if len(letter) != 1 or not letter.isalpha():
        await ctx.send("Please guess a single letter.")
        return
    
    if letter in game['word']:
        for idx, char in enumerate(game['word']):
            if char == letter:
                game['state'][idx] = letter
        await ctx.send(f"Correct! {' '.join(game['state'])}\nAttempts left: {game['attempts']}")
    else:
        game['attempts'] -= 1
        await ctx.send(f"Wrong! {' '.join(game['state'])}\nAttempts left: {game['attempts']}")

    if '_' not in game['state']:
        await ctx.send("Congratulations! You guessed the word!")
        hangman_games.pop(ctx.channel.id)
    elif game['attempts'] == 0:
        await ctx.send(f"Game over! The word was {game['word']}.")
        hangman_games.pop(ctx.channel.id)

async def start_wordle(channel):
    word = random.choice(WORD_LIST)
    wordle_games[channel.id] = {'word': word, 'attempts': 6}
    await channel.send("Starting Wordle! You have 6 attempts to guess the 5-letter word.")

@bot.command()
async def wordle_guess(ctx, guess: str):
    game = wordle_games.get(ctx.channel.id)
    if not game:
        await ctx.send("No Wordle game is running.")
        return
    
    if len(guess) != 5 or not guess.isalpha():
        await ctx.send("Please guess a 5-letter word.")
        return

    game['attempts'] -= 1
    response = []
    for g, w in zip(guess, game['word']):
        if g == w:
            response.append(f"[{g}]")
        elif g in game['word']:
            response.append(f"({g})")
        else:
            response.append(g)
    
    await ctx.send(f"{' '.join(response)}\nAttempts left: {game['attempts']}")

    if guess == game['word']:
        await ctx.send("Congratulations! You guessed the word!")
        wordle_games.pop(ctx.channel.id)
    elif game['attempts'] == 0:
        await ctx.send(f"Game over! The word was {game['word']}.")
        wordle_games.pop(ctx.channel.id)

async def start_anagram(channel):
    word = random.choice(WORD_LIST)
    shuffled = ''.join(random.sample(word, len(word)))
    anagram_games[channel.id] = {'word': word, 'shuffled': shuffled}
    await channel.send(f"Starting Anagrams! Unscramble the letters: {shuffled}")

@bot.command()
async def anagram_guess(ctx, guess: str):
    game = anagram_games.get(ctx.channel.id)
    if not game:
        await ctx.send("No anagram game is running.")
        return

    if guess == game['word']:
        await ctx.send(f"Congratulations! You unscrambled the word: {game['word']}!")
        anagram_games.pop(ctx.channel.id)
    else:
        await ctx.send("Incorrect. Try again!")

# Run the bot
bot.run(TOKEN)
