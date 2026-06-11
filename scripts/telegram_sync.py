#!/usr/bin/env python3
import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# Load config from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHATS = [x.strip() for x in os.environ.get("ALLOWED_CHATS", "").split(",") if x.strip()]

# Path template configurations (matching Obsidian plugin style)
NOTE_PATH_TEMPLATE = os.environ.get("NOTE_PATH_TEMPLATE", "Telegram/{{messageDate:YYYY-MM-DD}}.md")
FILE_PATH_TEMPLATE = os.environ.get("FILE_PATH_TEMPLATE", "Telegram/Attachments/{{file:name}}.{{file:extension}}")
MESSAGE_TEMPLATE = os.environ.get("MESSAGE_TEMPLATE", "### {{messageTime:HH:mm:ss}} - {{user:name}} (in {{chat:name}})\n{{files}}\n\n{{content}}")

TZ_OFFSET = float(os.environ.get("TIMEZONE_OFFSET", "0"))
STATE_FILE = ".github/telegram_sync_state.json"

if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
    sys.exit(1)

def make_request(url, data=None):
    req = urllib.request.Request(url)
    if data:
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(data).encode('utf-8')
        response = urllib.request.urlopen(req, jsondata)
    else:
        response = urllib.request.urlopen(req)
    return json.loads(response.read().decode('utf-8'))

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?timeout=10"
    if offset:
        url += f"&offset={offset}"
    res = make_request(url)
    if res.get("ok"):
        return res.get("result", [])
    return []

def get_file_url(file_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    res = make_request(url)
    if res.get("ok"):
        file_path = res["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}", file_path
    return None, None

def download_file(file_id, dest_path):
    download_url, _ = get_file_url(file_id)
    if download_url:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with urllib.request.urlopen(download_url) as response, open(dest_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
        return True
    return False

def set_reaction(chat_id, message_id, emoji):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMessageReaction"
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}]
    }
    try:
        make_request(url, data)
        return True
    except Exception as e:
        print(f"Failed to set message reaction: {e}")
        return False

def is_chat_allowed(chat):
    if not ALLOWED_CHATS:
        return True
    chat_id = str(chat.get("id"))
    username = chat.get("username", "")
    for allowed in ALLOWED_CHATS:
        if allowed == chat_id:
            return True
        if username and (allowed == username or allowed == f"@{username}"):
            return True
    return False

def get_local_time(unix_time):
    dt_utc = datetime.fromtimestamp(unix_time, tz=timezone.utc)
    dt_local = dt_utc + timedelta(hours=TZ_OFFSET)
    return dt_local

def format_dt(dt, moment_fmt):
    res = moment_fmt
    
    # Hour 24
    if "HH" in res:
        res = res.replace("HH", dt.strftime("%H"))
    elif "H" in res:
        res = res.replace("H", str(dt.hour))
        
    # Hour 12
    if "hh" in res:
        res = res.replace("hh", dt.strftime("%I"))
    elif "h" in res:
        res = res.replace("h", str(int(dt.strftime("%I"))))
        
    # Minutes
    if "mm" in res:
        res = res.replace("mm", dt.strftime("%M"))
    elif "m" in res:
        res = res.replace("m", str(dt.minute))
        
    # Seconds
    if "ss" in res:
        res = res.replace("ss", dt.strftime("%S"))
    elif "s" in res:
        res = res.replace("s", str(dt.second))
        
    # Year
    if "YYYY" in res:
        res = res.replace("YYYY", dt.strftime("%Y"))
    elif "YY" in res:
        res = res.replace("YY", dt.strftime("%y"))
        
    # Month
    if "MM" in res:
        res = res.replace("MM", dt.strftime("%m"))
        
    # Day
    if "DD" in res:
        res = res.replace("DD", dt.strftime("%d"))
        
    # AM/PM
    if "a" in res:
        res = res.replace("a", dt.strftime("%p").lower())
    if "A" in res:
        res = res.replace("A", dt.strftime("%p").upper())
        
    # Timezone offset representation
    if "zz" in res:
        sign = "+" if TZ_OFFSET >= 0 else "-"
        abs_offset = abs(TZ_OFFSET)
        hours = int(abs_offset)
        minutes = int((abs_offset - hours) * 60)
        tz_str = f"GMT{sign}{hours:02d}:{minutes:02d}"
        res = res.replace("zz", tz_str)
    elif "z" in res:
        sign = "+" if TZ_OFFSET >= 0 else "-"
        abs_offset = abs(TZ_OFFSET)
        hours = int(abs_offset)
        minutes = int((abs_offset - hours) * 60)
        tz_str = f"GMT{sign}{hours:02d}:{minutes:02d}"
        res = res.replace("z", tz_str)
        
    return res

