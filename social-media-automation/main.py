"""
Social Media Automation - Main Script
Fully automated content pipeline: Trend → YouTube → Transcript → Carousel → Post
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.twitter_trends import TwitterTrends
from scrapers.youtube_search import YouTubeSearch
from scrapers.transcript_extractor import TranscriptExtractor
from content_generator.carousel_creator import CarouselCreator
from content_generator.post_writer import PostWriter


class SocialMediaAutomation:
    """Main automation orchestrator"""
    
    def __init__(self, config_path: str = 'config/config.json'):
        """
        Initialize automation system
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.database_file = 'automation_history.json'
        self.history = self._load_history()
        
        # Initialize components
        print("🚀 Initializing Social Media Automation System...\n")
        
        try:
            self.twitter = TwitterTrends()
            print("✅ Twitter trends scraper ready")
        except Exception as e:
            print(f"⚠️ Twitter scraper not available: {e}")
            self.twitter = None
        
        try:
            self.youtube = YouTubeSearch()
            print("✅ YouTube search ready")
        except Exception as e:
            print(f"❌ YouTube search failed: {e}")
            self.youtube = None
        
        self.transcript = TranscriptExtractor()
        print("✅ Transcript extractor ready")
        
        self.carousel = CarouselCreator()
        print("✅ Carousel creator ready")
        
        self.writer = PostWriter(use_ai=self.config.get('use_ai', True))
        print("✅ Post writer ready")
        
        print("\n" + "="*50 + "\n")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration"""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {
            'use_ai': False,
            'platforms': ['instagram', 'linkedin', 'facebook'],
            'carousel_slides': 5,
            'color_scheme': 'modern_blue',
            'min_video_views': 10000,
            'exclude_topics': ['death', 'war', 'violence']
        }
    
    def _load_history(self) -> dict:
        """Load automation history"""
        if os.path.exists(self.database_file):
            with open(self.database_file, 'r') as f:
                return json.load(f)
        return {'processed_topics': [], 'posts': []}
    
    def _save_history(self):
        """Save automation history"""
        with open(self.database_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def _is_topic_processed(self, topic: str) -> bool:
        """Check if topic has been processed before"""
        return topic.lower() in [t.lower() for t in self.history.get('processed_topics', [])]
    
    def run(self, dry_run: bool = False):
        """
        Run the complete automation pipeline
        
        Args:
            dry_run: If True, generate content but don't post
        """
        print(f"🎬 Starting Automation Pipeline")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Step 1: Get trending topic
        print("📊 Step 1: Fetching trending topics...")
        topic = self._get_trending_topic()
        
        if not topic:
            print("❌ No suitable trending topic found")
            return False
        
        print(f"✅ Selected topic: {topic['name']}")
        print(f"   Volume: {topic.get('tweet_volume', 'N/A')}\n")
        
        # Step 2: Search YouTube
        print("🎥 Step 2: Searching YouTube videos...")
        video = self._find_best_video(topic['name'])
        
        if not video:
            print("❌ No suitable video found")
            return False
        
        print(f"✅ Found video: {video['title'][:60]}...")
        print(f"   Channel: {video['channel_title']}")
        print(f"   Views: {video['view_count']:,}")
        print(f"   URL: {video['url']}\n")
        
        # Step 3: Extract transcript
        print("📝 Step 3: Extracting video transcript...")
        transcript_text = self.transcript.get_transcript(video['video_id'])
        
        if not transcript_text:
            print("❌ Failed to extract transcript")
            return False
        
        stats = self.transcript.get_transcript_stats(transcript_text)
        print(f"✅ Transcript extracted")
        print(f"   Words: {stats['word_count']:,}")
        print(f"   Reading time: {stats['estimated_reading_time_minutes']:.1f} minutes\n")
        
        # Step 4: Extract key points
        print("🔑 Step 4: Extracting key points...")
        key_points = self.transcript.extract_key_points(transcript_text, num_points=5)
        
        print(f"✅ Extracted {len(key_points)} key points:")
        for i, point in enumerate(key_points, 1):
            print(f"   {i}. {point[:70]}...")
        print()
        
        # Step 5: Generate carousel
        print("🎨 Step 5: Creating carousel...")
        slides = self.writer.generate_carousel_content(
            video['title'],
            transcript_text,
            num_slides=self.config.get('carousel_slides', 5)
        )
        
        carousel_files = self.carousel.create_carousel(
            slides=slides,
            platform='instagram',
            color_scheme=self.config.get('color_scheme', 'modern_blue'),
            title=topic['name']
        )
        
        print(f"✅ Created {len(carousel_files)} carousel slides")
        for file in carousel_files:
            print(f"   📄 {file}")
        print()
        
        # Step 6: Generate posts for each platform
        print("✍️ Step 6: Generating social media posts...")
        
        posts = {}
        for platform in self.config.get('platforms', ['instagram']):
            print(f"   Generating {platform} post...")
            post = self.writer.generate_post(
                video_title=video['title'],
                transcript=transcript_text,
                key_points=key_points,
                platform=platform,
                tone='engaging'
            )
            posts[platform] = post
        
        print(f"✅ Generated posts for {len(posts)} platforms\n")
        
        # Display posts
        for platform, post in posts.items():
            print(f"📱 {platform.upper()} POST:")
            print(post['caption'][:200] + "..." if len(post['caption']) > 200 else post['caption'])
            print(f"\n{post['hashtags']}\n")
            print("-" * 50 + "\n")
        
        # Step 7: Post to platforms (if not dry run)
        if not dry_run:
            print("📤 Step 7: Publishing to platforms...")
            print("⚠️ Publishing is not yet implemented")
            print("   Manual posting required for now\n")
        else:
            print("✅ Dry run complete - content ready for review\n")
        
        # Save to history
        self.history['processed_topics'].append(topic['name'])
        self.history['posts'].append({
            'topic': topic['name'],
            'video_id': video['video_id'],
            'video_title': video['title'],
            'timestamp': datetime.now().isoformat(),
            'carousel_files': carousel_files,
            'posts': posts
        })
        self._save_history()
        
        print("="*50)
        print("✨ AUTOMATION COMPLETE!")
        print("="*50)
        
        return True
    
    def _get_trending_topic(self):
        """Get a trending topic that hasn't been processed"""
        if not self.twitter:
            # Fallback topics if Twitter not available
            fallback_topics = [
                {'name': 'AI Automation', 'tweet_volume': 50000},
                {'name': 'Productivity Tips', 'tweet_volume': 30000},
                {'name': 'Digital Marketing', 'tweet_volume': 40000},
            ]
            
            for topic in fallback_topics:
                if not self._is_topic_processed(topic['name']):
                    return topic
            
            return fallback_topics[0]
        
        # Get trends from Twitter
        trends = self.twitter.get_trending_topics(limit=20)
        
        # Filter out processed topics and excluded keywords
        exclude_keywords = self.config.get('exclude_topics', [])
        
        for trend in trends:
            if self._is_topic_processed(trend['name']):
                continue
            
            trend_lower = trend['name'].lower()
            if any(keyword in trend_lower for keyword in exclude_keywords):
                continue
            
            return trend
        
        return trends[0] if trends else None
    
    def _find_best_video(self, topic: str):
        """Find the best video for a topic"""
        if not self.youtube:
            print("❌ YouTube search not available")
            return None
        
        video = self.youtube.get_best_video(
            query=topic,
            min_views=self.config.get('min_video_views', 10000),
            max_results=20
        )
        
        return video


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Social Media Automation')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Run without posting (for testing)')
    parser.add_argument('--config', default='config/config.json',
                       help='Path to config file')
    
    args = parser.parse_args()
    
    try:
        automation = SocialMediaAutomation(config_path=args.config)
        automation.run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️ Automation interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
