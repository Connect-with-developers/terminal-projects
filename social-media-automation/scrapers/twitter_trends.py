"""
Twitter Trends Scraper
Gets trending topics from X (Twitter) to use as content inspiration
"""

import os
import tweepy
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class TwitterTrends:
    """Scrape trending topics from Twitter/X"""
    
    def __init__(self):
        """Initialize Twitter API client"""
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
        if not all([self.api_key, self.api_secret, self.bearer_token]):
            raise ValueError("Twitter API credentials not found in environment variables")
        
        # Initialize Tweepy client
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            wait_on_rate_limit=True
        )
    
    def get_trending_topics(self, location: str = "worldwide", limit: int = 10) -> List[Dict]:
        """
        Get trending topics from Twitter
        
        Args:
            location: Location for trends (worldwide, US, UK, etc.)
            limit: Number of trends to return
            
        Returns:
            List of trending topics with metadata
        """
        try:
            # WOEID (Where On Earth ID) mapping
            woeid_map = {
                "worldwide": 1,
                "us": 23424977,
                "uk": 23424975,
                "india": 23424848,
                "canada": 23424775,
                "australia": 23424748
            }
            
            woeid = woeid_map.get(location.lower(), 1)
            
            # Note: Twitter API v2 doesn't support trends endpoint yet
            # Using v1.1 API through tweepy
            auth = tweepy.OAuth1UserHandler(
                self.api_key,
                self.api_secret
            )
            api = tweepy.API(auth)
            
            trends = api.get_place_trends(id=woeid)
            
            trending_list = []
            for trend in trends[0]['trends'][:limit]:
                trending_list.append({
                    'name': trend['name'],
                    'url': trend['url'],
                    'tweet_volume': trend.get('tweet_volume', 0),
                    'query': trend.get('query', trend['name'])
                })
            
            return trending_list
            
        except Exception as e:
            print(f"Error fetching trends: {e}")
            return []
    
    def search_trending_tweets(self, topic: str, limit: int = 10) -> List[Dict]:
        """
        Search tweets related to a trending topic
        
        Args:
            topic: Trending topic to search for
            limit: Number of tweets to return
            
        Returns:
            List of tweets with metadata
        """
        try:
            # Search recent tweets
            tweets = self.client.search_recent_tweets(
                query=f"{topic} -is:retweet lang:en",
                max_results=limit,
                tweet_fields=['created_at', 'public_metrics', 'author_id']
            )
            
            if not tweets.data:
                return []
            
            tweet_list = []
            for tweet in tweets.data:
                metrics = tweet.public_metrics
                tweet_list.append({
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': tweet.created_at,
                    'likes': metrics['like_count'],
                    'retweets': metrics['retweet_count'],
                    'replies': metrics['reply_count']
                })
            
            return tweet_list
            
        except Exception as e:
            print(f"Error searching tweets: {e}")
            return []
    
    def get_best_trend_for_content(self, 
                                   min_volume: int = 10000,
                                   exclude_keywords: List[str] = None) -> Dict:
        """
        Get the best trending topic for content creation
        
        Args:
            min_volume: Minimum tweet volume required
            exclude_keywords: Keywords to exclude (e.g., sensitive topics)
            
        Returns:
            Best trending topic with metadata
        """
        if exclude_keywords is None:
            exclude_keywords = ['death', 'war', 'violence', 'breaking']
        
        trends = self.get_trending_topics(limit=20)
        
        for trend in trends:
            # Skip if volume too low
            if trend['tweet_volume'] and trend['tweet_volume'] < min_volume:
                continue
            
            # Skip if contains excluded keywords
            trend_lower = trend['name'].lower()
            if any(keyword in trend_lower for keyword in exclude_keywords):
                continue
            
            return trend
        
        # Return first trend if none match criteria
        return trends[0] if trends else None


def main():
    """Test the Twitter trends scraper"""
    print("🔥 Twitter Trends Scraper\n")
    
    try:
        scraper = TwitterTrends()
        
        # Get trending topics
        print("Fetching trending topics...")
        trends = scraper.get_trending_topics(limit=10)
        
        print("\n📈 Top 10 Trending Topics:\n")
        for i, trend in enumerate(trends, 1):
            volume = trend['tweet_volume'] or 'N/A'
            print(f"{i}. {trend['name']}")
            print(f"   Volume: {volume}")
            print(f"   URL: {trend['url']}\n")
        
        # Get best trend for content
        best_trend = scraper.get_best_trend_for_content()
        if best_trend:
            print(f"\n✨ Best Trend for Content: {best_trend['name']}")
            print(f"   Volume: {best_trend['tweet_volume']}")
            
            # Search tweets for this trend
            print(f"\n🔍 Recent tweets about '{best_trend['name']}':\n")
            tweets = scraper.search_trending_tweets(best_trend['name'], limit=5)
            
            for i, tweet in enumerate(tweets, 1):
                print(f"{i}. {tweet['text'][:100]}...")
                print(f"   ❤️ {tweet['likes']} | 🔁 {tweet['retweets']}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure you have set up your Twitter API credentials:")
        print("   - TWITTER_API_KEY")
        print("   - TWITTER_API_SECRET")
        print("   - TWITTER_BEARER_TOKEN")


if __name__ == "__main__":
    main()