def sanitize_filename(name):
    # Keep alphanumeric characters, spaces, dashes, dots, and underscores
    return "".join(c for c in name if c.isalnum() or c in " .-_()").strip()

def process_variables(template, msg, file_info=None):
    date_val = msg.get("date")
    dt = get_local_time(date_val) if date_val else datetime.now()
    
    def repl_message_date(match):
        fmt = match.group(1)
        return format_dt(dt, fmt)
        
    def repl_date(match):
        now_dt = datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET)
        fmt = match.group(1)
        return format_dt(now_dt, fmt)

    template = re.sub(r"{{messageDate:(.*?)}}", repl_message_date, template)
    template = re.sub(r"{{messageTime:(.*?)}}", repl_message_date, template)
    template = re.sub(r"{{date:(.*?)}}", repl_date, template)
    template = re.sub(r"{{time:(.*?)}}", repl_date, template)
    
    from_user = msg.get("from", {})
    username = from_user.get("username", "")
    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    
    chat = msg.get("chat", {})
    chat_name = chat.get("title") or chat.get("username") or "Private Chat"
    chat_id = str(chat.get("id", ""))
    
    template = template.replace("{{user:name}}", sanitize_filename(username or "unknown"))
    template = template.replace("{{user:fullName}}", sanitize_filename(full_name or "unknown"))
    template = template.replace("{{userId}}", chat_id)
    template = template.replace("{{chat:name}}", sanitize_filename(chat_name))
    template = template.replace("{{chatId}}", chat_id)
    template = template.replace("{{messageId}}", str(msg.get("message_id", "")))
    
    if file_info:
        template = template.replace("{{file:type}}", file_info.get("type", ""))
        template = template.replace("{{file:name}}", sanitize_filename(file_info.get("name", "")))
        template = template.replace("{{file:extension}}", file_info.get("extension", ""))
        
    return template

