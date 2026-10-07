# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Installation

```bash
cd social-media-automation
pip install -r requirements.txt
```

### 2. Get API Keys

#### YouTube API (Required)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create credentials (API Key)
5. Copy the API key

#### Twitter API (Optional but recommended)
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app
3. Get API keys and bearer token

#### OpenAI API (Optional - for better content)
1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create API key
3. Add credits to your account

### 3. Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
nano .env

# Copy example config
cp config/config.example.json config/config.json

# Edit config if needed
nano config/config.json
```

### 4. Test Run

```bash
# Run in dry-run mode (won't post)
python main.py --dry-run
```

### 5. Check Output

Generated files will be in:
- `output/carousels/` - Carousel images
- `automation_history.json` - Post history

## 📝 Minimal Setup (Just YouTube)

If you only have YouTube API key:

```bash
# Set only YouTube key in .env
YOUTUBE_API_KEY=your_key_here

# Run with manual topic
python main.py --dry-run
```

The system will use fallback topics if Twitter is not configured.

## 🎨 Customize Carousel Design

Edit `config/config.json`:

```json
{
  "color_scheme": "modern_blue",  // or: vibrant, minimal, dark, gradient_purple
  "carousel_slides": 5,
  "platforms": ["instagram", "linkedin", "facebook"]
}
```

## 🤖 Enable AI Content Generation

1. Get OpenAI API key
2. Add to `.env`:
   ```
   OPENAI_API_KEY=your_key
   ```
3. Set in `config/config.json`:
   ```json
   {
     "use_ai": true
   }
   ```

## 📱 Setup Social Media Posting

### Facebook/Instagram
1. Create Facebook Developer App
2. Get Page Access Token
3. For Instagram: Connect Instagram Business Account
4. Add tokens to `.env`

### LinkedIn
1. Create LinkedIn App
2. Get OAuth access token
3. Add to `.env`

## ⏰ Automate with GitHub Actions

1. Push to GitHub
2. Go to Settings → Secrets and variables → Actions
3. Add all secrets from `.env`
4. Enable Actions
5. Workflow runs automatically 3x daily!

## 🔧 Troubleshooting

### "No suitable video found"
- Try a different trending topic
- Lower `min_video_views` in config
- Make sure video has English captions

### "Failed to extract transcript"
- Not all videos have transcripts
- Try a different video
- Check if video is available in your region

### "Twitter API error"
- System will use fallback topics
- Not critical for testing

### "OpenAI error"
- System will use template-based generation
- Content will be simpler but still works

## 💡 Pro Tips

1. **Test First**: Always use `--dry-run` to test
2. **Start Simple**: Get it working with just YouTube API
3. **Add Features Gradually**: Add Twitter, AI, posting later
4. **Check History**: Review `automation_history.json` to avoid duplicates
5. **Monitor Usage**: Watch your API quotas

## 📊 Expected Output

After running:
```
✅ 7 carousel slides generated
✅ 3 platform-specific posts created
✅ Content saved in output/ folder
```

## 🎯 Next Steps

1. Review generated carousels
2. Customize color schemes
3. Enable AI for better content
4. Set up social media posting
5. Automate with GitHub Actions

## 🆘 Need Help?

- Check the main README.md
- Review error messages
- Test each component separately
- Start with minimal configuration

---

**Ready to automate? Run:**
```bash
python main.py --dry-run
```
