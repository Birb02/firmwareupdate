import discord
from discord.ext import commands
import aiohttp
from PIL import Image
import imagehash
import io
import re
import shutil
import os
import sys
import asyncio
import json

PREFIX = ">"
BOT_VERSION = "V.RS.22.GH.OL"
BOT_CERT = "USRS2250ILMP6482"
AUTHORIZED_IDS = {949748857351340062, 479990917110038529}

BOT_FILE = os.path.abspath(__file__)
CRED_FILE = "credentials.json"
UPDATE_FLAG = "update_flag.txt"
STABLE_BACKUP = BOT_FILE.replace(".py", "_backup.py")
GITHUB_UPFW = "https://github.com/Birb02/firmwareupdate/blob/main/UPFW.py"

# Load credentials if they exist
TOKEN = None
BOT_PASSWORD = None

def load_credentials():
    global TOKEN, BOT_PASSWORD
    if not os.path.exists(CRED_FILE):
        return False
    with open(CRED_FILE) as f:
        data = json.load(f)
    TOKEN = data["token"]
    BOT_PASSWORD = data["password"]
    return True

def save_credentials(token, password):
    data = {"token": token, "password": password}
    with open(CRED_FILE, "w") as f:
        json.dump(data, f)

# ----------------- BOT INIT -----------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
authenticated_users = set()

# ----------------- SERVERCONFIG -----------------
async def get_serverconfig_channel(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name="serverconfig")
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel = await guild.create_text_channel(
            "serverconfig",
            overwrites=overwrites,
            reason="Bot configuration storage"
        )
    return channel

async def get_banned_data(guild):
    channel = await get_serverconfig_channel(guild)
    banned_words = []
    banned_hashes = []
    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.content.startswith("WORD:"):
            banned_words.append(msg.content[5:].strip().lower())
        elif msg.content.startswith("IMG:"):
            banned_hashes.append(msg.content[4:].strip())
    return banned_words, banned_hashes

def hash_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.phash(img))

def is_authenticated(user_id):
    return user_id in authenticated_users

def auth_required():
    async def predicate(ctx):
        if not is_authenticated(ctx.author.id):
            await ctx.send("You must authenticate first using `>Auth`.")
            return False
        return True
    return commands.check(predicate)

# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    print(f"[OK] Running {bot.user}")
    print(f"[INFO] Version: {BOT_VERSION}")
    print(f"[INFO] Certificate: {BOT_CERT}")

    # -----------------
    # Check if this is post-FWUP first restart
    if os.path.exists(UPDATE_FLAG):
        with open(UPDATE_FLAG) as f:
            updater_id = int(f.read().strip())
        user = await bot.fetch_user(updater_id)
        # Recover token from backup to login (already logged in now with old token)
        # Start DM questionnaire
        try:
            await user.send("New Root Auth Password:")
        except:
            return  # can't DM

        def check(m):
            return m.author.id == updater_id and isinstance(m.channel, discord.DMChannel)

        # Get new root password
        msg = await bot.wait_for("message", check=check)
        new_password = msg.content.strip()
        await msg.delete()

        # Ask for token
        await user.send(
            "Since this is a fresh update, enter the bot token (can be same or new):"
        )
        msg = await bot.wait_for("message", check=check)
        new_token = msg.content.strip()
        await msg.delete()

        # Save credentials locally
        save_credentials(new_token, new_password)

        await user.send("Credentials saved. Restarting firmware.")
        os.remove(UPDATE_FLAG)
        os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    banned_words, banned_hashes = await get_banned_data(message.guild)
    content = message.content.lower()
    for word in banned_words:
        if re.search(rf"\b{re.escape(word)}\b", content):
            await message.delete()
            return
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image"):
            img_hash = hash_image(await attachment.read())
            if img_hash in banned_hashes:
                await message.delete()
                return
    await bot.process_commands(message)

