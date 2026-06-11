# Telegram Sync Action for Obsidian Vault

This repository contains a self-contained GitHub Actions workflow and a Python script designed to sync messages and media from a Telegram Bot directly into your GitHub-backed Obsidian vault. 

Since GitHub Actions runs continuously on a cron schedule, it polls the Telegram Bot API in the background. This solves the **24-hour limit** where messages are lost if Obsidian is not opened within 24 hours of receiving them.

---

## Repository Structure

```text
.
├── .github
│   ├── scripts
│   │   └── telegram_sync.py      # Main Python polling and parsing script
│   └── workflows
│       └── telegram-sync.yml     # GitHub Actions workflow configuration
└── README.md                     # Setup and usage instructions
```

---

## How it Works

1. **Scheduled Polling**: Every 30 minutes, the GitHub Actions runner wakes up and runs `telegram_sync.py`.
2. **Retrieve Updates**: The script queries the Telegram Bot API `getUpdates` using your bot's secret token.
3. **State Preservation**: To avoid processing messages twice, a state file called `.github/telegram_sync_state.json` is maintained in the repository, keeping track of the last processed `update_id`.
4. **Rich Content Rendering**:
   - **Text & Captions**: Formatting (bold, italics, strike-through, code, text-links) is parsed and translated to standard Markdown.
   - **Media & Attachments**: Images, documents, voice notes, audios, and videos are automatically downloaded, saved to your attachments folder, and linked using Obsidian's native wiki-link syntax (`![[filename]]` or `[[filename]]`).
5. **Git Push**: If new messages or media are retrieved, the runner commits the changes and pushes them directly back to your repository. When you sync your Obsidian vault with GitHub on your devices, the new notes and attachments are instantly loaded.

---

## Setup Instructions

### Step 1: Add files to your Obsidian Vault Repository
Simply copy the `.github` folder from this repository into the root directory of your GitHub-backed Obsidian vault repository.

### Step 2: Set up Secrets in GitHub
In your GitHub vault repository:
1. Go to **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Create the following secrets:
   - `TELEGRAM_BOT_TOKEN`: The token provided by `@BotFather` when you created your bot.
   - `ALLOWED_CHATS`: (Optional) A comma-separated list of Telegram usernames (e.g. `your_username`) or numerical chat IDs that are authorized to sync to your vault. If left empty, all incoming messages sent to the bot will be synced.

### Step 3: Enable Workflow Write Permissions
For security reasons, GitHub workflows have read-only permissions by default. You must enable write permissions so the runner can push new notes back to your repository:
1. In your GitHub repository, go to **Settings** -> **Actions** -> **General**.
2. Scroll down to the **Workflow permissions** section.
3. Select **Read and write permissions**.
4. Click **Save**.

---

## Configuration Settings

You can customize how the synchronization behaves by editing the `env` block in `.github/workflows/telegram-sync.yml`:

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `NOTES_DIR` | The vault folder where notes are stored. | `Telegram` |
| `ATTACHMENTS_DIR`| The vault folder where images/files are saved. | `Telegram/Attachments` |
| `NOTE_FORMAT` | `daily` to group notes by day (`YYYY-MM-DD.md`) or `single` to append everything to `Inbox.md`. | `daily` |
| `TIMEZONE_OFFSET` | Your local timezone offset in decimal hours (e.g., `5.5` for GMT+5:30, `-8` for GMT-8). | `5.5` |

---

## Formatting Syntax

The script converts Telegram message types as follows:

* **Daily Note Header**: Appends `### HH:MM:SS - Sender` above each entry.
* **Single Note Header**: Appends `## YYYY-MM-DD HH:MM:SS - Sender (in ChatName)`.
* **Images, Voice Notes, Video & Audio**: Linked as embeds (`![[attachment.ext]]`).
* **Documents / PDFs**: Linked as inline links (`[[document.ext]]`).
* **Formatted Text**: Handles bold (`**bold**`), italic (`*italic*`), underline (`<u>underline</u>`), strikethrough (`~~strikethrough~~`), code (```code```), and hyperlinks.
