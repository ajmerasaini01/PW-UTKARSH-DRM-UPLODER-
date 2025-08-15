import os
import threading
import asyncio
import time
import logging
import re
import json
import requests
import subprocess
from subprocess import getstatusoutput
from flask import Flask
from dotenv import load_dotenv

# ================== ENV & SETUP ==================
load_dotenv()
os.makedirs("./downloads", exist_ok=True)

# ---- Credentials (already filled from your provided values) ----
API_ID = 24119778
API_HASH = "cca11ca97dd8683d65ca1beb62baceb1"
BOT_TOKEN = "7208534557:AAH9zDoXCjMJkm8ahqsJTsljAzbeSe20Xic"
STRING = "AQFwCeIAOz1FS7JecfYU8zMZdNCoey8c3cbpOlG0CmPPY9mXBXyG2C0_Uf83cWS_dI38I16qpCyuggIpwc2LrcYQtUXEbyjxtfRWl3jif61NDbq95dMqvSLJkYz6xGaPas5qCfMubSwdkxgaFc_ejU1A5Fglp4RsPKnH_G4OjF_wEUAzNiWn0PhTVlUT-au6thdjfR-hsPvGUnksl4bTRb4BfR0cFsh0X8Tg14_KGJRMBGUN2URG1PO1ATGpiFDPmUDFco2SwQIW6VadpUUROTUD70z0SnAvQ7aZMD7MvpovTdHO8YJVu0GiMT5qJZKtNGHUzKj4rdxiKdHoA0_9z5h2pIR20QAAAAGrb7QLAA"
AUTH_USERS = 7171191819
sudo_users = [7171191819]

# न्यूनतम वेलिडेशन
if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("Please set API_ID, API_HASH, BOT_TOKEN correctly.")

# ================== Flask Server ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running fine on Render."

def run_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ================== Pyrogram Imports ==================
from pyrogram import Client, filters
from pyromod import listen
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, User
import tgcrypto
import helper
from p_bar import progress_bar
from get_video_info import get_video_attributes, get_video_thumb

