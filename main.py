import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord import Embed
import env
import aiohttp
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from twitch import checkIfLive
import asyncio
from tictactoe import TicTacToe
import json
import random
import time
import os
from typing import Optional
from asyncio import sleep
import requests
from googleapiclient.discovery import build

# Initialize variables
intents = discord.Intents.all()

user_message_times = {}

script_dir = os.path.dirname(os.path.realpath(__file__))

# Change the current working directory to the script's directory
os.chdir(script_dir)

ANTI_SPAM_SECONDS = 5
BASE_EXP = 100
EXP_MULTIPLIER = 2

isLive = False

counting_channel_id = 892158631603228672
twitch_announcement_id = 793635730826985523
welcome_id = 793633905252106250
polls_id = 832213669764923413
log_channel_id = 812313840666542184
youtube_id = 812313840666542184
level_up_id = 898895899923714118

last_user_id = None

youtube = build('youtube', 'v3', developerKey='AIzaSyBN4ki9nTmY-CNYy2YRuWMwIdRWoZHNoeo')
channel_id = 'UCX4nLphiA84NuMw5lMZlI6A'
last_video_id = None

GIPHY_API_KEY = env.GIPHY_API_KEY

bot = commands.Bot(command_prefix='!', intents=intents)

with open('polls_questions.txt', 'r') as f:
    text = f.read()

def read_count():
    with open("count.txt", "r") as f:
        count_data = f.read().strip().split(',')
        count = int(count_data[0])
        last_user = int(count_data[1]) if len(count_data) > 1 else None
        return count, last_user

def write_count(count, last_user):
    with open("count.txt", "w") as f:
        f.write(f"{count},{last_user}")

def load_reaction_roles_data():
    try:
        with open("reaction_roles.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        with open("reaction_roles.json", "w") as f:
            json.dump({}, f)
        return {}

def save_reaction_roles_data(data):
    with open("reaction_roles.json", "w") as f:
        json.dump(data, f, indent=4)


def calculate_new_level(exp):
    level = 1
    required_exp = BASE_EXP

    while exp >= required_exp:
        exp -= required_exp
        level += 1
        required_exp = int(BASE_EXP * (EXP_MULTIPLIER ** (level - 1)))

    return level

async def is_spam(user_id):
    current_time = time.time()
    if user_id not in user_message_times:
        user_message_times[user_id] = current_time
        return False

    last_message_time = user_message_times[user_id]
    user_message_times[user_id] = current_time
    return current_time - last_message_time < ANTI_SPAM_SECONDS

@bot.event
async def on_message(message):
    global counter_data
    exp_to_add = random.randint(10, 20)

    if message.author == bot.user:
        return
    
    global count, last_user_id

    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Check if the message is in the counting channel
    if message.channel.id == counting_channel_id:
        try:
            # Check if the message is the correct number and the user didn't count twice
            if int(message.content) == count + 1 and message.author.id != last_user_id:
                count += 1
                last_user_id = message.author.id
                write_count(count, last_user_id)
                last_user_id = message.author.id
            else:
                await message.delete()
        except ValueError:  # If the message is not a number, delete it
            await message.delete()
    
    with open('bad words.txt', 'r') as f:
        bad_words = f.read()

    banned_words = bad_words.split(',')

    for word in banned_words:
        if word.lower() in message.content.lower():
            await message.delete()
            await message.channel.send(f'{message.author.mention}, please do not use offensive language.')
            return
    
    user_id = str(message.author.id)
    if user_id not in exp_data:
        exp_data[user_id] = {
            "username": message.author.name,
            "exp": 0,
            "level": 1,
        }
        
    if await is_spam(message.author.id):
        return

    exp_data[user_id]["exp"] += exp_to_add
    save_exp_data(exp_data)
    new_level = calculate_new_level(exp_data[user_id]["exp"])

    if new_level > exp_data[user_id]["level"]:
        save_exp_data(exp_data)
        exp_data[user_id]["level"] = new_level
        role_names = ["Zombie", "Skeleton", "Creeper", "Wither", "Ender Dragon"]
        role_name = role_names[min(new_level - 1, len(role_names) - 1)]

        role = discord.utils.get(message.guild.roles, name=role_name)
        if not role:
            role = await message.guild.create_role(name=role_name)

        member = message.author
        await member.add_roles(role)

        # Create an embed for the level-up message
        embed = discord.Embed(title="Level Up!", description=f"{message.author.mention} leveled up to {role_name}!", color=16739179)

        # Send the embed to a specific channel
        level_up_channel = bot.get_channel(level_up_id)
        await level_up_channel.send(embed=embed)

    await bot.process_commands(message)
    

def find_duplicate_questions(text):
    questions = re.findall(r"(^.*\?$)", text, re.MULTILINE)
    seen_questions = set()
    duplicates = set()

    for question in questions:
        if question in seen_questions:
            duplicates.add(question)
        else:
            seen_questions.add(question)

    return duplicates


def remove_duplicates(text, duplicates):
    lines = text.split('\n')
    unique_questions = []
    i = 0

    included_duplicates = set()

    while i < len(lines):
        line = lines[i]
        if line.endswith('?') and (line not in duplicates or line not in included_duplicates):
            question_block = [line]
            if line in duplicates:
                included_duplicates.add(line)
            for j in range(1, 5):
                if i + j < len(lines) and not lines[i + j].endswith('?'):
                    question_block.append(lines[i + j])
                else:
                    break
            unique_questions.append('\n'.join(question_block))
            i += 4
        else:
            i += 1

    return unique_questions

duplicates = find_duplicate_questions(text)
unique_questions = remove_duplicates(text, duplicates)


async def get_random_greeting_gif():
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.giphy.com/v1/gifs/random?api_key={GIPHY_API_KEY}&tag=waving') as response:
            data = await response.json()
            return data['data']['images']['original']['url']


async def get_random_meme_gif():
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.giphy.com/v1/gifs/random?api_key={GIPHY_API_KEY}&tag=memes&rating=G') as response:
            data = await response.json()
            return data['data']['images']['original']['url']

# Loads PBs from file
def load_pbs():
    with open('pbs.json', 'r') as file:
        pbs = json.load(file)
    return pbs

# Saves PBs to file
def save_pbs(pbs):
    with open('pbs.json', 'w') as file:
        json.dump(pbs, file)


@bot.event
async def on_ready():
    checkforvideos()
    global count, last_user_id
    count_data = read_count()
    count = count_data[0]
    last_user_id = count_data[1]
    print(f'{bot.user.name} has connected to Discord!')
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)
                
    load_reaction_roles.start()
        
    twitchNotifications.start()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_polls, CronTrigger(hour=23, minute=0, second=0), misfire_grace_time=60)
    scheduler.start()

