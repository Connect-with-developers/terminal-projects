""
YouTube Search Module
Searches YouTube for videos based on trending topics
"""

import os
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()


class YouTubeSearch:
    """Search YouTube videos and get metadata"""
    
    def __init__(self):
        """Initialize YouTube API client"""
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY not found in environment variables")
        
        self.youtube = build('youtube', 'v3', developerKey=self.api_key)
    
    def search_videos(self, 
                     query: str, 
                     max_results: int = 10,
                     language: str = 'en',
                     order: str = 'viewCount') -> List[Dict]:
        """
        Search for YouTube videos
        
        Args:
            query: Search query
            max_results: Number of results to return
            language: Video language (default: English)
            order: Sort order (viewCount, relevance, date, rating)
            
        Returns:
            List of video metadata
        """
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                relevanceLanguage=language,
                order=order,
                videoCaption='closedCaption',  # Only videos with captions
                videoDuration='medium'  # 4-20 minutes
            ).execute()
            
            video_ids = []
            for item in search_response.get('items', []):
                if item['id']['kind'] == 'youtube#video':
                    video_ids.append(item['id']['videoId'])
            
            if not video_ids:
                return []
            
            # Get detailed video information
            videos_response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            videos = []
            for item in videos_response.get('items', []):
                video_data = {
                    'video_id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail_url': item['snippet']['thumbnails']['high']['url'],
                    'view_count': int(item['statistics'].get('viewCount', 0)),
                    'like_count': int(item['statistics'].get('likeCount', 0)),
                    'comment_count': int(item['statistics'].get('commentCount', 0)),
                    'duration': item['contentDetails']['duration'],
                    'url': f"https://www.youtube.com/watch?v={item['id']}"
                }
                videos.append(video_data)
            
            return videos
            
        except HttpError as e:
            print(f"HTTP Error: {e}")
            return []
        except Exception as e:
            print(f"Error searching videos: {e}")
            return []
    
    def get_best_video(self, 
                       query: str,
                       min_views: int = 10000,
                       max_results: int = 20) -> Optional[Dict]:
        """
        Get the best video for a given query
        
        Args:
            query: Search query
            min_views: Minimum view count
            max_results: Number of videos to search through
            
        Returns:
            Best video metadata or None
        """
        videos = self.search_videos(query, max_results=max_results)
        
        # Filter by minimum views
        filtered_videos = [v for v in videos if v['view_count'] >= min_views]
        
        if not filtered_videos:
            return videos[0] if videos else None
        
        # Sort by engagement (views + likes)
        sorted_videos = sorted(
            filtered_videos,
            key=lambda x: x['view_count'] + (x['like_count'] * 10),
            reverse=True
        )
        
        return sorted_videos[0]
    
    def get_video_details(self, video_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Video metadata or None
        """
        try:
            response = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=video_id
            ).execute()
            
            if not response.get('items'):
                return None
            
            item = response['items'][0]
            
            return {
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'channel_title': item['snippet']['channelTitle'],
                'published_at': item['snippet']['publishedAt'],
                'thumbnail_url': item['snippet']['thumbnails']['high']['url'],
                'view_count': int(item['statistics'].get('viewCount', 0)),
                'like_count': int(item['statistics'].get('likeCount', 0)),
                'comment_count': int(item['statistics'].get('commentCount', 0)),
                'duration': item['contentDetails']['duration'],
                'url': f"https://www.youtube.com/watch?v={item['id']}"
            }
            
        except Exception as e:
            print(f"Error getting video details: {e}")
            return None
    
    def search_by_channel(self, channel_id: str, max_results: int = 10) -> List[Dict]:
        """
        Search videos from a specific channel
        
        Args:
            channel_id: YouTube channel ID
            max_results: Number of results to return
            
        Returns:
            List of video metadata
        """
        try:
            search_response = self.youtube.search().list(
                channelId=channel_id,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                order='date'
            ).execute()
            
            videos = []
            for item in search_response.get('items', []):
                if item['id']['kind'] == 'youtube#video':
                    video_data = {
                        'video_id': item['id']['videoId'],
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail_url': item['snippet']['thumbnails']['high']['url'],
                        'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    }
                    videos.append(video_data)
            
            return videos
            
        except Exception as e:
            print(f"Error searching by channel: {e}")
            return []


def main():
    """Test the YouTube search module"""
    print("🎥 YouTube Video Search\n")
    
    try:
        youtube = YouTubeSearch()
        
        # Test search
        query = "AI automation tutorial"
        print(f"Searching for: '{query}'\n")
        
        videos = youtube.search_videos(query, max_results=5)
        
        print(f"📹 Found {len(videos)} videos:\n")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']}")
            print(f"   Channel: {video['channel_title']}")
            print(f"   Views: {video['view_count']:,}")
            print(f"   Likes: {video['like_count']:,}")
            print(f"   URL: {video['url']}\n")
        
        # Get best video
        print("\n✨ Getting best video...")
        best_video = youtube.get_best_video(query)
        
        if best_video:
            print(f"\n🏆 Best Video:")
            print(f"   Title: {best_video['title']}")
            print(f"   Channel: {best_video['channel_title']}")
            print(f"   Views: {best_video['view_count']:,}")
            print(f"   Likes: {best_video['like_count']:,}")
            print(f"   URL: {best_video['url']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure you have set up your YouTube API key:")
        print("   - YOUTUBE_API_KEY")
        print("\n   Get it from: https://console.cloud.google.com/")


if __name__ == "__main__":
    main()