# ================== Pyrogram Bot Init ==================
bot = Client(
    "bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

DEF_FORMAT = "480"

# एक ही Client नाम रखें (conflicts से बचने के लिए)
bot = Client(
    "bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

# ----- async exec helper -----
async def aexec(cmd_list):
    proc = await asyncio.create_subprocess_exec(
        *cmd_list,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        print(stdout.decode(errors="ignore"))
    return proc.returncode, stderr.decode(errors="ignore")


# ================== HANDLERS ==================
@bot.on_message(filters.command(["start"]))
async def start_cmd(_, m: Message):
    await m.reply_text("**Hi BOSS, I'm Alive!**\n\nCommands:\n- /down → download\n- /cpd → classplus\n- /cancel → cancel\n- /restart → restart")

@bot.on_message(filters.command(["cancel"]))
async def cancel_cmd(_, m: Message):
    await m.reply_text("Canceled.")
    return

@bot.on_message(filters.command("restart"))
async def restart_handler(_, m: Message):
    await m.reply_text("Restarted!", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

# -------------- /down --------------
@bot.on_message(filters.command(["down"]))
async def down_cmd(_, m: Message):
    editable = await m.reply_text("**Send a text file containing URLs**")
    file_msg: Message = await bot.listen(editable.chat.id)
    x = await file_msg.download()
    await file_msg.delete(True)

    try:
        with open(x, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip().splitlines()
        links = []
        for line in content:
            if ":" in line:
                links.append(line.split(":", 1))
        os.remove(x)
        if not links:
            await m.reply_text("No valid links found in file.")
            return
    except Exception:
        await m.reply_text("Invalid file input.")
        try:
            os.remove(x)
        except Exception:
            pass
        return

    editable = await editable.edit(f"Total links found: **{len(links)}**\nSend start index (default **0**)")

    try:
        idx_msg: Message = await bot.listen(editable.chat.id)
        arg = int(idx_msg.text.strip())
    except Exception:
        arg = 0

    editable = await editable.edit("**Enter Batch Name**")
    bn_msg: Message = await bot.listen(editable.chat.id)
    batch_name = bn_msg.text.strip()

    editable = await editable.edit("**Downloaded By (name)**")
    by_msg: Message = await bot.listen(editable.chat.id)
    downloaded_by = by_msg.text.strip()

    await editable.edit("**Enter resolution (e.g., 144/240/360/480/720)**")
    res_msg: Message = await bot.listen(editable.chat.id)
    vid_format = (res_msg.text or DEF_FORMAT).strip()

    editable = await editable.edit(
        "Now send **Thumb URL** (or type **no**)\nEg: https://telegra.ph/file/cef3ef6ee69126c23bfe3.jpg"
    )
    thumb_msg: Message = await bot.listen(editable.chat.id)
    thumb = thumb_msg.text.strip()

    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = 1 if str(arg) == "0" else int(arg)
    for i in range(arg, len(links)):
        try:
            url = links[i][1].strip()
            name = (
                links[i][0]
                .replace("\t", "")
                .replace(":", "")
                .replace("/", "")
                .replace("+", "")
                .replace("#", "")
                .replace("|", "")
                .replace("@", "")
                .replace("*", "")
                .replace(".", "")
                .strip()
            )
        except Exception:
            continue

        # yt-dlp command build
        ytf = None
        out = {}
        cmd_list = [
            "yt-dlp",
            "--no-warnings",
            "--socket-timeout", "30",
            "-R", "25",
            "--fragment-retries", "25",
            "--external-downloader", "aria2c",
            "--downloader-args", "aria2c: -x 16 -j 32",
            url
        ]

        try:
            if "youtu" in url:
                ytf = f"b[height<={vid_format}][ext=mp4]/bv[height<={vid_format}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            elif ".m3u8" in url or "livestream" in url:
                ytf = f"b[height<={vid_format}]/bv[height<={vid_format}]+ba"
            elif url.endswith(".mp4"):
                ytf = f"b[height<={vid_format}]/bv[height<={vid_format}]+ba"
            elif url.endswith(".pdf"):
                # PDF direct download
                r = requests.get(url, allow_redirects=True, timeout=60)
                if r.status_code == 200:
                    pdf_name = f"{name}.pdf"
                    with open(pdf_name, "wb") as f:
                        f.write(r.content)
                    caption_pdf = f'{str(count).zfill(2)}. {name}\n\n**Batch »** {batch_name}\n**Downloaded By »** {downloaded_by}'
                    await bot.send_document(m.chat.id, pdf_name, caption=caption_pdf)
                    count += 1
                    try:
                        os.remove(pdf_name)
                    except Exception:
                        pass
                continue
            else:
                # generic probe to pick a format
                probe_cmd = f'yt-dlp -F "{url}"'
                k = await helper.run(probe_cmd)
                out = helper.vid_info(str(k)) or {}
                # pick any available format as fallback
                if out:
                    first_key = next(iter(out.keys()))
                    ytf = out.get(first_key, None)

            if not ytf:
                # final fallback to best
                ytf = "bestvideo+bestaudio/best"

            # Output pattern
            file_out = f"{name}.%(ext)s"
            cmd_list.extend(["-f", ytf, "-o", file_out])

            show = f"**Downloading**: `{name}`\n**Quality**: {vid_format}\n**URL**: `{url}`"
            prog = await m.reply_text(show)

            # run download
            _, _stderr = await aexec(cmd_list)

            # After download, try send mp4 if exists
            mp4_path = f"{name}.mp4"
            if not os.path.exists(mp4_path):
                # maybe mkv
                mkv_path = f"{name}.mkv"
                if os.path.exists(mkv_path):
                    mp4_path = mkv_path

            if thumb == "no":
                thumbnail = f"{name}.jpg" if os.path.exists(f"{name}.jpg") else None
            else:
                thumbnail = "thumb.jpg" if os.path.exists("thumb.jpg") else None

            try:
                # duration/width/height (best effort)
                try:
                    duration, width, height = get_video_attributes(mp4_path)
                except Exception:
                    duration = width = height = 0

                caption_vid = f'{str(count).zfill(2)}. {name} - {vid_format}p\n\n**Batch »** {batch_name}\n**Downloaded By »** {downloaded_by}'
                await bot.send_video(
                    m.chat.id,
                    video=mp4_path,
                    caption=caption_vid,
                    duration=duration or None,
                    width=width or None,
                    height=height or None,
                    file_name=name,
                    supports_streaming=True
                )
                count += 1
                await prog.delete(True)
            except Exception as e:
                await m.reply_text(f"Upload error: {e}")

            # cleanup
            for ext in (".mp4", ".mkv", ".jpg"):
                try:
                    if os.path.exists(f"{name}{ext}"):
                        os.remove(f"{name}{ext}")
                except Exception:
                    pass

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            await m.reply_text(f"Error: {e}")
            continue


# -------------- /cpd --------------
@bot.on_message(filters.command(["cpd"]))
async def cpd_cmd(_, m: Message):
    editable = await m.reply_text("Send txt file")
    file_msg: Message = await bot.listen(editable.chat.id)
    x = await file_msg.download()
    await file_msg.delete(True)

    try:
        with open(x, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().strip().splitlines()
        links = [ln.split(":", 1) for ln in lines if ":" in ln]
        os.remove(x)
        if not links:
            await m.reply_text("No valid links found.")
            return
    except Exception:
        await m.reply_text("Invalid file input.")
        try:
            os.remove(x)
        except Exception:
            pass
        return

    editable = await m.reply_text(
        f"Total links: **{len(links)}**\nSend start index (default **0**)"
    )
    try:
        idx_msg: Message = await bot.listen(editable.chat.id)
        arg = int(idx_msg.text.strip())
    except Exception:
        arg = 0

    editable = await m.reply_text("**Enter Title**")
    title_msg: Message = await bot.listen(editable.chat.id)
    title = title_msg.text.strip()

    await m.reply_text("**Enter resolution** (e.g., 144/240/360/480/720)")
    res_msg: Message = await bot.listen(editable.chat.id)
    res = res_msg.text.strip()

    editable4 = await m.reply_text(
        "Send **Thumb URL** (or **no**)\nEg: https://telegra.ph/file/d9e24878bd4aba05049a1.jpg"
    )
    tmsg: Message = await bot.listen(editable.chat.id)
    thumb = tmsg.text.strip()
    if thumb.startswith("http://") or thumb.startswith("https://"):
        getstatusoutput(f"wget '{thumb}' -O 'thumb.jpg'")
        thumb = "thumb.jpg"
    else:
        thumb = "no"

    count = 1 if arg == 0 else int(arg)

    for i in range(arg, len(links)):
        try:
            url = links[i][1].strip()
            name1 = (
                links[i][0]
                .replace("\t", "")
                .replace(":", "")
                .replace("/", "")
                .replace("+", "")
                .replace("#", "")
                .replace("|", "")
                .replace("@", "")
                .replace("*", "")
                .replace("download", ".pdf")
                .replace(".", "")
                .strip()
            )
        except Exception:
            continue

        # PDF shortcut
        if url.endswith(".pdf") or "pdf" in name1.lower():
            fname = f"{str(count).zfill(3)}) {name1.replace('pdf', '')}.pdf"
            try:
                r = requests.get(url, allow_redirects=True, timeout=60)
                if r.status_code == 200:
                    with open(fname, "wb") as f:
                        f.write(r.content)
                    try:
                        await bot.send_document(m.chat.id, fname, file_name=fname, caption=fname)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    count += 1
            finally:
                try:
                    if os.path.exists(fname):
                        os.remove(fname)
                except Exception:
                    pass
            continue

        # बाकी logic (formats) – best effort simple:
        ytf = f"bestvideo[height<={res}]+bestaudio/best"
        name = name1
        out_name = f'{str(count).zfill(3)}) {name}'

        if "player.vimeo" in url:
            # simple vimeo mapping
            if res == '144' or res == '240':
                ytf = 'http-240p'
            elif res == '360':
                ytf = 'http-360p'
            elif res == '480':
                ytf = 'http-540p'
            elif res == '720':
                ytf = 'http-720p'
            else:
                ytf = 'http-360p'

        # classplus special signing
        if "videos.classplusapp" in url:
            headers = {
                'Host': 'api.classplusapp.com',
                'x-access-token': 'REDACTED',  # ← अपना वैध टोकन env से लें
                'user-agent': 'Mobile-Android',
                'app-version': '1.4.37.1',
                'api-version': '18',
                'device-id': 'device-id',
                'device-details': 'SDK-30',
                'accept-encoding': 'gzip'
            }
            params = (('url', f'{url}'),)
            try:
                response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url',
                                        headers=headers, params=params, timeout=60)
                url = response.json().get('url', url)
            except Exception:
                pass

        cmd = f'yt-dlp -o "{out_name}.%(ext)s" -f "{ytf}" --no-keep-video --remux-video mkv "{url}"'
        await m.reply_text(f"**Downloading**\n`{out_name}`\n`{url}`")

        # run shell via helper (as in your original)
        try:
            _ = await helper.run(cmd)
        except Exception as e:
            await m.reply_text(f"Download error: {e}")
            continue

        # pick produced file
        sent = False
        for ext in (".mp4", ".mkv"):
            fpath = f"{out_name}{ext}"
            if os.path.exists(fpath):
                try:
                    await bot.send_document(m.chat.id, fpath, caption=f"{out_name}")
                    sent = True
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    await m.reply_text(f"Upload error: {e}")
                finally:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                break

        if sent:
            count += 1


# ================== RUN BOTH (SERVER + BOT) ==================
if __name__ == "__main__":
    # Flask keep-alive (Render) in background thread
    threading.Thread(target=run_server, daemon=True).start()
    # Start Telegram bot (block)
    bot.run()
