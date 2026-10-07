"""
Test Script - Test individual components
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_transcript_extractor():
    """Test transcript extraction"""
    print("🧪 Testing Transcript Extractor...\n")
    
    from scrapers.transcript_extractor import TranscriptExtractor
    
    extractor = TranscriptExtractor()
    
    # Test with a known video (replace with actual video ID)
    video_id = "dQw4w9WgXcQ"
    
    print(f"Extracting transcript for video: {video_id}")
    transcript = extractor.get_transcript(video_id)
    
    if transcript:
        print("✅ Transcript extracted successfully!")
        print(f"   Length: {len(transcript)} characters")
        print(f"   Preview: {transcript[:200]}...")
    else:
        print("❌ Failed to extract transcript")
        print("   Try a different video ID with English captions")
    
    print()


def test_carousel_creator():
    """Test carousel creation"""
    print("🧪 Testing Carousel Creator...\n")
    
    from content_generator.carousel_creator import CarouselCreator
    
    creator = CarouselCreator(output_dir='output/test_carousels')
    
    slides = [
        {'title': 'Test Slide 1', 'content': 'This is a test carousel slide.'},
        {'title': 'Test Slide 2', 'content': 'Testing the carousel creator functionality.'},
        {'title': 'Test Slide 3', 'content': 'Final test slide to verify everything works.'}
    ]
    
    print("Creating test carousel...")
    files = creator.create_carousel(
        slides=slides,
        platform='instagram',
        color_scheme='modern_blue',
        title='Test Carousel'
    )
    
    print(f"✅ Created {len(files)} slides:")
    for file in files:
        print(f"   📄 {file}")
    
    print()


def test_post_writer():
    """Test post generation"""
    print("🧪 Testing Post Writer...\n")
    
    from content_generator.post_writer import PostWriter
    
    writer = PostWriter(use_ai=False)
    
    video_title = "Test Video: How to Automate Everything"
    transcript = "This is a test transcript with sample content about automation."
    key_points = [
        "Automation saves time",
        "Use the right tools",
        "Test before deploying"
    ]
    
    print("Generating Instagram post...")
    post = writer.generate_post(
        video_title=video_title,
        transcript=transcript,
        key_points=key_points,
        platform='instagram'
    )
    
    print("✅ Post generated:")
    print(f"\n{post['caption']}\n")
    print(f"{post['hashtags']}\n")
    print(f"{post['cta']}\n")


def test_youtube_search():
    """Test YouTube search (requires API key)"""
    print("🧪 Testing YouTube Search...\n")
    
    try:
        from scrapers.youtube_search import YouTubeSearch
        
        youtube = YouTubeSearch()
        
        print("Searching for 'python tutorial'...")
        videos = youtube.search_videos('python tutorial', max_results=3)
        
        print(f"✅ Found {len(videos)} videos:")
        for i, video in enumerate(videos, 1):
            print(f"\n{i}. {video['title'][:60]}...")
            print(f"   Views: {video['view_count']:,}")
            print(f"   URL: {video['url']}")
        
    except Exception as e:
        print(f"⚠️ YouTube search test failed: {e}")
        print("   Make sure YOUTUBE_API_KEY is set in .env")
    
    print()


def main():
    """Run all tests"""
    print("="*60)
    print("  SOCIAL MEDIA AUTOMATION - COMPONENT TESTS")
    print("="*60)
    print()
    
    tests = [
        ('Carousel Creator', test_carousel_creator),
        ('Post Writer', test_post_writer),
        ('Transcript Extractor', test_transcript_extractor),
        ('YouTube Search', test_youtube_search),
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} test failed: {e}\n")
        
        print("-"*60)
        print()
    
    print("="*60)
    print("  TESTS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
