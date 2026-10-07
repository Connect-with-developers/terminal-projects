# Social Media Automation System

Fully automated content creation and publishing system that:
1. 🔥 Scrapes trending topics from X (Twitter)
2. 🎥 Searches YouTube for relevant videos
3. 📝 Extracts English transcripts
4. 🎨 Generates carousels/posts automatically
5. 📱 Posts to Facebook, LinkedIn, Instagram

## Features

- **Trending Topic Detection**: Monitors X/Twitter for trending topics
- **YouTube Search**: Finds best English videos on trending topics
- **Transcript Extraction**: Gets full video transcripts
- **Content Generation**: Creates carousels and posts using AI
- **Multi-Platform Publishing**: Posts to Facebook, LinkedIn, Instagram
- **Scheduled Automation**: Can run on GitHub Actions or cron

## Project Structure

```
social-media-automation/
├── scrapers/
│   ├── twitter_trends.py      # Get trending topics from X
│   ├── youtube_search.py      # Search YouTube videos
│   └── transcript_extractor.py # Extract video transcripts
├── content_generator/
│   ├── carousel_creator.py    # Create carousel images
│   ├── post_writer.py         # Generate post captions
│   └── templates/             # Design templates
├── publishers/
│   ├── facebook_publisher.py  # Post to Facebook
│   ├── linkedin_publisher.py  # Post to LinkedIn
│   └── instagram_publisher.py # Post to Instagram
├── utils/
│   ├── database.py            # Track posted content
│   └── logger.py              # Logging system
├── config/
│   ├── config.json            # Configuration
│   └── credentials.json       # API credentials
├── output/                    # Generated content
│   ├── carousels/
│   ├── posts/
│   └── videos/
├── main.py                    # Main automation script
└── requirements.txt
```

## Installation

```bash
cd social-media-automation
pip install -r requirements.txt
```

## Configuration

1. Copy `config/config.example.json` to `config/config.json`
2. Add your API credentials for:
   - Twitter API (for trends)
   - YouTube Data API (for search)
   - Facebook Graph API
   - LinkedIn API
   - Instagram Graph API

## Usage

### Manual Run
```bash
python main.py
```

### Automated Run (GitHub Actions)
The workflow runs automatically based on schedule in `.github/workflows/social-automation.yml`

## API Requirements

### Twitter API
- Get from: https://developer.twitter.com/
- Needed for: Trending topics

### YouTube Data API
- Get from: https://console.cloud.google.com/
- Needed for: Video search and details

### Facebook/Instagram API
- Get from: https://developers.facebook.com/
- Needed for: Posting to Facebook and Instagram

### LinkedIn API
- Get from: https://www.linkedin.com/developers/
- Needed for: Posting to LinkedIn

## Features in Detail

### 1. Trending Topic Detection
- Monitors X/Twitter trending topics
- Filters by category (tech, business, etc.)
- Stores in database to avoid duplicates

### 2. YouTube Video Search
- Searches for trending topic keywords
- Filters for English videos only
- Finds videos with available transcripts
- Sorts by view count and relevance

### 3. Transcript Extraction
- Uses YouTube Transcript API
- Extracts English captions
- Cleans and formats text
- Summarizes long transcripts

### 4. Content Generation
- Creates 5-10 slide carousels
- Generates engaging captions
- Adds hashtags automatically
- Multiple design templates

### 5. Multi-Platform Publishing
- **Facebook**: Posts carousel + caption
- **LinkedIn**: Professional format
- **Instagram**: Square format + stories

## Workflow

```
1. Fetch trending topics from X
   ↓
2. Select topic not posted before
   ↓
3. Search YouTube for relevant videos
   ↓
4. Get English transcript
   ↓
5. Generate carousel slides
   ↓
6. Create engaging caption
   ↓
7. Post to Facebook
   ↓
8. Post to LinkedIn
   ↓
9. Post to Instagram
   ↓
10. Save to database
```

## Scheduling

### GitHub Actions (Free)
```yaml
schedule:
  - cron: '0 9,15,21 * * *'  # 3 times daily
```

### Local Cron
```bash
# Run 3 times daily
0 9,15,21 * * * cd /path/to/project && python main.py
```

## Safety Features

- ✅ Duplicate detection (won't post same topic twice)
- ✅ Rate limiting (respects API limits)
- ✅ Error handling and retry logic
- ✅ Content preview before posting
- ✅ Dry-run mode for testing

## Environment Variables

```bash
# Twitter
TWITTER_API_KEY=your_key
TWITTER_API_SECRET=your_secret
TWITTER_BEARER_TOKEN=your_token

# YouTube
YOUTUBE_API_KEY=your_key

# Facebook
FACEBOOK_ACCESS_TOKEN=your_token
FACEBOOK_PAGE_ID=your_page_id

# LinkedIn
LINKEDIN_ACCESS_TOKEN=your_token
LINKEDIN_ORG_ID=your_org_id

# Instagram
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_ACCOUNT_ID=your_account_id

# Optional: AI for content generation
OPENAI_API_KEY=your_key
```

## Todo / Roadmap

- [ ] Add TikTok support
- [ ] Video clips generation
- [ ] A/B testing for posts
- [ ] Analytics dashboard
- [ ] Multi-language support
- [ ] Custom brand templates
- [ ] Story generation for Instagram/Facebook
- [ ] Thread generation for X

## License

MIT

## Disclaimer

Use responsibly and follow platform terms of service. Ensure you have proper API access and permissions.