def get_unique_path(path):
    if not os.path.exists(path):
        return path
    dir_name, file_name = os.path.split(path)
    base_name, ext = os.path.splitext(file_name)
    counter = 1
    while True:
        new_name = f"{base_name}_{counter}{ext}"
        new_path = os.path.join(dir_name, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def convert_entities_to_markdown(text, entities):
    if not entities or not text:
        return text
    
    sorted_entities = sorted(entities, key=lambda e: e.get('offset', 0), reverse=True)
    
    for entity in sorted_entities:
        offset = entity.get('offset', 0)
        length = entity.get('length', 0)
        type_ = entity.get('type')
        
        start = offset
        end = offset + length
        
        entity_text = text[start:end]
        
        if type_ == 'bold':
            replacement = f"**{entity_text}**"
        elif type_ == 'italic':
            replacement = f"*{entity_text}*"
        elif type_ == 'underline':
            replacement = f"<u>{entity_text}</u>"
        elif type_ == 'strikethrough':
            replacement = f"~~{entity_text}~~"
        elif type_ == 'code':
            replacement = f"`{entity_text}`"
        elif type_ == 'pre':
            replacement = f"```\n{entity_text}\n```"
        elif type_ == 'text_link':
            url = entity.get('url', '')
            replacement = f"[{entity_text}]({url})"
        else:
            replacement = entity_text
            
        text = text[:start] + replacement + text[end:]
        
    return text

def process_message(msg):
    date_val = msg.get("date")
    if not date_val:
        return None
    
    dt = get_local_time(date_val)
    time_str = dt.strftime("%H:%M:%S")
    
    # Resolve note path using variables
    note_path = process_variables(NOTE_PATH_TEMPLATE, msg)
    if not note_path.endswith(".md"):
        note_path += ".md"
        
    # Get sender info
    from_user = msg.get("from", {})
    sender = from_user.get("username")
    if not sender:
        first_name = from_user.get("first_name", "")
        last_name = from_user.get("last_name", "")
        sender = f"{first_name} {last_name}".strip() or "Unknown"
        
    chat = msg.get("chat", {})
    chat_name = chat.get("title") or chat.get("username") or "Private Chat"
    
    # Check if chat is allowed
    if not is_chat_allowed(chat):
        print(f"Skipping message from unauthorized chat: {chat_name} (ID: {chat.get('id')})")
        return None

    # Get text/caption
    text = msg.get("text", "")
    caption = msg.get("caption", "")
    entities = msg.get("entities", [])
    caption_entities = msg.get("caption_entities", [])
    
    formatted_text = ""
    if text:
        formatted_text = convert_entities_to_markdown(text, entities)
    elif caption:
        formatted_text = convert_entities_to_markdown(caption, caption_entities)
        
    # Process attachments
    attachments = []
    
    def process_attachment(file_id, file_type, orig_name, default_ext, is_embed):
        safe_time = dt.strftime("%Y%m%d_%H%M%S")
        base_name, ext = os.path.splitext(orig_name) if orig_name else (f"{safe_time}_{file_type}", default_ext)
        if not ext:
            ext = default_ext
        if ext.startswith("."):
            ext = ext[1:]
            
        file_info = {
            "type": file_type,
            "name": base_name,
            "extension": ext
        }
        
        # Resolve attachment path using variables
        raw_dest_path = process_variables(FILE_PATH_TEMPLATE, msg, file_info)
        # Ensure it has the correct extension if template didn't specify it
        if not raw_dest_path.endswith(f".{ext}"):
            _, raw_ext = os.path.splitext(raw_dest_path)
            if not raw_ext:
                raw_dest_path += f".{ext}"
                
        dest_path = get_unique_path(raw_dest_path)
        print(f"Downloading {file_type} to {dest_path}...")
        
        if download_file(file_id, dest_path):
            filename_for_link = os.path.basename(dest_path)
            attachments.append((filename_for_link, is_embed))

    # Photos
    if "photo" in msg:
        photo_sizes = msg["photo"]
        if photo_sizes:
            largest = photo_sizes[-1]
            process_attachment(largest["file_id"], "photo", "", "jpg", True)
                
    # Documents
    elif "document" in msg:
        doc = msg["document"]
        mime = doc.get("mime_type", "")
        is_embed = mime.startswith("image/") or mime.startswith("audio/") or mime.startswith("video/")
        process_attachment(doc["file_id"], "document", doc.get("file_name", "document"), "bin", is_embed)
            
    # Voice notes
    elif "voice" in msg:
        voice = msg["voice"]
        process_attachment(voice["file_id"], "voice", "", "ogg", True)
            
    # Audio
    elif "audio" in msg:
        audio = msg["audio"]
        process_attachment(audio["file_id"], "audio", audio.get("file_name", "audio.mp3"), "mp3", True)
            
    # Video
    elif "video" in msg:
        video = msg["video"]
        process_attachment(video["file_id"], "video", video.get("file_name", "video.mp4"), "mp4", True)

    # Format entries using MESSAGE_TEMPLATE
    embeds = "\n".join(f"![[{f}]]" for f, is_embed in attachments if is_embed)
    links = "\n".join(f"[[{f}]]" for f, _ in attachments)
    
    entry_content = MESSAGE_TEMPLATE
    entry_content = entry_content.replace("{{files}}", embeds)
    entry_content = entry_content.replace("{{files:links}}", links)
    entry_content = entry_content.replace("{{content:text}}", formatted_text)
    entry_content = entry_content.replace("{{content}}", formatted_text)
    
    # Process date/time/user/chat variables
    entry_content = process_variables(entry_content, msg)
    
    # Clean up excess consecutive newlines that can result from empty values (e.g. no attachments)
    entry_content = entry_content.strip()
    entry_content = re.sub(r'\n{3,}', '\n\n', entry_content)
    
    # Save/Append to the note file
    os.makedirs(os.path.dirname(note_path), exist_ok=True)
    file_exists = os.path.exists(note_path)
    
    with open(note_path, "a", encoding="utf-8") as f:
        if not file_exists:
            title = os.path.splitext(os.path.basename(note_path))[0]
            f.write(f"# {title}\n\n")
        f.write(entry_content + "\n\n---\n\n")
        
    print(f"Successfully processed message to {note_path}")
    
    # React to the message to indicate it has been processed
    chat_id = chat.get("id")
    message_id = msg.get("message_id")
    if chat_id and message_id:
        emoji = "👍"
        if "edit_date" in msg:
            emoji = "🦄"
        set_reaction(chat_id, message_id, emoji)
        
    return True

def main():
    last_update_id = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                last_update_id = state.get("last_update_id")
        except Exception as e:
            print(f"Warning: could not read state file: {e}")
            
    print(f"Fetching updates from Telegram. Last update ID: {last_update_id}")
    
    offset = last_update_id + 1 if last_update_id is not None else None
    updates = get_updates(offset)
    
    if not updates:
        print("No new updates.")
        return
        
    processed_count = 0
    max_update_id = last_update_id
    
    for update in updates:
        update_id = update.get("update_id")
        if update_id is not None:
            max_update_id = max(max_update_id or 0, update_id)
            
        msg = update.get("message") or update.get("channel_post") or update.get("edited_message") or update.get("edited_channel_post")
        if msg:
            try:
                if process_message(msg):
                    processed_count += 1
            except Exception as e:
                print(f"Error processing update {update_id}: {e}")
                import traceback
                traceback.print_exc()
                
    # Save state
    if max_update_id is not None:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"last_update_id": max_update_id}, f)
            
    print(f"Done. Processed {processed_count} new messages. Updated last_update_id to {max_update_id}")

if __name__ == "__main__":
    main()
