import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import "https://deno.land/x/xhr@0.1.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface DiscordMessage {
  id: string;
  content: string;
  embeds: Array<{ url?: string; description?: string }>;
  timestamp: string;
}

interface ArticleData {
  url: string;
  title: string;
  text: string;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    console.log('Starting daily AI summary generation...');
    
    const DISCORD_TOKEN = Deno.env.get('DISCORD_TOKEN');
    const SUMMARY_CHANNEL_ID = Deno.env.get('SUMMARY_CHANNEL_ID');
    const CHANNEL_IDS = Deno.env.get('CHANNEL_IDS');
    const GOOGLE_API_KEY = Deno.env.get('GOOGLE_API_KEY');
    const APIFY_API_TOKEN = Deno.env.get('APIFY_API_TOKEN');

    if (!DISCORD_TOKEN || !SUMMARY_CHANNEL_ID || !CHANNEL_IDS || !GOOGLE_API_KEY) {
      throw new Error('Missing required environment variables');
    }

    // Normalize Discord token (add Bot prefix if not present)
    const discordAuth = DISCORD_TOKEN.startsWith('Bot ') ? DISCORD_TOKEN : `Bot ${DISCORD_TOKEN}`;
    console.log('Discord auth configured:', discordAuth.substring(0, 15) + '...');

    const channelIds = CHANNEL_IDS.split(',').map(id => id.trim());
    console.log(`Scanning channels: ${channelIds.join(', ')}`);

    // Get today's date range (America/Chicago timezone)
    const now = new Date();
    const chicagoOffset = -6 * 60; // CST offset in minutes
    const localNow = new Date(now.getTime() + chicagoOffset * 60000);
    const startOfDay = new Date(localNow.setHours(0, 0, 0, 0));
    const endOfDay = new Date(localNow.setHours(23, 59, 59, 999));

    console.log(`Date range: ${startOfDay.toISOString()} to ${endOfDay.toISOString()}`);

    // Collect all URLs from messages
    const allUrls = new Set<string>();
    const urlRegex = /(https?:\/\/[^\s<>()]+)/gi;

