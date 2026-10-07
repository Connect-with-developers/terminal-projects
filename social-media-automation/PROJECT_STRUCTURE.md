# Social Media Automation - Project Structure

## 📁 Complete File Structure

```
social-media-automation/
│
├── .github/
│   └── workflows/
│       └── social-automation.yml      # GitHub Actions workflow
│
├── config/
│   └── config.example.json            # Configuration template
│
├── scrapers/
│   ├── __init__.py
│   ├── twitter_trends.py              # Fetch trending topics from X
│   ├── youtube_search.py              # Search YouTube videos
│   └── transcript_extractor.py        # Extract video transcripts
│
├── content_generator/
│   ├── __init__.py
│   ├── carousel_creator.py            # Create carousel images
│   └── post_writer.py                 # Generate post captions
│
├── publishers/                         # (To be implemented)
│   ├── __init__.py
│   ├── facebook_publisher.py          # Post to Facebook
│   ├── linkedin_publisher.py          # Post to LinkedIn
│   └── instagram_publisher.py         # Post to Instagram
│
├── utils/
│   ├── __init__.py
│   ├── database.py                    # (Future) Database helpers
│   └── logger.py                      # (Future) Logging utilities
│
├── output/
│   ├── carousels/                     # Generated carousel images
│   ├── posts/                         # Generated post content
│   └── videos/                        # (Future) Video clips
│
├── main.py                            # Main automation script
├── test_components.py                 # Component testing script
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variables template
├── .gitignore                         # Git ignore rules
├── README.md                          # Full documentation
├── QUICKSTART.md                      # Quick start guide
└── automation_history.json            # (Generated) Post history
```

## 🔄 Automation Flow

```
1. Twitter/X Trends
   └─> Get trending topics
   └─> Filter by keywords and volume
   └─> Select best topic
        │
        ↓
2. YouTube Search
   └─> Search videos for topic
   └─> Filter by views, language, captions
   └─> Select best video
        │
        ↓
3. Transcript Extraction
   └─> Get video transcript (English)
   └─> Clean and process text
   └─> Extract key points
        │
        ↓
4. Content Generation
   ├─> Generate carousel slides
   │   └─> Create images with text
   │   └─> Apply color scheme
   │   └─> Add branding
   │
   └─> Generate post captions
       └─> Platform-specific format
       └─> Add hashtags
       └─> Include CTA
        │
        ↓
5. Publishing (Manual/Auto)
   ├─> Post to Instagram
   ├─> Post to LinkedIn
   └─> Post to Facebook
        │
        ↓
6. History Tracking
   └─> Save to database
   └─> Prevent duplicates
   └─> Track performance
```

## 🎯 Key Features

### ✅ Implemented
- [x] Twitter trends scraping
- [x] YouTube video search
- [x] Transcript extraction
- [x] Carousel image generation (5 color schemes)
- [x] Post caption generation (template-based)
- [x] AI content generation (OpenAI)
- [x] Multi-platform support (Instagram, LinkedIn, Facebook)
- [x] Duplicate detection
- [x] GitHub Actions automation
- [x] Dry-run mode for testing

### 🚧 To Be Implemented
- [ ] Facebook API publishing
- [ ] LinkedIn API publishing
- [ ] Instagram API publishing
- [ ] Video clip generation
- [ ] Story generation
- [ ] Analytics tracking
- [ ] A/B testing
- [ ] Custom brand templates
- [ ] Multi-language support

## 🔑 Required API Keys

### Minimum (for testing)
- `YOUTUBE_API_KEY` - YouTube Data API v3

### Recommended
- `TWITTER_API_KEY` - Twitter API for trends
- `TWITTER_API_SECRET`
- `TWITTER_BEARER_TOKEN`

### Optional (better content)
- `OPENAI_API_KEY` - AI-generated captions

### For Publishing
- `FACEBOOK_ACCESS_TOKEN` - Facebook Graph API
- `FACEBOOK_PAGE_ID`
- `INSTAGRAM_ACCESS_TOKEN` - Instagram Graph API
- `INSTAGRAM_ACCOUNT_ID`
- `LINKEDIN_ACCESS_TOKEN` - LinkedIn API
- `LINKEDIN_ORG_ID`

## 🎨 Carousel Color Schemes

1. **modern_blue** - Professional dark blue theme
2. **vibrant** - Bold purple and orange
3. **minimal** - Clean white background
4. **dark** - Sleek black theme
5. **gradient_purple** - Purple gradient

## 📊 Output Examples

### Carousel Slide Structure
```
Slide 1: Title/Intro
Slide 2-6: Key Points (from transcript)
Slide 7: Call to Action
```

### Post Caption Structure
```
🎥 [Video Title]

Key Takeaways:
💡 Point 1
✨ Point 2
🚀 Point 3

[Engagement Question]

#hashtag1 #hashtag2 ...
```

## 🚀 Usage Examples

### Basic Test Run
```bash
python main.py --dry-run
```

### Test Individual Components
```bash
python test_components.py
```

### With Custom Config
```bash
python main.py --config custom_config.json --dry-run
```

### GitHub Actions (Automatic)
- Runs 3x daily at 9 AM, 3 PM, 9 PM UTC
- Generates content and commits to repo
- Manual trigger available in Actions tab

## 📈 Scaling Strategy

### Phase 1 (Current)
- Manual posting
- Single trending topic per run
- Template-based content

### Phase 2 (Next)
- Automated posting via APIs
- Multiple topics per day
- AI-enhanced content

### Phase 3 (Future)
- Video clip generation
- Story automation
- Analytics dashboard
- A/B testing
- Multi-account support

## 🔒 Security Notes

- Never commit `.env` file
- Use GitHub Secrets for Actions
- Rotate API keys regularly
- Monitor API usage/quotas
- Review generated content before posting

## 💡 Best Practices

1. **Always test first** - Use `--dry-run`
2. **Review content** - Check quality before posting
3. **Monitor history** - Avoid duplicate topics
4. **Respect limits** - Watch API quotas
5. **Customize branding** - Adjust color schemes
6. **Schedule wisely** - Post at peak engagement times
7. **Track performance** - Analyze what works

## 🐛 Common Issues

### Issue: No transcript found
- **Solution**: Try different video, not all have captions

### Issue: Twitter API error
- **Solution**: Use fallback topics, Twitter not critical

### Issue: Rate limit exceeded
- **Solution**: Reduce frequency or upgrade API plan

### Issue: Poor quality content
- **Solution**: Enable AI generation with OpenAI key

## 📚 Resources

- [Twitter API Docs](https://developer.twitter.com/)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Facebook Graph API](https://developers.facebook.com/)
- [LinkedIn API](https://docs.microsoft.com/en-us/linkedin/)
- [OpenAI API](https://platform.openai.com/docs)

## 🎓 Learning Path

1. Start with YouTube-only setup
2. Add Twitter trends
3. Enable AI content generation
4. Set up social media APIs
5. Automate with GitHub Actions
6. Scale to multiple platforms

---

**Ready to start? Check QUICKSTART.md for setup instructions!**
