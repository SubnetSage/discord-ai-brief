#!/usr/bin/env python3
"""
Discord AI Daily Summary Generator
Fetches links from Discord channels, scrapes articles, and generates AI summaries
"""

import os
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from urllib.parse import urlparse
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SUMMARY_CHANNEL_ID = os.getenv('SUMMARY_CHANNEL_ID')
CHANNEL_IDS = os.getenv('CHANNEL_IDS', '').split(',')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
APIFY_API_TOKEN = os.getenv('APIFY_API_TOKEN')

def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and converting to lowercase"""
    try:
        parsed = urlparse(url)
        # Remove fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.lower()
    except:
        return url

def format_date(date: datetime) -> str:
    """Format date as YYYY-MM-DD"""
    return date.strftime('%Y-%m-%d')

def get_discord_messages(channel_id: str, token: str) -> List[Dict]:
    """Fetch messages from a Discord channel"""
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=100"
    headers = {
        'Authorization': f'Bot {token}' if not token.startswith('Bot ') else token,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching messages from channel {channel_id}: {e}")
        return []

def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_reddit_url(url: str) -> bool:
    """Check if URL is a Reddit post"""
    return 'reddit.com' in url and ('/comments/' in url or '/r/' in url)

def get_reddit_thread(url: str) -> Optional[Dict[str, str]]:
    """Fetch Reddit thread content using Apify API"""
    if not APIFY_API_TOKEN:
        print(f"Skipping Reddit {url}: APIFY_API_TOKEN not configured")
        return None
    
    try:
        # Start Apify actor run
        actor_url = f"https://api.apify.com/v2/acts/trudax~reddit-scraper/runs?token={APIFY_API_TOKEN}"
        actor_payload = {
            'startUrls': [{'url': url}],
            'sort': 'new',
            'maxItems': 10,
            'maxPostCount': 10,
            'maxComments': 10,
            'scrollTimeout': 40,
            'proxy': {
                'useApifyProxy': True,
                'apifyProxyGroups': ['RESIDENTIAL']
            }
        }
        
        print(f"Starting Apify Reddit scraper for {url}...")
        run_response = requests.post(actor_url, json=actor_payload, timeout=30)
        run_response.raise_for_status()
        run_data = run_response.json()
        run_id = run_data['data']['id']
        
        # Poll for completion (max 60 seconds)
        status_url = f"https://api.apify.com/v2/acts/trudax~reddit-scraper/runs/{run_id}?token={APIFY_API_TOKEN}"
        for _ in range(30):  # 30 attempts * 2 seconds = 60 seconds max
            time.sleep(2)
            status_response = requests.get(status_url, timeout=10)
            status_response.raise_for_status()
            status = status_response.json()['data']['status']
            
            if status == 'SUCCEEDED':
                # Fetch dataset results
                dataset_id = run_data['data']['defaultDatasetId']
                dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_TOKEN}"
                dataset_response = requests.get(dataset_url, timeout=10)
                dataset_response.raise_for_status()
                results = dataset_response.json()
                
                if results and len(results) > 0:
                    post = results[0]
                    title = post.get('title', 'Reddit Thread')
                    text_content = post.get('text', '')
                    comments = post.get('comments', [])
                    
                    # Combine post text and top comments
                    content_parts = []
                    if text_content:
                        content_parts.append(f"Post: {text_content[:500]}")
                    
                    for comment in comments[:5]:  # Top 5 comments
                        comment_text = comment.get('text', '')
                        if comment_text:
                            content_parts.append(f"Comment: {comment_text[:200]}")
                    
                    combined_text = ' | '.join(content_parts)
                    return {
                        'url': url,
                        'title': title,
                        'text': f'[REDDIT THREAD] {combined_text[:2000]}'
                    }
                else:
                    print(f"No content found for {url}")
                    return {'url': url, 'title': 'Reddit Thread', 'text': '[REDDIT - No content available]'}
            
            elif status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                print(f"Apify run failed with status: {status}")
                return {'url': url, 'title': 'Reddit Thread', 'text': '[REDDIT - Scraping failed]'}
        
        print(f"Apify run timed out for {url}")
        return {'url': url, 'title': 'Reddit Thread', 'text': '[REDDIT - Scraping timed out]'}
        
    except Exception as e:
        print(f"Error fetching Reddit thread for {url}: {e}")
        return {'url': url, 'title': 'Reddit Thread', 'text': '[REDDIT - Error fetching content]'}

def get_youtube_transcript(url: str) -> Optional[Dict[str, str]]:
    """Fetch YouTube transcript via Apify API"""
    if not APIFY_API_TOKEN:
        print(f"Skipping YouTube {url}: APIFY_API_TOKEN not configured")
        return None
    
    video_id = extract_youtube_id(url)
    if not video_id:
        print(f"Could not extract video ID from {url}")
        return None
    
    try:
        # Get video title from YouTube page
        headers = {'User-Agent': 'AI-News-Summarizer/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
        title = title_match.group(1).strip().replace(' - YouTube', '') if title_match else f'YouTube Video {video_id}'
        
        # Start Apify actor run
        actor_url = f"https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/runs?token={APIFY_API_TOKEN}"
        actor_payload = {"videoUrl": url}
        
        print(f"Starting Apify actor for {url}...")
        run_response = requests.post(actor_url, json=actor_payload, timeout=30)
        run_response.raise_for_status()
        run_data = run_response.json()
        run_id = run_data['data']['id']
        
        # Poll for completion (max 60 seconds)
        status_url = f"https://api.apify.com/v2/acts/pintostudio~youtube-transcript-scraper/runs/{run_id}?token={APIFY_API_TOKEN}"
        for _ in range(30):  # 30 attempts * 2 seconds = 60 seconds max
            time.sleep(2)
            status_response = requests.get(status_url, timeout=10)
            status_response.raise_for_status()
            status = status_response.json()['data']['status']
            
            if status == 'SUCCEEDED':
                # Fetch dataset results
                dataset_id = run_data['data']['defaultDatasetId']
                dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_TOKEN}"
                dataset_response = requests.get(dataset_url, timeout=10)
                dataset_response.raise_for_status()
                results = dataset_response.json()
                
                if results and len(results) > 0 and 'transcript' in results[0]:
                    transcript_text = results[0]['transcript']
                    return {
                        'url': url,
                        'title': title,
                        'text': f'[VIDEO TRANSCRIPT] {transcript_text[:2000]}'
                    }
                else:
                    print(f"No transcript available for {url}")
                    return {'url': url, 'title': title, 'text': '[VIDEO - No transcript available]'}
            
            elif status in ['FAILED', 'ABORTED', 'TIMED-OUT']:
                print(f"Apify run failed with status: {status}")
                return {'url': url, 'title': title, 'text': '[VIDEO - Transcript extraction failed]'}
        
        print(f"Apify run timed out for {url}")
        return {'url': url, 'title': title, 'text': '[VIDEO - Transcript extraction timed out]'}
        
    except Exception as e:
        print(f"Error fetching YouTube transcript for {url}: {e}")
        return {'url': url, 'title': title if 'title' in locals() else f'YouTube Video {video_id}', 'text': '[VIDEO - Error fetching transcript]'}

def scrape_article(url: str) -> Optional[Dict[str, str]]:
    """Scrape article content from URL"""
    parsed = urlparse(url)
    
    # Handle YouTube URLs separately
    if 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
        return get_youtube_transcript(url)
    
    # Handle Reddit URLs
    if is_reddit_url(url):
        return get_reddit_thread(url)
    
    # Skip non-article domains
    skip_domains = ['twitter.com', 'x.com', 'imgur.com', 'giphy.com']
    if any(domain in parsed.netloc for domain in skip_domains):
        return None
    
    try:
        headers = {'User-Agent': 'AI-News-Summarizer/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        
        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else parsed.netloc
        
        # Extract meta description
        desc_match = re.search(
            r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']\s+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        text = desc_match.group(1) if desc_match else ''
        
        return {'url': url, 'title': title, 'text': text}
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def generate_summary(articles: List[Dict[str, str]], api_key: str) -> str:
    """Generate AI summary using Google Gemini"""
    date = format_date(datetime.now())
    
    # Prepare article list
    article_list = '\n\n'.join([
        f"{i+1}. {article['title']}\nURL: {article['url']}\nContent: {article['text'][:500]}"
        for i, article in enumerate(articles)
    ])
    
    prompt = f"""You are an AI news curator. Extract and summarize the notable AI news from these articles and videos.

