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
In your GitHub-backed Obsidian vault repository, create a file named `.github/workflows/telegram-sync.yml` and add the following content (replace `your-username/telegram-sync-action` with your actual repository name):

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

    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4
        with:
          fetch-depth: 0 # Fetch all history so push works cleanly

      - name: Run Telegram Sync Action
        uses: your-username/telegram-sync-action@main
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

---

## Action Inputs Configuration

You can customize how the synchronization behaves by changing the `with` parameters in your workflow:

| Input Parameter | Description | Default Value |
| :--- | :--- | :--- |
| `telegram_bot_token`| **Required**. The Telegram bot token from BotFather. | N/A |
| `allowed_chats` | Comma-separated list of allowed user names or chat IDs. | `''` (allows all) |
| `note_path_template`| Obsidian note path template with variable support. | `'Telegram/{{messageDate:YYYY-MM-DD}}.md'` |
| `file_path_template`| Attachment file path template with variable support. | `'Telegram/Attachments/{{file:name}}.{{file:extension}}'` |
| `timezone_offset` | Your local timezone offset in decimal hours (e.g., `5.5` for GMT+5:30). | `'0'` |

---

## Path Variables

The action parses and replaces the following variables inside the path templates:

* **Date & Time**: `{{messageDate:FORMAT}}`, `{{messageTime:FORMAT}}`, `{{date:FORMAT}}`, `{{time:FORMAT}}` (e.g., `YYYY-MM-DD` formats).
* **Sender Info**: `{{user:name}}`, `{{user:fullName}}`, `{{userId}}`.
* **Chat Info**: `{{chat:name}}`, `{{chatId}}`, `{{messageId}}`.
* **Attachment Info**: `{{file:type}}` (e.g., photo, voice, document), `{{file:name}}` (sanitized original file name), `{{file:extension}}`.