# ----------------- AUTH SYSTEM -----------------
@bot.command()
async def Auth(ctx):
    if ctx.author.id not in AUTHORIZED_IDS:
        await ctx.send("Developer Privilages: Revoked.")
        return
    try:
        await ctx.author.send(
            "Final Update, LOG: 1.0 - AA: In Loving Memory of Perry the Budgie, I miss you buddy.. | Enter your bot password:"
        )
    except:
        await ctx.send("I cannot DM you. Enable DMs and try again.")
        return
    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
    try:
        msg = await bot.wait_for("message", check=check, timeout=46)
    except asyncio.TimeoutError:
        await ctx.author.send("Authentication timed out.")
        return
    if msg.content.strip() == BOT_PASSWORD:
        authenticated_users.add(ctx.author.id)
        await ctx.author.send("Authentication successful.")
        await ctx.send("Authenticated successfully.")
    else:
        await ctx.author.send("Incorrect password.")
        await ctx.send("Authentication failed.")

# ----------------- COMMANDS -----------------
@bot.command()
@auth_required()
async def BanWord(ctx, *, words):
    channel = await get_serverconfig_channel(ctx.guild)
    word_list = [w.strip().lower() for w in words.split(",") if w.strip()]
    for word in word_list:
        await channel.send(f"WORD:{word}")
    await ctx.send(f"[OK] Added {len(word_list)} banned words.")

@bot.command()
@auth_required()
async def BanCDN(ctx):
    if not ctx.message.attachments:
        await ctx.send("Attach an image to blacklist.")
        return
    image_bytes = await ctx.message.attachments[0].read()
    img_hash = hash_image(image_bytes)
    channel = await get_serverconfig_channel(ctx.guild)
    await channel.send(f"IMG:{img_hash}")
    await ctx.send("[OK] Image hashed and blacklisted.")

@bot.command()
async def xhelp(ctx):
    embed = discord.Embed(title="Prototype Tool", color=0x008b8b)
    embed.description = (
        f"**Version:** {BOT_VERSION}\n"
        f"**Certificate:** `{BOT_CERT}`\n\n"
        "Use `>Auth` to authenticate."
    )
    embed.add_field(name=">Auth", value="Authenticate via DM password", inline=False)
    embed.add_field(name=">BanWord", value="Ban words (authenticated)", inline=False)
    embed.add_field(name=">BanCDN", value="Ban image hashes (authenticated)", inline=False)
    embed.add_field(name=">FWUP", value="Firmware update", inline=False)
    embed.add_field(name=">FHALT", value="Emergency shutdown", inline=False)
    await ctx.send(embed=embed)

# ----------------- EMERGENCY -----------------
@bot.command()
@auth_required()
async def FHALT(ctx):
    await ctx.send("[HALT] Bot shutting down.")
    await bot.close()

# ----------------- FIRMWARE UPDATE -----------------
async def fetch_update():
    async with aiohttp.ClientSession() as session:
        async with session.get(GITHUB_UPFW) as resp:
            if resp.status != 200:
                return None
            return await resp.text()

@bot.command()
@auth_required()
async def FWUP(ctx):
    await ctx.send("[INFO] Starting firmware update...")

    backup = STABLE_BACKUP
    shutil.copy(BOT_FILE, backup)
    await ctx.send(f"[OK] Backup created: {backup}")

    # Fetch new code from GitHub
    new_code = await fetch_update()
    if not new_code:
        await ctx.send("[FAIL] Could not download update.")
        return

    with open(BOT_FILE, "w") as f:
        f.write(new_code)

    # Mark updater for DM credential setup
    with open(UPDATE_FLAG, "w") as f:
        f.write(str(ctx.author.id))

    await ctx.send("[OK] Firmware updated. Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

# -----------------
if load_credentials():
    print("[OK] Credentials loaded.")
else:
    print("[WARN] No credentials found. Waiting for DM setup after FWUP.")
bot.run(TOKEN)