def get_last_video_id_from_file():
    try:
        with open('last_video_id.txt', 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return None
    
def update_last_video_id_in_file(video_id):
    with open('last_video_id.txt', 'w') as file:
        file.write(video_id)
        
@tasks.loop(minutes=30)
async def checkforvideos():
    channel = bot.get_channel(890908593241612288)

    request = youtube.search().list(
        part='snippet',
        channelId='UCX4nLphiA84NuMw5lMZlI6A',
        maxResults=1,
        type='video',
        order='date'
    )
    response = request.execute()
    video_id = response['items'][0]['id']['videoId']

    last_video_id = get_last_video_id_from_file()

    if last_video_id != video_id:
        update_last_video_id_in_file(video_id)
        await channel.send(f'<@&814797615358803968> A new video has been uploaded! https://www.youtube.com/watch?v={video_id}')


@bot.tree.command(description="See my current PBs", name="pb")
async def pb(interaction: discord.Interaction):
    pbs = load_pbs()
    embed = discord.Embed(title="Minecraft Speedrunning PBs", color=discord.Color.red())
    for category, time in pbs.items():
        embed.add_field(name=category, value=time, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(description="Edit the pbs", name="editpb")
@commands.has_permissions(administrator=True)
async def editpb(ctx, category: str, new_time: str):
    pbs = load_pbs()
    if category in pbs:
        pbs[category] = new_time
        save_pbs(pbs)
        
@bot.tree.command(description="Get all the commands for the server!", name="help")
async def help(interaction: discord.Interaction):
    member = interaction.user
    is_admin = member.guild_permissions.administrator

    general_embed = discord.Embed(
        title="General Commands",
        description="Here are the general commands:",
        color=discord.Color.red()
    )
    general_embed.add_field(name="/tictactoe {user}", value="Play a game of Tic Tac Toe with another member in the server!", inline=False)
    general_embed.add_field(name="/meme", value="Sends a random meme GIF", inline=False)
    general_embed.add_field(name="/coinflip", value="Flip a coin", inline=False)
    general_embed.add_field(name="/8ball {question}", value="Ask the magic 8 ball a question", inline=False)
    general_embed.add_field(name="/dadjoke", value="Sends a random dadjoke", inline=False)
    general_embed.add_field(name="/wouldyourather", value="Sends a random would you rather question", inline=False)
    general_embed.add_field(name="/level", value="Shows your current level and role", inline=False)
    general_embed.add_field(name="/rockpaperscissor", value="Play a game of Rock Paper or Scissors against the AI", inline=False)
    general_embed.add_field(name="/pb", value="See my current PBs", inline=False)

    if is_admin: 
        admin_embed = discord.Embed(
            title="Admin Commands",
            description="React with 🔒 to view admin commands.",
            color=discord.Color.red()
        )
        general_msg = await interaction.channel.send(embed=general_embed)
        admin_help_msg = await interaction.channel.send(embed=admin_embed)
        await admin_help_msg.add_reaction("🔒")

        def check(reaction, user):
            return user == member and str(reaction.emoji) == "🔒" and reaction.message.id == admin_help_msg.id

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)

        except asyncio.TimeoutError:
            await admin_help_msg.clear_reactions()
        else:
            admin_embed = discord.Embed(
                title="Admin Commands",
                description="Here are the admin commands:",
                color=discord.Color.red()
            )
            admin_embed.add_field(name="/Kick {user} {reason}", value="Kick a member, remember to add a reason and a log sends automatically to the log channel with the latest 10 messages of the user", inline=False)
            admin_embed.add_field(name="/Bank {user} {reason}", value="Ban a member and sends a log to the log channel", inline=False)
            admin_embed.add_field(name="/timout {user} {time}", value="Timeout a member with specified time", inline=False)
            admin_embed.add_field(name="/editpb {category} {time}", value="Edit a pb", inline=False)
            await admin_help_msg.edit(embed=admin_embed)
            await admin_help_msg.clear_reactions()
    else:
        await interaction.channel.send(embed=general_embed)
        
def count_options(question):
    options = re.findall(r'^\d+:', question, re.MULTILINE)
    return len(options)

def save_question_index(index):
    with open('question_index.txt', 'w') as file:
        file.write(str(index))

def load_question_index():
    try:
        with open('question_index.txt', 'r') as file:
            content = file.read().strip()
            if content:
                index = int(content)                
                return index
            else:
                return 0
    except FileNotFoundError:
        return 0

async def daily_polls():
    question_index = load_question_index()
    channel = bot.get_channel(polls_id)
    if 0 <= question_index < len(unique_questions):
        question = unique_questions[question_index]

        # Create an Embed object
        embed = Embed(title=f"Daily Poll nr: {question_index} \u2b50",
                      description=f"{question}",
                      color=16739179)
      
        embed.set_footer(text="React to vote!")

        sent_message = await channel.send(embed=embed)
        
        num_options = count_options(question)
        for i in range(1, num_options + 1):
            await sent_message.add_reaction(f"{i}\N{COMBINING ENCLOSING KEYCAP}")
    
    question_index += 1
    save_question_index(question_index)
    question_index += 1
   
@bot.tree.command(description="Check the bot's responsiveness", name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")
        
@bot.tree.command(description="Play a game of rock paper scissor agains the AI", name="rockpaperscissor")
@app_commands.describe(user_choice = "Rock Paper or Scissor?")
async def rockpaperscissor(interaction: discord.Interaction, user_choice: str):
    user_choice = user_choice.lower()
    valid_choices = ["rock", "paper", "scissors"]

    if user_choice not in valid_choices:
        await interaction.response.send_message("Invalid choice! Please choose rock, paper, or scissors.")
        return

    ai_choice = random.choice(valid_choices)
    result = ""

    if user_choice == ai_choice:
        result = "It's a tie!"
    elif (user_choice == "rock" and ai_choice == "scissors") or \
         (user_choice == "paper" and ai_choice == "rock") or \
         (user_choice == "scissors" and ai_choice == "paper"):
        result = "You win!"
    else:
        result = "You lose!"
    await interaction.response.send_message(f"You chose {user_choice.capitalize()}, the AI chose {ai_choice.capitalize()}. {result}")
    
@bot.tree.command(description="Check the bot's responsiveness", name="8ball")
async def ball(interaction: discord.Interaction, *, question: str):
    answers = ["It is certain","It is decidedly so","Without a doubt","Yes - definitely","You may rely on it","As I see it, yes","Most likely","Outlook good","Yes","Signs point to yes","Reply hazy, try again","Ask again later","Better not tell you now","Cannot predict now","Concentrate and ask again","Don't count on it","My reply is no","My sources say no","Outlook not so good","Very doubtful"]
    await interaction.response.send_message(f"Question: {question}\nAnswer: {answers[random.randint(0, len(answers) - 1)]}")

@bot.tree.command(description="Get all the commands for the server!", name="dadjoke")
async def dadjoke(interaction: discord.Interaction): 
    async with aiohttp.ClientSession() as session:
        async with session.get('https://icanhazdadjoke.com/', headers={"Accept": "application/json"}) as response:
            data = await response.json()
            await interaction.channel.send(data['joke'])

@bot.tree.command(description="Send a random Meme!", name="meme")
async def meme(interaction: discord.Interaction):
    gif_url = await get_random_meme_gif()
    embed = Embed()
    embed.set_image(url=gif_url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(description="Send a random Would You Rather question!", name="wouldyourather")
async def wouldyourather(interaction: discord.Interaction):
    with open('current-would-you-rather.txt', 'r') as file:
        current_line = int(file.readline())

    # Read questions from the 'would-you-rather.txt' file
    with open('would-you-rather.txt', 'r') as questions:
        data = questions.readlines()
        question = data[current_line].strip()

    await interaction.response.send_message(question)

    # Update the current line in the file
    with open('current-would-you-rather.txt', 'w') as file:
        file.write(str(current_line))
        
    current_line += 1
    if current_line >= len(data):
        current_line = 0

    # Update the current line in the file
    with open('current-would-you-rather.txt', 'w') as file:
        file.write(str(current_line))


@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(description="Announce Something!", name="announce")
@app_commands.describe(what_to_announce="What should I announce", to_which_channel="To which channel?", embed_message="Embed the message? (True/False)")
async def announce(interaction: discord.Interaction, what_to_announce: str, to_which_channel: discord.TextChannel, embed_message: bool = False):
    if embed_message:
        embed = Embed(description=what_to_announce, color=discord.Color.red())
        await to_which_channel.send(embed=embed)
    else:
        await to_which_channel.send(what_to_announce)
        
@bot.tree.command(description="Flip a coin.", name="coinflip")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(["Heads!", "Tails!"]))

@bot.tree.command(description="Show your current level and role", name="level")
async def level(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in exp_data:
        await interaction.response.send_message("You don't have any experience points yet.")
        return

    exp = exp_data[user_id]["exp"]
    level = exp_data[user_id]["level"]
    role_names = ["Creeper", "Zombie", "Skeleton", "Wither", "Ender Dragon"]
    role_name = role_names[min(level - 1, len(role_names) - 1)]

    await interaction.response.send_message(f"Your current level is {level} and your role is {role_name} with an exp of {exp}.")

def load_exp_data():
    try:
        with open("exp_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

exp_data = load_exp_data()

def save_exp_data(exp_data):
    with open("exp_data.json", "w") as f:
        json.dump(exp_data, f)

isLive = False

@tasks.loop(seconds=10)
async def twitchNotifications():
    global isLive
    stream = checkIfLive("ZodiSP")
    if stream != "OFFLINE":
        if isLive == False:
            isLive = True

            title = stream.title
            thumbnail_url = stream.thumbnail_url.format(width=1080, height=608)
            url = f"https://www.twitch.tv/ZodiSP"

            embed = discord.Embed(
                title=f"{title}",
                description=f"<@&814797613395476503> [ZodiSP is live! Click here to watch the stream.]({url})",
                color=16739179,
            )

            embed.set_author(name="ZodiSP", url=url, icon_url="https://i.imgur.com/OVsAABd.jpg")
            embed.set_thumbnail(url=thumbnail_url)
            embed.set_footer(text="Twitch Notifications")

            await bot.get_channel(twitch_announcement_id).send(embed=embed)
    else:
        isLive = False



def tictactoe_accept_check(reaction, user, players):
    return (
        user in players
        and str(reaction.emoji) == '✅'
        and reaction.message.author == bot.user
    )


@bot.tree.command(description="Play a game of Tic Tac Toe towards an opponent", name="tictactoe")
@app_commands.describe(opponent = "Who do you want to play against?")
async def tictactoe(interaction: discord.Interaction, opponent: discord.Member):
    author = interaction.user
    if author == opponent:
        await interaction.response.send_message("You can't play against yourself!")
        return
    

    players = [author, opponent]
    game = TicTacToe(*players)
    accept_message = await interaction.channel.send(
        f"{opponent.mention}, do you accept the challenge from {author.mention}? (React with ✅ to accept)"
    )
    await accept_message.add_reaction('✅')

    try:
        reaction, user = await bot.wait_for(
            'reaction_add', check=lambda r, u: tictactoe_accept_check(r, u, players), timeout=60
        )

    except asyncio.TimeoutError:
        await interaction.channel.send("Challenge not accepted in time.")
        return
    await interaction.channel.send("Challenge accepted! The game board is 3x3. Enter the row and column numbers (1-3) separated by a space to make a move. Example: '1 3'")
    while True:
        await interaction.channel.send(f"Current board:\n```\n{game}\n```{players[game.current_turn].mention}'s turn.")

        try:
            move_message = await bot.wait_for(
                'message', check=lambda m: m.author == players[game.current_turn], timeout=60
            )
        except asyncio.TimeoutError:
            await interaction.channel.send("Turn not played in time. The game has ended.")
            break

        try:
            x, y = map(int, move_message.content.split())
            if x not in range(1, 4) or y not in range(1, 4):
                raise ValueError
            result, valid_move = game.make_move(x, y)
            if result:
                await interaction.channel.send(f"Current board:\n```\n{game}\n```{result}")
                if valid_move:
                    break
        except ValueError:
            await interaction.channel.send("Invalid input. Please enter the row and column separated by a space, like '1 3'.")
    
@bot.tree.command(description="Choose a message to turn into a reaction role!", name = "reactionrole")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message_id = "The ID of the message to add the reaction role to", emoji = "The emoji to react with", role = "The role to give when the user reacts")
async def setup_reaction_role(ctx, message_id: str, emoji: str, role: discord.Role):
    try:
        message_id = int(message_id)
    except ValueError:
        await ctx.send("Invalid message ID provided. Please make sure it's a valid integer.")
        return

    data = load_reaction_roles_data()
    try:
        message = await ctx.channel.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send("Message not found. Please make sure the message ID is correct and the bot can access the message.")
        return
    
    await message.add_reaction(emoji)

    if str(ctx.guild.id) not in data:
        data[str(ctx.guild.id)] = []

    data[str(ctx.guild.id)].append({
        "channel_id": ctx.channel.id,
        "message_id": message_id,
        "emoji": emoji,
        "role_id": role.id
    })

    save_reaction_roles_data(data)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return

    data = load_reaction_roles_data()

    for item in data[str(payload.guild_id)]:
        if payload.message_id == item["message_id"] and str(payload.emoji) == item["emoji"]:
            role = discord.utils.get(payload.member.guild.roles, id=item["role_id"])
            await payload.member.add_roles(role)
            break
        
@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if member.bot:
        return

    data = load_reaction_roles_data()

    for item in data[str(payload.guild_id)]:
        if payload.message_id == item["message_id"] and str(payload.emoji) == item["emoji"]:
            role = discord.utils.get(guild.roles, id=item["role_id"])
            await member.remove_roles(role)
            break


@tasks.loop(seconds=60)
async def load_reaction_roles():
    data = load_reaction_roles_data()
    for guild_id, guild_data in data.items():
        for reaction_role in guild_data:
            channel_id = reaction_role.get("channel_id")
            message_id = reaction_role.get("message_id")
            emoji = reaction_role.get("emoji")

            guild = bot.get_guild(int(guild_id))
            channel = bot.get_channel(int(channel_id))
            message = await channel.fetch_message(message_id)

            await message.add_reaction(emoji)

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name='Member')
    await member.add_roles(role)
    print(f'Role "{role}" assigned to {member}.')
    
    gif_url = await get_random_greeting_gif()

    embed = Embed()
    embed.set_image(url=gif_url)
    channel = bot.get_channel(welcome_id)
    
    await channel.send(f"Welcome {member.name}!", embed=embed)  

load_reaction_roles.before_loop(bot.wait_until_ready)

TOKEN = env.TOKEN

bot.run(TOKEN)