    for (const channelId of channelIds) {
      console.log(`Fetching messages from channel ${channelId}...`);
      
      const response = await fetch(
        `https://discord.com/api/v10/channels/${channelId}/messages?limit=100`,
        {
          headers: {
            'Authorization': discordAuth,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        console.error(`Failed to fetch messages from ${channelId}: ${response.status}`);
        continue;
      }

      const messages: DiscordMessage[] = await response.json();
      console.log(`Retrieved ${messages.length} messages from channel ${channelId}`);

      // Filter messages from today and extract URLs
      for (const message of messages) {
        const messageTime = new Date(message.timestamp);
        if (messageTime >= startOfDay && messageTime <= endOfDay) {
          // Extract URLs from message content
          const contentUrls = message.content.match(urlRegex) || [];
          contentUrls.forEach(url => {
            const normalized = normalizeUrl(url);
            // Skip reddit.com links
            if (!normalized.includes('reddit.com')) {
              allUrls.add(normalized);
            }
          });

          // Extract URLs from embeds
          message.embeds.forEach(embed => {
            if (embed.url) {
              const normalized = normalizeUrl(embed.url);
              // Skip reddit.com links
              if (!normalized.includes('reddit.com')) {
                allUrls.add(normalized);
              }
            }
          });
        }
      }
    }

    console.log(`Found ${allUrls.size} unique URLs`);

    if (allUrls.size === 0) {
      const noLinksMessage = `# Daily AI News — ${formatDate(new Date())}\n\n*No links found for today.*`;
      await postToDiscord(discordAuth, SUMMARY_CHANNEL_ID, noLinksMessage);
      return new Response(
        JSON.stringify({ success: true, linkCount: 0, message: 'No links found' }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Scrape articles
    console.log('Scraping articles...');
    const articles: ArticleData[] = [];
    
    for (const url of Array.from(allUrls)) {
      try {
        const articleData = await scrapeArticle(url);
        if (articleData) {
          articles.push(articleData);
        }
      } catch (error) {
        console.error(`Failed to scrape ${url}:`, error);
      }
    }

    console.log(`Successfully scraped ${articles.length} articles`);

    // Validate we have content before generating summary
    if (articles.length === 0) {
      const noContentMessage = `# Daily AI News — ${formatDate(new Date())}\n\n*No articles could be scraped from the ${allUrls.size} links found.*`;
      await postToDiscord(discordAuth, SUMMARY_CHANNEL_ID, noContentMessage);
      return new Response(
        JSON.stringify({ success: true, linkCount: allUrls.size, articleCount: 0, message: 'No articles scraped' }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // Debug: Show sample of what we're sending to AI
    console.log('\n--- Scraped Articles Sample ---');
    articles.slice(0, 3).forEach((article, i) => {
      console.log(`${i+1}. ${article.title.substring(0, 60)}...`);
      console.log(`   Content length: ${article.text.length} chars`);
      console.log(`   Is video: ${article.text.includes('VIDEO TRANSCRIPT')}`);
    });
    console.log('--- End Sample ---\n');

    // Generate summary using Google Gemini
    console.log('Generating AI summary...');
    const summary = await generateSummary(articles, GOOGLE_API_KEY);

    // Post to Discord
    await postToDiscord(discordAuth, SUMMARY_CHANNEL_ID, summary);

    // Save as markdown file
    const filename = `ai-news-${formatDate(new Date())}.md`;
    console.log(`Summary generated successfully: ${filename}`);

    return new Response(
      JSON.stringify({ 
        success: true, 
        linkCount: allUrls.size,
        articleCount: articles.length,
        filename,
        summary: summary.substring(0, 200) + '...'
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in daily-ai-summary:', error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});

function normalizeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    // Remove fragments and normalize
    parsed.hash = '';
    return parsed.toString().toLowerCase();
  } catch {
    return url;
  }
}

function extractYouTubeId(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes('youtube.com')) {
      return parsed.searchParams.get('v');
    } else if (parsed.hostname.includes('youtu.be')) {
      return parsed.pathname.slice(1);
    }
  } catch {
    return null;
  }
  return null;
}

async function getYouTubeTranscript(url: string): Promise<ArticleData | null> {
  const videoId = extractYouTubeId(url);
  if (!videoId) {
    console.log(`Could not extract video ID from URL: ${url}`);
    return null;
  }

  const APIFY_API_TOKEN = Deno.env.get('APIFY_API_TOKEN');
  
  if (!APIFY_API_TOKEN) {
    console.log("⚠ APIFY_API_TOKEN not set, skipping transcript");
    // Return basic info without transcript
    try {
      const response = await fetch(url);
      const html = await response.text();
      const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
      const title = titleMatch ? titleMatch[1].trim() : `YouTube Video ${videoId}`;
      return {
        url,
        title,
        text: '[VIDEO - No transcript available]'
      };
    } catch {
      return null;
    }
  }

  try {
    // Get video title first
    const response = await fetch(url);
    const html = await response.text();
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1].trim() : `YouTube Video ${videoId}`;

    console.log(`🎬 Fetching transcript for: ${title}`);

    // Call Apify actor to get transcript
    const apifyUrl = `https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/runs?token=${APIFY_API_TOKEN}`;
    const apifyPayload = {
      videoUrl: url
    };

    // Start the actor run
    const runResponse = await fetch(apifyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apifyPayload),
    });

    if (!runResponse.ok) {
      throw new Error(`Apify API error: ${runResponse.status}`);
    }

    const runData = await runResponse.json();
    const runId = runData.data.id;
    const datasetId = runData.data.defaultDatasetId;

    // Poll for completion (with timeout)
    const maxWait = 60; // seconds
    let waited = 0;
    let status = '';

    while (waited < maxWait) {
      const statusUrl = `https://api.apify.com/v2/actor-runs/${runId}?token=${APIFY_API_TOKEN}`;
      const statusResponse = await fetch(statusUrl);
      const statusData = await statusResponse.json();
      status = statusData.data.status;

      if (['SUCCEEDED', 'FAILED', 'ABORTED'].includes(status)) {
        break;
      }

      await new Promise(resolve => setTimeout(resolve, 2000));
      waited += 2;
    }

    // Get the dataset results if succeeded
    if (status === 'SUCCEEDED') {
      const datasetUrl = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${APIFY_API_TOKEN}`;
      const datasetResponse = await fetch(datasetUrl);
      const datasetItems = await datasetResponse.json();

      if (datasetItems && datasetItems.length > 0) {
        const transcriptData = datasetItems[0];
        const transcriptText = transcriptData.transcript || '';

        if (transcriptText) {
          console.log(`✓ Got transcript for video: ${title}`);
          return {
            url,
            title,
            text: `[VIDEO TRANSCRIPT] ${transcriptText.slice(0, 2000)}`
          };
        }
      }
    }

    // If we get here, transcript fetch failed
    console.log(`⚠ Could not get transcript for ${url}`);
    return {
      url,
      title,
      text: '[VIDEO - No transcript available]'
    };

  } catch (error) {
    console.error(`⚠ Error fetching transcript for ${url}:`, error);
    // Return basic info even without transcript
    try {
      const response = await fetch(url);
      const html = await response.text();
      const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
      const title = titleMatch ? titleMatch[1].trim() : `YouTube Video ${videoId}`;
      return {
        url,
        title,
        text: '[VIDEO - No transcript available]'
      };
    } catch {
      return null;
    }
  }
}

function formatDate(date: Date): string {
  return date.toISOString().split('T')[0]; // YYYY-MM-DD
}

async function scrapeArticle(url: string): Promise<ArticleData | null> {
  try {
    const urlObj = new URL(url);
    
    // Handle YouTube videos separately
    if (urlObj.hostname.includes('youtube.com') || urlObj.hostname.includes('youtu.be')) {
      return await getYouTubeTranscript(url);
    }
    
    // Skip other non-article URLs
    const skipDomains = ['twitter.com', 'x.com', 'imgur.com', 'giphy.com'];
    if (skipDomains.some(domain => urlObj.hostname.includes(domain))) {
      return null;
    }

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'AI-News-Summarizer/1.0',
      },
    });

    if (!response.ok) return null;

    const html = await response.text();
    
    // Extract title from HTML
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    const title = titleMatch ? titleMatch[1].trim() : urlObj.hostname;

    // Extract meta description as fallback content
    const descMatch = html.match(/<meta\s+(?:name|property)=["'](?:description|og:description)["']\s+content=["']([^"']+)["']/i);
    const text = descMatch ? descMatch[1] : '';

    return { url, title, text };
  } catch (error) {
    console.error(`Error scraping ${url}:`, error);
    return null;
  }
}

async function generateSummary(articles: ArticleData[], apiKey: string): Promise<string> {
  const date = formatDate(new Date());
  
  // Validate articles have content
  const validArticles = articles.filter(a => a.text && a.text.trim().length > 20);
  
  if (validArticles.length === 0) {
    return `# Daily AI News — ${date}\n\n*No substantial content could be extracted from the articles found.*`;
  }
  
  // Prepare article list with clear indication of content type
  const articleList = validArticles.map((article, idx) => 
    `${idx + 1}. ${article.title}\nURL: ${article.url}\nContent: ${article.text.substring(0, 500)}`
  ).join('\n\n');

  const prompt = `You are generating a daily AI news summary. Below are ${validArticles.length} articles and videos that were shared today.

IMPORTANT: You must immediately generate the summary in the specified format. Do not ask for more information.

Articles and Videos:
${articleList}

Generate a Markdown summary NOW with this exact structure:

# Daily AI News — ${date} (America/Chicago)

## TL;DR
(5-10 bullet points of the most important updates)

## Notable Launches & Updates
(Product releases, feature announcements)

## Research & Papers
(Academic papers, technical research)

## Funding & Policy
(Investments, regulations, policy changes)

## Video Summaries
(For videos with transcripts, provide a concise summary of the key points discussed)

## All Links
(For each article/video: - **[Title](URL)**: One-line summary)

Use concrete facts, no hype. Be specific about numbers, companies, and products. For video transcripts, provide a brief summary of the main topics discussed.`;

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          contents: [{
            parts: [{
              text: prompt
            }]
          }],
          generationConfig: {
            temperature: 0.7,
            topK: 40,
            topP: 0.95,
            maxOutputTokens: 8192,
          }
        }),
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Google API error:', errorText);
      throw new Error(`Google API error: ${response.status}`);
    }

    const data = await response.json();
    return data.candidates[0].content.parts[0].text;
  } catch (error) {
    console.error('Error generating summary:', error);
    throw error;
  }
}

async function postToDiscord(token: string, channelId: string, content: string): Promise<void> {
  // If content is too long, upload as file
  if (content.length > 1800) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const formData = new FormData();
    formData.append('files[0]', blob, `ai-news-${formatDate(new Date())}.md`);
    formData.append('payload_json', JSON.stringify({
      content: `# Daily AI News Summary — ${formatDate(new Date())}\n\n*Summary attached as file (too long for inline message)*`
    }));

    await fetch(`https://discord.com/api/v10/channels/${channelId}/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bot ${token}`,
      },
      body: formData,
    });
  } else {
    await fetch(`https://discord.com/api/v10/channels/${channelId}/messages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bot ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content }),
    });
  }
}
