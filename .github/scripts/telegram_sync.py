#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

# Load config from environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHATS = [x.strip() for x in os.environ.get("ALLOWED_CHATS", "").split(",") if x.strip()]
NOTES_DIR = os.environ.get("NOTES_DIR", "Telegram")
ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "Telegram/Attachments")
NOTE_FORMAT = os.environ.get("NOTE_FORMAT", "daily") # "daily" or "single"
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

def is_chat_allowed(chat):
    if not ALLOWED_CHATS:
        return True  # If empty, default to allowing all chats
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

def convert_entities_to_markdown(text, entities):
    if not entities or not text:
        return text
    
    # Sort entities in reverse order of offset to process from the end of the text.
    # This prevents character insertions from invalidating offsets of subsequent entities.
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

def sanitize_filename(name):
    return "".join(c for c in name if c.isalnum() or c in " .-_()").strip()

def process_message(msg):
    date_val = msg.get("date")
    if not date_val:
        return None
    
    dt = get_local_time(date_val)
    time_str = dt.strftime("%H:%M:%S")
    date_str = dt.strftime("%Y-%m-%d")
    
    # Determine note path
    if NOTE_FORMAT == "daily":
        note_name = f"{date_str}.md"
        note_path = os.path.join(NOTES_DIR, note_name)
    else:
        note_path = os.path.join(NOTES_DIR, "Inbox.md")
        
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
    
    # Photos
    if "photo" in msg:
        photo_sizes = msg["photo"]
        if photo_sizes:
            largest = photo_sizes[-1]
            file_id = largest["file_id"]
            safe_time = dt.strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_time}_photo.jpg"
            dest = os.path.join(ATTACHMENTS_DIR, filename)
            print(f"Downloading photo to {dest}...")
            if download_file(file_id, dest):
                attachments.append((filename, True))
                
    # Documents
    elif "document" in msg:
        doc = msg["document"]
        file_id = doc["file_id"]
        orig_name = sanitize_filename(doc.get("file_name", "document"))
        safe_time = dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_time}_{orig_name}"
        dest = os.path.join(ATTACHMENTS_DIR, filename)
        print(f"Downloading document to {dest}...")
        if download_file(file_id, dest):
            mime = doc.get("mime_type", "")
            is_embed = mime.startswith("image/") or mime.startswith("audio/") or mime.startswith("video/")
            attachments.append((filename, is_embed))
            
    # Voice notes
    elif "voice" in msg:
        voice = msg["voice"]
        file_id = voice["file_id"]
        safe_time = dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_time}_voice.ogg"
        dest = os.path.join(ATTACHMENTS_DIR, filename)
        print(f"Downloading voice note to {dest}...")
        if download_file(file_id, dest):
            attachments.append((filename, True))
            
    # Audio
    elif "audio" in msg:
        audio = msg["audio"]
        file_id = audio["file_id"]
        orig_name = sanitize_filename(audio.get("file_name", "audio.mp3"))
        safe_time = dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_time}_{orig_name}"
        dest = os.path.join(ATTACHMENTS_DIR, filename)
        print(f"Downloading audio to {dest}...")
        if download_file(file_id, dest):
            attachments.append((filename, True))
            
    # Video
    elif "video" in msg:
        video = msg["video"]
        file_id = video["file_id"]
        orig_name = sanitize_filename(video.get("file_name", "video.mp4"))
        safe_time = dt.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_time}_{orig_name}"
        dest = os.path.join(ATTACHMENTS_DIR, filename)
        print(f"Downloading video to {dest}...")
        if download_file(file_id, dest):
            attachments.append((filename, True))

    # Format entries
    entry_lines = []
    
    if NOTE_FORMAT == "daily":
        entry_lines.append(f"### {time_str} - {sender}")
    else:
        entry_lines.append(f"## {date_str} {time_str} - {sender} (in {chat_name})")
        
    for filename, is_embed in attachments:
        # Use Obsidian attachment relative format or standard wiki link
        if is_embed:
            entry_lines.append(f"![[{filename}]]")
        else:
            entry_lines.append(f"[[{filename}]]")
            
    if formatted_text:
        entry_lines.append(formatted_text)
        
    entry_content = "\n\n".join(entry_lines)
    
    # Save/Append to the note file
    os.makedirs(os.path.dirname(note_path), exist_ok=True)
    file_exists = os.path.exists(note_path)
    
    with open(note_path, "a", encoding="utf-8") as f:
        if not file_exists:
            title = os.path.splitext(os.path.basename(note_path))[0]
            f.write(f"# {title}\n\n")
        f.write(entry_content + "\n\n---\n\n")
        
    print(f"Successfully processed message to {note_path}")
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
                
    # Save the updated offset state back
    if max_update_id is not None:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({"last_update_id": max_update_id}, f)
            
    print(f"Done. Processed {processed_count} new messages. Updated last_update_id to {max_update_id}")

if __name__ == "__main__":
    main()
