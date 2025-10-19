#!/usr/bin/env python3
"""
Discord AI Daily Summary Generator
Fetches links from Discord channels, scrapes articles, and generates AI summaries
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlparse
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Configuration from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SUMMARY_CHANNEL_ID = os.getenv('SUMMARY_CHANNEL_ID')
CHANNEL_IDS = os.getenv('CHANNEL_IDS', '').split(',')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

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

def scrape_article(url: str) -> Optional[Dict[str, str]]:
    """Scrape article content from URL"""
    # Skip non-article domains
    skip_domains = ['youtube.com', 'youtu.be', 'twitter.com', 'x.com', 'imgur.com', 'giphy.com']
    parsed = urlparse(url)
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
    
    prompt = f"""You are an AI news curator. Generate a concise daily brief from these AI-related articles.

Articles:
{article_list}

Create a Markdown summary with this exact structure:

# Daily AI News — {date} (America/Chicago)

## TL;DR
(5-10 bullet points of the most important updates)

## Notable Launches & Updates
(Product releases, feature announcements)

## Research & Papers
(Academic papers, technical research)

## Funding & Policy
(Investments, regulations, policy changes)

## All Links
(For each article: - **[Title](URL)**: One-line summary)

Use concrete facts, no hype. Be specific about numbers, companies, and products."""
    
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
        
        # Validate environment variables
        if not all([DISCORD_TOKEN, SUMMARY_CHANNEL_ID, CHANNEL_IDS, GOOGLE_API_KEY]):
            return jsonify({'error': 'Missing required environment variables'}), 500
        
        # Get today's date range (America/Chicago timezone)
        now = datetime.now()
        # Chicago is UTC-6 (CST) or UTC-5 (CDT)
        chicago_offset = timedelta(hours=-6)
        chicago_now = now + chicago_offset
        start_of_day = chicago_now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = chicago_now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        print(f'Date range: {start_of_day} to {end_of_day}')
        
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
            
            # Filter messages from today and extract URLs
            for message in messages:
                message_time = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                # Convert to Chicago time
                message_time_chicago = message_time + chicago_offset
                
                if start_of_day <= message_time_chicago <= end_of_day:
                    # Extract URLs from message content
                    content_urls = url_pattern.findall(message.get('content', ''))
                    for url in content_urls:
                        all_urls.add(normalize_url(url))
                    
                    # Extract URLs from embeds
                    for embed in message.get('embeds', []):
                        if embed.get('url'):
                            all_urls.add(normalize_url(embed['url']))
        
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
