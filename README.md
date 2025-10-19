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

#### Frontend

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:8080`

#### Edge Functions (Local Development)

1. **Install Supabase CLI**:
```bash
npm install -g supabase
```

2. **Start Supabase locally**:
```bash
supabase start
```

3. **Create secrets file** at `supabase/.env`:
```bash
DISCORD_TOKEN=your_discord_bot_token
SUMMARY_CHANNEL_ID=your_summary_channel_id
CHANNEL_IDS=comma_separated_channel_ids
GOOGLE_API_KEY=your_google_gemini_api_key
```

4. **Serve the edge function**:
```bash
supabase functions serve daily-ai-summary --env-file supabase/.env
```

5. **Test the function**:
```bash
curl -i --location --request POST 'http://localhost:54321/functions/v1/daily-ai-summary' \
  --header 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0' \
  --header 'Content-Type: application/json'
```

> Note: Update your frontend `.env` to point to local Supabase:
> ```
> VITE_SUPABASE_URL=http://localhost:54321
> ```

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