Articles, Videos, and Discussions:
{article_list}

Note: Items prefixed with [VIDEO TRANSCRIPT] are YouTube video transcripts, [REDDIT THREAD] are Reddit discussions. Items with [VIDEO - ...] or [REDDIT - ...] are content without available transcripts/data.

Create a concise Markdown summary titled "# Daily AI News — {date} (America/Chicago)" that highlights the most important and interesting developments. Use concrete facts, no hype. Be specific about numbers, companies, and products. Include links to sources."""
    
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}'
    
    payload = {
        'contents': [{
            'parts': [{'text': prompt}]
        }],
        'generationConfig': {
            'temperature': 0.7,
            'topK': 40,
            'topP': 0.95,
            'maxOutputTokens': 8192
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Error generating summary: {e}")
        raise

def post_to_discord(token: str, channel_id: str, content: str):
    """Post message to Discord channel"""
    url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
    headers = {
        'Authorization': f'Bot {token}' if not token.startswith('Bot ') else token,
        'Content-Type': 'application/json'
    }
    
    # If content is too long, upload as file
    if len(content) > 1800:
        files = {
            'file': (f'ai-news-{format_date(datetime.now())}.md', content, 'text/markdown')
        }
        data = {
            'content': f"# Daily AI News Summary — {format_date(datetime.now())}\n\n*Summary attached as file (too long for inline message)*"
        }
        response = requests.post(
            url,
            headers={'Authorization': headers['Authorization']},
            data={'payload_json': json.dumps(data)},
            files=files
        )
    else:
        response = requests.post(url, headers=headers, json={'content': content})
    
    response.raise_for_status()

@app.route('/', methods=['POST', 'OPTIONS'])
def generate_summary_endpoint():
    """Main endpoint to generate daily summary"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        print('Starting daily AI summary generation...')
        
        # Log configuration (without sensitive data)
        print(f'DISCORD_TOKEN: {"✓ Set" if DISCORD_TOKEN else "✗ Missing"}')
        print(f'SUMMARY_CHANNEL_ID: {SUMMARY_CHANNEL_ID if SUMMARY_CHANNEL_ID else "✗ Missing"}')
        print(f'CHANNEL_IDS: {CHANNEL_IDS if CHANNEL_IDS else "✗ Missing"}')
        print(f'GOOGLE_API_KEY: {"✓ Set" if GOOGLE_API_KEY else "✗ Missing"}')
        print(f'APIFY_API_TOKEN: {"✓ Set" if APIFY_API_TOKEN else "✗ Missing"}')
        
        # Validate environment variables
        if not all([DISCORD_TOKEN, SUMMARY_CHANNEL_ID, CHANNEL_IDS, GOOGLE_API_KEY]):
            return jsonify({'error': 'Missing required environment variables'}), 500
        
        # Get date range - using last 48 hours to avoid timezone issues
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=48)
        
        print(f'Fetching messages from last 48 hours: {start_time} to {now}')
        
        # Collect all URLs from messages
        all_urls = set()
        url_pattern = re.compile(r'https?://[^\s<>()]+', re.IGNORECASE)
        
        for channel_id in CHANNEL_IDS:
            channel_id = channel_id.strip()
            if not channel_id:
                continue
            
            print(f'Fetching messages from channel {channel_id}...')
            messages = get_discord_messages(channel_id, DISCORD_TOKEN)
            print(f'Retrieved {len(messages)} messages from channel {channel_id}')
            
            # Filter messages from last 48 hours and extract URLs
            recent_messages = 0
            for message in messages:
                message_time = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                
                print(f'Message time (UTC): {message_time}, In range: {message_time >= start_time}')
                
                if message_time >= start_time:
                    recent_messages += 1
                    # Extract URLs from message content
                    content_urls = url_pattern.findall(message.get('content', ''))
                    print(f'Found {len(content_urls)} URLs in message content: {content_urls}')
                    for url in content_urls:
                        all_urls.add(normalize_url(url))
                    
                    # Extract URLs from embeds
                    for embed in message.get('embeds', []):
                        if embed.get('url'):
                            embed_url = embed['url']
                            print(f'Found URL in embed: {embed_url}')
                            all_urls.add(normalize_url(embed_url))
            
            print(f'Found {recent_messages} recent messages in channel {channel_id}')
        
        print(f'Found {len(all_urls)} unique URLs')
        
        if len(all_urls) == 0:
            no_links_message = f"# Daily AI News — {format_date(datetime.now())}\n\n*No links found for today.*"
            post_to_discord(DISCORD_TOKEN, SUMMARY_CHANNEL_ID, no_links_message)
            return jsonify({'success': True, 'linksFound': 0, 'message': 'No links found'}), 200
        
        # Scrape articles
        print('Scraping articles...')
        articles = []
        for url in all_urls:
            article_data = scrape_article(url)
            if article_data:
                articles.append(article_data)
        
        print(f'Successfully scraped {len(articles)} articles')
        
        # Generate summary using Google Gemini
        print('Generating AI summary...')
        summary = generate_summary(articles, GOOGLE_API_KEY)
        
        # Post to Discord
        post_to_discord(DISCORD_TOKEN, SUMMARY_CHANNEL_ID, summary)
        
        filename = f'ai-news-{format_date(datetime.now())}.md'
        print(f'Summary generated successfully: {filename}')
        
        return jsonify({
            'success': True,
            'linksFound': len(all_urls),
            'articlesScraped': len(articles),
            'filename': filename,
            'summary': summary[:200] + '...'
        }), 200
        
    except Exception as e:
        print(f'Error in daily-ai-summary: {e}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print('Starting Discord AI Daily Summary server on http://localhost:8000')
    print('Make sure you have set the following environment variables:')
    print('  - DISCORD_TOKEN')
    print('  - SUMMARY_CHANNEL_ID')
    print('  - CHANNEL_IDS (comma-separated)')
    print('  - GOOGLE_API_KEY')
    app.run(host='0.0.0.0', port=8000, debug=True)
