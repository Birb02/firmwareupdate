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

# ---------------- CONFIG ----------------

PREFIX = ">"
BOT_VERSION = "V.RS.22"
BOT_CERT = "USRSDADM1262X0B2"

AUTHORIZED_IDS = {949748857351340062, 479990917110038529}

BOT_FILE = os.path.abspath(__file__)
BACKUP_FILE = "stable_backup.py"
CRED_FILE = "credentials.json"
UPDATE_OPERATORS_FILE = "update_operators.json"

GITHUB_FW = "https://raw.githubusercontent.com/Birb02/firmwareupdate/main/UPFW.py"

TOKEN = None
BOT_PASSWORD = None

authenticated_users = set()

# ---------------- TOKEN LOADING ----------------

def get_token_from_backup():
    if not os.path.exists(BACKUP_FILE):
        return None
    try:
        with open(BACKUP_FILE) as f:
            content = f.read()
        match = re.search(r'TOKEN\s*=\s*["\'](.+?)["\']', content)
        if match:
            return match.group(1)
    except:
        pass
    return None

def load_credentials():
    global TOKEN, BOT_PASSWORD
    if os.path.exists(CRED_FILE):
        try:
            with open(CRED_FILE) as f:
                data = json.load(f)
            TOKEN = data.get("token")
            BOT_PASSWORD = data.get("password")
        except:
            print("[WARN] credentials.json corrupted")
            TOKEN = None
            BOT_PASSWORD = None

def load_password():
    global BOT_PASSWORD
    if not os.path.exists(CRED_FILE):
        return
    try:
        with open(CRED_FILE) as f:
            data = json.load(f)
        BOT_PASSWORD = data.get("password")
    except:
        print("[WARN] Could not read password from credentials.json")

def save_credentials(token, password):
    with open(CRED_FILE, "w") as f:
        json.dump(
            {"token": token, "password": password},
            f,
            indent=4
        )

# ---------------- STARTUP TOKEN LOGIC ----------------

def resolve_token():
    global TOKEN
    TOKEN = get_token_from_backup()
    if TOKEN:
        print("[INFO] Using token from stable_backup.py")
        load_password()   # FIX: ensure password loads
        return
    load_credentials()
    load_password()
    if TOKEN:
        print("[INFO] Using token from credentials.json")
        return
    print("[ERROR] No token detected.")
    print("Populate credentials.json manually.")
    if not os.path.exists(CRED_FILE):
        with open(CRED_FILE, "w") as f:
            f.write("{}")
    sys.exit(1)

# ---------------- DISCORD INIT ----------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ---------------- SERVERCONFIG ----------------

async def get_serverconfig_channel(guild):
    channel = discord.utils.get(guild.text_channels, name="serverconfig")
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        channel = await guild.create_text_channel(
            "serverconfig",
            overwrites=overwrites
        )
    return channel

async def get_banned_data(guild):
    channel = await get_serverconfig_channel(guild)
    banned_words = []
    banned_hashes = []
    async for msg in channel.history(limit=None):
        if msg.content.startswith("WORD:"):
            banned_words.append(msg.content[5:].strip())
        elif msg.content.startswith("IMG:"):
            banned_hashes.append(msg.content[4:].strip())
    return banned_words, banned_hashes

def hash_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.phash(img))

# ---------------- AUTH SYSTEM ----------------

def is_authenticated(uid):
    return uid in authenticated_users

def auth_required():
    async def predicate(ctx):
        if not is_authenticated(ctx.author.id):
            await ctx.send("You must authenticate using >Auth")
            return False
        return True
    return commands.check(predicate)

# ---------------- POST-UPDATE OPERATOR DM ----------------

async def post_update_operator_setup():
    if not os.path.exists(UPDATE_OPERATORS_FILE):
        return
    try:
        with open(UPDATE_OPERATORS_FILE) as f:
            data = json.load(f)
        operator_id = data.get("operator")
        user = await bot.fetch_user(operator_id)
        await user.send(
            "⚙ Firmware update completed.\n\n"
            "Keep existing credentials? (Y/N)"
        )
        def check(m):
            return m.author.id == operator_id and isinstance(m.channel, discord.DMChannel)
        msg = await bot.wait_for("message", check=check)
        if msg.content.lower() == "y":
            await user.send("✔ Existing credentials kept.")
        else:
            await user.send("Send **new bot token**:")
            msg = await bot.wait_for("message", check=check)
            new_token = msg.content.strip()
            await user.send("Send **new password**:")
            msg = await bot.wait_for("message", check=check)
            new_password = msg.content.strip()
            save_credentials(new_token, new_password)
            await user.send("✔ Credentials updated.")
        os.remove(UPDATE_OPERATORS_FILE)
        await user.send("⚙ Setup complete. System ready.")
    except Exception as e:
        print("[POST UPDATE SETUP ERROR]", e)

# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    print(f"[OK] Running {bot.user}")
    print(f"[INFO] Version {BOT_VERSION}")
    print(f"[INFO] Certificate {BOT_CERT}")
    await post_update_operator_setup()

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

# ---------------- AUTH ----------------

@bot.command()
async def Auth(ctx):
    if ctx.author.id not in AUTHORIZED_IDS:
        await ctx.send("Developer privileges revoked.")
        return
    try:
        await ctx.author.send("Enter bot password:")
    except:
        await ctx.send("Enable DMs.")
        return
    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
    msg = await bot.wait_for("message", check=check)
    if msg.content == BOT_PASSWORD:
        authenticated_users.add(ctx.author.id)
        await ctx.author.send("Authenticated.")
        await ctx.send("Authentication successful.")
    else:
        await ctx.author.send("Incorrect password.")

# ---------------- COMMANDS ----------------

@bot.command()
@auth_required()
async def BanWord(ctx, *, words):
    channel = await get_serverconfig_channel(ctx.guild)
    word_list = [w.strip().lower() for w in words.split(",")]
    for word in word_list:
        await channel.send(f"WORD:{word}")
    await ctx.send(f"Added {len(word_list)} banned words.")

@bot.command()
@auth_required()
async def BanCDN(ctx):
    if not ctx.message.attachments:
        await ctx.send("Attach image.")
        return
    image_bytes = await ctx.message.attachments[0].read()
    img_hash = hash_image(image_bytes)
    channel = await get_serverconfig_channel(ctx.guild)
    await channel.send(f"IMG:{img_hash}")
    await ctx.send("Image hash stored.")

# ---------------- HELP ----------------

@bot.command()
async def xhelp(ctx):
    embed = discord.Embed(
        title="Property of INGSOC",
        description="FOIK-Firmware Dependant Moderation ToolKit",
        color=0x008b8b
    )
    embed.add_field(
        name="System",
        value=f"Version: `{BOT_VERSION}`\nCertificate: `{BOT_CERT}`",
        inline=False
    )
    embed.add_field(
        name="Authentication",
        value="`>Auth` — Authenticate via DM password",
        inline=False
    )
    embed.add_field(
        name="Moderation",
        value="`>BanWord` — Ban words\n`>BanCDN` — Ban images",
        inline=False
    )
    embed.add_field(
        name="Firmware",
        value="`>FWUP` — Check and install firmware update",
        inline=False
    )
    embed.add_field(
        name="Emergency",
        value="`>FHALT` — Shutdown the bot",
        inline=False
    )
    embed.set_footer(text="First Of Its Kind, Sharp And Efficent.")
    await ctx.send(embed=embed)

# ---------------- EMERGENCY ----------------

@bot.command()
@auth_required()
async def FHALT(ctx):
    await ctx.send("Shutting down.")
    await bot.close()

# ---------------- FIRMWARE UPDATE ----------------

async def fetch_update():
    async with aiohttp.ClientSession() as session:
        async with session.get(GITHUB_FW) as resp:
            if resp.status != 200:
                return None
            return await resp.text()

@bot.command()
@auth_required()
async def FWUP(ctx):
    await ctx.send("[INFO] Checking firmware update...")
    new_code = await fetch_update()
    if not new_code:
        await ctx.send("Failed to download firmware.")
        return
    match = re.search(r'BOT_CERT\s*=\s*[\'"](.{16})[\'"]', new_code)
    if not match:
        await ctx.send("Invalid firmware.")
        return
    new_cert = match.group(1)
    if new_cert == BOT_CERT:
        await ctx.send("No update is needed.")
        return
    shutil.copy(BOT_FILE, BACKUP_FILE)
    await ctx.send("Backup created.")
    # Save operator for post-update DM
    with open(UPDATE_OPERATORS_FILE, "w") as f:
        json.dump({"operator": ctx.author.id}, f)
    with open(BOT_FILE, "w") as f:
        f.write(new_code)
    await ctx.send("Firmware installed. Restarting.")
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ---------------- MAIN ----------------

def main():
    try:
        resolve_token()
        bot.run(TOKEN)
    except Exception as e:
        print("[CRITICAL] Firmware error detected.")
        print(e)
        choice = input("Login with backup token? (Y/N): ")
        if choice.lower() == "y":
            token = get_token_from_backup()
            if token:
                bot.run(token)
        else:
            sys.exit(1)

main()
