"""
YouTube Transcript Extractor
Extracts and processes video transcripts
"""

import re
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)


class TranscriptExtractor:
    """Extract and process YouTube video transcripts"""
    
    def __init__(self):
        """Initialize transcript extractor"""
        pass
    
    def get_transcript(self, 
                      video_id: str, 
                      languages: List[str] = ['en', 'en-US', 'en-GB']) -> Optional[str]:
        """
        Get transcript for a YouTube video
        
        Args:
            video_id: YouTube video ID
            languages: Preferred languages (default: English variants)
            
        Returns:
            Full transcript text or None
        """
        try:
            # Try to get transcript
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to find manual transcript first (more accurate)
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except:
                # Fall back to auto-generated
                transcript = transcript_list.find_generated_transcript(languages)
            
            # Get the actual transcript data
            transcript_data = transcript.fetch()
            
            # Combine all text
            full_text = ' '.join([entry['text'] for entry in transcript_data])
            
            # Clean up the text
            full_text = self.clean_transcript(full_text)
            
            return full_text
            
        except TranscriptsDisabled:
            print(f"Transcripts are disabled for video: {video_id}")
            return None
        except NoTranscriptFound:
            print(f"No English transcript found for video: {video_id}")
            return None
        except VideoUnavailable:
            print(f"Video unavailable: {video_id}")
            return None
        except Exception as e:
            print(f"Error getting transcript: {e}")
            return None
    
    def get_transcript_with_timestamps(self, 
                                      video_id: str,
                                      languages: List[str] = ['en']) -> Optional[List[Dict]]:
        """
        Get transcript with timestamps
        
        Args:
            video_id: YouTube video ID
            languages: Preferred languages
            
        Returns:
            List of transcript entries with timestamps
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            try:
                transcript = transcript_list.find_manually_created_transcript(languages)
            except:
                transcript = transcript_list.find_generated_transcript(languages)
            
            transcript_data = transcript.fetch()
            
            # Clean text in each entry
            for entry in transcript_data:
                entry['text'] = self.clean_transcript(entry['text'])
            
            return transcript_data
            
        except Exception as e:
            print(f"Error getting transcript with timestamps: {e}")
            return None
    
    def clean_transcript(self, text: str) -> str:
        """
        Clean up transcript text
        
        Args:
            text: Raw transcript text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove [Music], [Applause], etc.
        text = re.sub(r'\[.*?\]', '', text)
        
        # Remove duplicate punctuation
        text = re.sub(r'([.!?])\1+', r'\1', text)
        
        # Fix spacing around punctuation
        text = re.sub(r'\s+([.!?,;:])', r'\1', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def summarize_transcript(self, text: str, max_words: int = 200) -> str:
        """
        Create a simple summary of the transcript
        
        Args:
            text: Full transcript text
            max_words: Maximum words in summary
            
        Returns:
            Summarized text
        """
        words = text.split()
        
        if len(words) <= max_words:
            return text
        
        # Take first and last portions
        first_part = ' '.join(words[:max_words // 2])
        last_part = ' '.join(words[-(max_words // 2):])
        
        return f"{first_part} ... {last_part}"
    
    def extract_key_points(self, text: str, num_points: int = 5) -> List[str]:
        """
        Extract key points from transcript (simple sentence-based)
        
        Args:
            text: Full transcript text
            num_points: Number of key points to extract
            
        Returns:
            List of key points
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        if not sentences:
            return []
        
        # Simple approach: take evenly distributed sentences
        step = len(sentences) // num_points if len(sentences) > num_points else 1
        key_points = []
        
        for i in range(0, len(sentences), step):
            if len(key_points) >= num_points:
                break
            key_points.append(sentences[i])
        
        return key_points[:num_points]
    
    def get_transcript_stats(self, text: str) -> Dict:
        """
        Get statistics about the transcript
        
        Args:
            text: Transcript text
            
        Returns:
            Dictionary with stats
        """
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]
        
        return {
            'word_count': len(words),
            'character_count': len(text),
            'sentence_count': len(sentences),
            'avg_words_per_sentence': len(words) / len(sentences) if sentences else 0,
            'estimated_reading_time_minutes': len(words) / 200  # Average reading speed
        }


def main():
    """Test the transcript extractor"""
    print("📝 YouTube Transcript Extractor\n")
    
    # Test with a known video ID (example: a popular tech video)
    video_id = "dQw4w9WgXcQ"  # Replace with actual video ID
    
    print(f"Extracting transcript for video: {video_id}\n")
    
    extractor = TranscriptExtractor()
    
    # Get transcript
    transcript = extractor.get_transcript(video_id)
    
    if transcript:
        print("✅ Transcript extracted successfully!\n")
        
        # Show stats
        stats = extractor.get_transcript_stats(transcript)
        print("📊 Transcript Stats:")
        print(f"   Words: {stats['word_count']:,}")
        print(f"   Sentences: {stats['sentence_count']}")
        print(f"   Characters: {stats['character_count']:,}")
        print(f"   Estimated reading time: {stats['estimated_reading_time_minutes']:.1f} minutes\n")
        
        # Show first 500 characters
        print("📄 Preview (first 500 characters):")
        print(f"   {transcript[:500]}...\n")
        
        # Extract key points
        key_points = extractor.extract_key_points(transcript, num_points=5)
        print("🔑 Key Points:")
        for i, point in enumerate(key_points, 1):
            print(f"   {i}. {point}\n")
        
        # Get summary
        summary = extractor.summarize_transcript(transcript, max_words=100)
        print("📋 Summary:")
        print(f"   {summary}")
        
    else:
        print("❌ Failed to extract transcript")
        print("\n💡 Tips:")
        print("   - Make sure the video has English captions")
        print("   - Try a different video ID")
        print("   - Check if the video is available")


if __name__ == "__main__":
    main()
