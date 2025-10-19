# Discord AI Daily - TypeScript Edition

A TypeScript/React web application that automatically generates AI-powered daily news summaries from Discord channels.

## Features

- 🤖 **AI-Powered Summaries**: Uses Lovable AI (Google Gemini 2.5 Flash) to generate comprehensive news briefs
- 📱 **Discord Integration**: Scans specified Discord channels for daily content
- 🔗 **Smart URL Extraction**: Finds and deduplicates URLs from messages and embeds
- 📝 **Structured Output**: Generates organized Markdown summaries with sections for launches, research, funding, and more
- 🌐 **Web Dashboard**: Modern React UI to trigger summaries and view status
- ☁️ **Lovable Cloud Backend**: Serverless edge functions for all backend logic

## Architecture

### Frontend
- **Framework**: React 18 + TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Build**: Vite
- **State**: React Query for server state

### Backend
- **Runtime**: Deno (Lovable Cloud Edge Functions)
- **Database**: Supabase (via Lovable Cloud)
- **AI**: Lovable AI Gateway (Google Gemini)
- **APIs**: Discord API v10

## Setup Instructions

### Prerequisites
1. A Discord bot with Message Content Intent enabled
2. Discord bot invited to your server with permissions:
   - Read Messages
   - Read Message History
   - Send Messages
   - Embed Links

### Configuration

All secrets are managed through Lovable Cloud:

1. **DISCORD_TOKEN**: Your Discord bot token (starts with `Bot ` if copied from Discord)
2. **SUMMARY_CHANNEL_ID**: Numeric ID of the channel where summaries will be posted
3. **CHANNEL_IDS**: Comma-separated numeric IDs of channels to scan (e.g., `123456,789012`)

### Getting Channel IDs

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click any channel → Copy ID

### Running Locally

#### 1. Create a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### 3. Set Environment Variables

```bash
export DISCORD_TOKEN="your_discord_bot_token"
export CHANNEL_IDS="channel_id_1,channel_id_2"
export SUMMARY_CHANNEL_ID="summary_channel_id"
export GOOGLE_API_KEY="your_google_gemini_api_key"
```

Or create a `.env` file (not tracked in git) and load it before running.

#### 4. Run the Python Server

```bash
python daily_ai_summary.py
```

The server will start on `http://localhost:8000`

#### 5. Run the Frontend

```bash
npm install
npm run dev
```

The app will be available at `http://localhost:8080` and will call your local Python server at `http://localhost:8000`

### Deployment

This app is designed to run on Lovable:

1. Push changes to the connected GitHub repository
2. Lovable automatically deploys the app
3. Edge functions are deployed automatically

## How It Works

1. **Trigger**: Click "Run Summary Now" in the web UI
2. **Scan**: Edge function fetches messages from configured Discord channels from today (America/Chicago timezone)
3. **Extract**: Pulls all URLs from message content and embeds, then deduplicates
4. **Scrape**: Fetches article titles and descriptions from each URL
5. **Summarize**: Lovable AI generates a structured Markdown summary
6. **Post**: Summary is posted to Discord (inline if short, as file if >1800 chars)

## Summary Format

```markdown
# Daily AI News — YYYY-MM-DD (America/Chicago)

## TL;DR
- Key highlight 1
- Key highlight 2
...

## Notable Launches & Updates
- Product/feature announcements

## Research & Papers
- Academic and technical research

## Funding & Policy
- Investments and regulations

## All Links
- **[Title](URL)**: One-line summary
```

## Technology Stack

- **Frontend**: React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Deno, Lovable Cloud (Supabase)
- **AI**: Lovable AI Gateway (Google Gemini 2.5 Flash)
- **APIs**: Discord API v10
- **Deployment**: Lovable Cloud

## Project Structure

```
discord-ai-daily/
├── src/
│   ├── pages/
│   │   └── Index.tsx           # Main dashboard
│   ├── components/
│   │   └── ui/                 # shadcn/ui components
│   └── integrations/
│       └── supabase/           # Supabase client
├── supabase/
│   └── functions/
│       └── daily-ai-summary/   # Edge function
│           └── index.ts        # Main logic
└── README.md
```

## Edge Function Details

The `daily-ai-summary` edge function:
- Fetches Discord messages using Discord API v10
- Filters messages from current local day (America/Chicago)
- Normalizes and deduplicates URLs
- Scrapes article metadata
- Calls Lovable AI for summary generation
- Posts result to Discord channel

## Customization

### Change AI Model
Edit `supabase/functions/daily-ai-summary/index.ts`:
```typescript
model: 'google/gemini-2.5-flash'  // or 'google/gemini-2.5-pro'
```

### Modify Summary Structure
Update the prompt in the `generateSummary` function to change sections or formatting.

### Add Domain Filtering
Extend the `skipDomains` array in `scrapeArticle` to exclude specific sites.

## Troubleshooting

### No messages found
- Verify channel IDs are correct numeric IDs
- Check bot has access to the channels
- Ensure Message Content Intent is enabled

### Summary not posting
- Verify SUMMARY_CHANNEL_ID is correct
- Check bot has Send Messages permission
- Review edge function logs in Lovable Cloud

### Scraping issues
- Some sites block automated scraping
- Meta descriptions may be limited
- Timeout may occur for slow sites

## License

MIT

## Links

- [Lovable Documentation](https://docs.lovable.dev)
- [Discord Developer Portal](https://discord.com/developers)
- [Supabase Documentation](https://supabase.com/docs)
