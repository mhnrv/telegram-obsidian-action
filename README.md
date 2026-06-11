# Telegram Sync Action for Obsidian Vault

This is a reusable GitHub Action designed to sync messages and media from a Telegram Bot directly into a Git-backed Obsidian vault. 

Since GitHub Actions runs continuously on a cron schedule, it polls the Telegram Bot API in the background. This solves the **24-hour limit** where messages are lost if Obsidian is not opened within 24 hours of sending them.

By deploying this repository to GitHub, you and anyone else can use it directly in a workflow without copying any Python scripts or code!

---

## Repository Structure

```text
.
├── scripts
│   └── telegram_sync.py      # Main Python polling and parsing script
├── action.yml                # Custom Composite Action configuration
└── README.md                 # Setup and usage instructions
```

---

## How to Use This Action in a Vault Repository

### Step 1: Create a Workflow File
In your GitHub-backed Obsidian vault repository, create a file named `.github/workflows/telegram-sync.yml` and add the following content:

```yaml
name: Telegram Sync to Vault

on:
  schedule:
    # Run every 30 minutes
    - cron: '*/30 * * * *'
  workflow_dispatch: # Allows manual trigger from the GitHub Actions tab

jobs:
  sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Fetch all history so push works cleanly

      - name: Run Telegram Sync Action
        uses: mhnrv/telegram-obsidian-action@main
        with:
          telegram_bot_token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          allowed_chats: ${{ secrets.ALLOWED_CHATS }}
          note_path_template: 'Telegram/{{messageDate:YYYY-MM-DD}}.md'
          file_path_template: 'Telegram/Attachments/{{file:name}}.{{file:extension}}'
          timezone_offset: '5.5' # Adjust to your timezone offset (e.g. 5.5 is GMT+5:30)

      - name: Commit and Push changes
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          
          # Check if there are changes to commit (new notes, attachments, or state json)
          if [ -n "$(git status --porcelain)" ]; then
            git add .
            git commit -m "sync: pull new messages and attachments from Telegram"
            git push
          else
            echo "No new messages to sync."
          fi
```

### Step 2: Set up Secrets in GitHub
In your Obsidian vault's GitHub repository:
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

## Action Inputs Configuration

You can customize how the synchronization behaves by changing the `with` parameters in your workflow:

| Input Parameter | Description | Default Value |
| :--- | :--- | :--- |
| `telegram_bot_token`| **Required**. The Telegram bot token from BotFather. | N/A |
| `allowed_chats` | Comma-separated list of allowed user names or chat IDs. | `''` (allows all) |
| `note_path_template`| Obsidian note path template with variable support. | `'Telegram/{{messageDate:YYYY-MM-DD}}.md'` |
| `file_path_template`| Attachment file path template with variable support. | `'Telegram/Attachments/{{file:name}}.{{file:extension}}'` |
| `timezone_offset` | Your local timezone offset in decimal hours (e.g., `5.5` for GMT+5:30). | `'0'` |
| `message_template` | The template for formatting each message inside the note. | See default below |
| `note_header_template`| The template for the header written at the top of a new note file. | `''` (no header) |

*Default `message_template`:*
```text
### {{messageTime:HH:mm:ss}} - {{user:name}} (in {{chat:name}})
{{files}}

{{content}}
```

---

## Message Template Customization

You can structure how messages are formatted inside your Obsidian notes using the `message_template` input. For example, if you want all messages appended to your note to follow this structure:
```text
HH:MM am/pm GMTOffset : MessageText

AttachmentLinks
```

You can configure your workflow step like this:
```yaml
      - name: Run Telegram Sync Action
        uses: mhnrv/telegram-obsidian-action@main
        with:
          telegram_bot_token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          allowed_chats: ${{ secrets.ALLOWED_CHATS }}
          note_path_template: 'Telegram/{{messageDate:YYYY-MM-DD}}.md'
          file_path_template: 'Telegram/Attachments/{{file:name}}.{{file:extension}}'
          timezone_offset: '5.5'
          message_template: |
            {{messageTime:hh:mm a z}} : {{content:text}}  
            
            {{files:links}}
```

### Supported Message Variables

Inside the `message_template`, you can use all path variables listed below, plus these message-specific variables:

* `{{content}}` or `{{content:text}}`: The message text or caption converted to Markdown formatting.
* `{{files}}`: The list of downloaded attachments formatted as embedded wiki-links (e.g., `![[attachment.jpg]]`).
* `{{files:links}}`: The list of downloaded attachments formatted as non-embedded wiki-links (e.g., `[[document.pdf]]`).

---

## Path & Date Variables

The action parses and replaces the following variables inside both path templates and message templates:

* **Date & Time**: 
  - `{{messageDate:FORMAT}}` / `{{messageTime:FORMAT}}`: The date/time when the message was sent.
  - `{{date:FORMAT}}` / `{{time:FORMAT}}`: The current execution date/time.
  - *Note: FORMAT supports standard tokens like `YYYY`, `YY`, `MM`, `DD`, `HH`, `hh` (12-hour), `mm`, `ss`, `a`/`A` (am/pm), and `z`/`zz` (GMT offset label like `GMT+05:30`).*
* **Sender Info**: `{{user:name}}` (username), `{{user:fullName}}` (first + last name), `{{userId}}`.
* **Chat Info**: `{{chat:name}}` (group/chat title), `{{chatId}}`, `{{messageId}}`.
* **Attachment Info (File Path only)**: `{{file:type}}` (photo/voice/document/etc.), `{{file:name}}` (sanitized original file name), `{{file:extension}}`.
