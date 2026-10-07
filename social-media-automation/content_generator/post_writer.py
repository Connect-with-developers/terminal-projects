"""
Post Writer
Generates engaging captions and posts for social media
"""

import os
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class PostWriter:
    """Generate social media posts and captions"""
    
    def __init__(self, use_ai: bool = True):
        """
        Initialize post writer
        
        Args:
            use_ai: Whether to use AI for content generation
        """
        self.use_ai = use_ai
        
        if use_ai:
            self.openai_key = os.getenv('OPENAI_API_KEY')
            if self.openai_key:
                try:
                    import openai
                    self.openai = openai
                    self.openai.api_key = self.openai_key
                    self.client = openai.OpenAI(api_key=self.openai_key)
                except ImportError:
                    print("OpenAI library not found. Install with: pip install openai")
                    self.use_ai = False
            else:
                self.use_ai = False
    
    def generate_post(self,
                     video_title: str,
                     transcript: str,
                     key_points: List[str],
                     platform: str = 'instagram',
                     tone: str = 'engaging') -> Dict[str, str]:
        """
        Generate a complete social media post
        
        Args:
            video_title: Title of the YouTube video
            transcript: Video transcript
            key_points: List of key points from video
            platform: Target platform (instagram, linkedin, facebook)
            tone: Tone of the post (engaging, professional, casual)
            
        Returns:
            Dictionary with caption, hashtags, and CTA
        """
        if self.use_ai:
            return self._generate_with_ai(video_title, transcript, key_points, platform, tone)
        else:
            return self._generate_template_based(video_title, key_points, platform)
    
    def _generate_with_ai(self,
                         video_title: str,
                         transcript: str,
                         key_points: List[str],
                         platform: str,
                         tone: str) -> Dict[str, str]:
        """Generate post using AI"""
        
        # Truncate transcript if too long
        max_transcript_length = 2000
        if len(transcript) > max_transcript_length:
            transcript = transcript[:max_transcript_length] + "..."
        
        platform_specs = {
            'instagram': {
                'max_length': 2200,
                'hashtag_count': '10-15',
                'style': 'casual and visual'
            },
            'linkedin': {
                'max_length': 3000,
                'hashtag_count': '3-5',
                'style': 'professional and insightful'
            },
            'facebook': {
                'max_length': 63206,
                'hashtag_count': '2-5',
                'style': 'conversational and engaging'
            }
        }
        
        spec = platform_specs.get(platform, platform_specs['instagram'])
        
        prompt = f"""Create an engaging {platform} post based on this YouTube video.

Video Title: {video_title}

Key Points:
{chr(10).join([f"- {point}" for point in key_points])}

Transcript Preview:
{transcript}

Requirements:
- Platform: {platform}
- Tone: {tone} and {spec['style']}
- Maximum length: {spec['max_length']} characters
- Include {spec['hashtag_count']} relevant hashtags
- Add emojis appropriately
- Include a strong hook in the first line
- End with a call-to-action

Format your response as:
CAPTION:
[your caption here]

HASHTAGS:
[hashtags separated by spaces]

CTA:
[call to action]
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a social media expert who creates engaging, viral-worthy content."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            # Parse response
            caption_match = re.search(r'CAPTION:\s*(.+?)(?=HASHTAGS:|CTA:|$)', content, re.DOTALL)
            hashtags_match = re.search(r'HASHTAGS:\s*(.+?)(?=CTA:|$)', content, re.DOTALL)
            cta_match = re.search(r'CTA:\s*(.+?)$', content, re.DOTALL)
            
            return {
                'caption': caption_match.group(1).strip() if caption_match else '',
                'hashtags': hashtags_match.group(1).strip() if hashtags_match else '',
                'cta': cta_match.group(1).strip() if cta_match else 'Follow for more!',
                'platform': platform
            }
            
        except Exception as e:
            print(f"Error generating with AI: {e}")
            return self._generate_template_based(video_title, key_points, platform)
    
    def _generate_template_based(self,
                                video_title: str,
                                key_points: List[str],
                                platform: str) -> Dict[str, str]:
        """Generate post using templates (fallback)"""
        
        # Create caption from template
        caption = f"🎥 {video_title}\n\n"
        caption += "Key Takeaways:\n"
        
        for i, point in enumerate(key_points[:5], 1):
            emoji = ['💡', '✨', '🚀', '🔥', '⚡'][i-1]
            caption += f"{emoji} {point}\n\n"
        
        caption += "Which point resonated with you the most? 💭"
        
        # Platform-specific hashtags
        hashtags_map = {
            'instagram': '#socialmedia #contentcreation #digitalmarketing #marketingtips #socialmediatips #contentmarketing #socialmediamarketing #marketingstrategy #growyourbusiness #entrepreneur',
            'linkedin': '#professionaldev #careergrowth #business #leadership #innovation',
            'facebook': '#learn #education #tutorial #tips #howto'
        }
        
        hashtags = hashtags_map.get(platform, hashtags_map['instagram'])
        
        cta = "Follow for more insights! 🚀"
        
        return {
            'caption': caption,
            'hashtags': hashtags,
            'cta': cta,
            'platform': platform
        }
    
    def generate_carousel_content(self,
                                 video_title: str,
                                 transcript: str,
                                 num_slides: int = 5) -> List[Dict[str, str]]:
        """
        Generate content for carousel slides
        
        Args:
            video_title: Video title
            transcript: Video transcript
            num_slides: Number of slides to generate
            
        Returns:
            List of slide content dictionaries
        """
        if self.use_ai:
            return self._generate_carousel_with_ai(video_title, transcript, num_slides)
        else:
            return self._generate_carousel_template(video_title, transcript, num_slides)
    
    def _generate_carousel_with_ai(self,
                                   video_title: str,
                                   transcript: str,
                                   num_slides: int) -> List[Dict[str, str]]:
        """Generate carousel content with AI"""
        
        max_transcript = 2000
        if len(transcript) > max_transcript:
            transcript = transcript[:max_transcript] + "..."
        
        prompt = f"""Create {num_slides} carousel slides based on this video.

Video Title: {video_title}
Transcript: {transcript}

Create {num_slides} slides with:
- Slide 1: Intro/Hook
- Slides 2-{num_slides-1}: Key points
- Slide {num_slides}: Conclusion/Summary

For each slide provide:
- A short title (max 50 characters)
- Content (max 150 characters)

Format as:
SLIDE 1:
Title: [title]
Content: [content]

SLIDE 2:
Title: [title]
Content: [content]

Continue for all {num_slides} slides.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a content creator who makes engaging carousel posts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # Parse slides
            slides = []
            slide_pattern = r'SLIDE \d+:.*?Title: (.+?)[\n\r]+Content: (.+?)(?=SLIDE \d+:|$)'
            matches = re.findall(slide_pattern, content, re.DOTALL)
            
            for title, content_text in matches:
                slides.append({
                    'title': title.strip(),
                    'content': content_text.strip()
                })
            
            return slides[:num_slides]
            
        except Exception as e:
            print(f"Error generating carousel with AI: {e}")
            return self._generate_carousel_template(video_title, transcript, num_slides)
    
    def _generate_carousel_template(self,
                                   video_title: str,
                                   transcript: str,
                                   num_slides: int) -> List[Dict[str, str]]:
        """Generate carousel content using templates"""
        
        slides = []
        
        # Intro slide
        slides.append({
            'title': 'Introduction',
            'content': f'Key insights from: {video_title[:80]}'
        })
        
        # Extract sentences from transcript
        sentences = [s.strip() for s in transcript.split('.') if len(s.strip()) > 30]
        
        # Content slides
        step = len(sentences) // (num_slides - 2) if len(sentences) > (num_slides - 2) else 1
        
        for i in range(1, num_slides - 1):
            idx = i * step
            if idx < len(sentences):
                slides.append({
                    'title': f'Point {i}',
                    'content': sentences[idx][:150]
                })
        
        # Conclusion slide
        slides.append({
            'title': 'Takeaway',
            'content': 'These insights can help you improve your skills!'
        })
        
        return slides[:num_slides]


def main():
    """Test the post writer"""
    print("📝 Post Writer Test\n")
    
    writer = PostWriter(use_ai=False)  # Set to True if you have OpenAI API key
    
    # Sample data
    video_title = "How to Automate Your Social Media in 2024"
    transcript = """
    In this video, we'll explore how to automate your social media presence.
    First, identify the best tools for automation. Then, create a content calendar.
    Finally, use AI to generate engaging posts. Automation saves time and increases consistency.
    """
    key_points = [
        "Use automation tools to save time",
        "Create a content calendar for consistency",
        "Leverage AI for content generation",
        "Focus on engagement metrics",
        "Test and optimize your strategy"
    ]
    
    # Generate Instagram post
    print("Generating Instagram post...\n")
    post = writer.generate_post(
        video_title=video_title,
        transcript=transcript,
        key_points=key_points,
        platform='instagram',
        tone='engaging'
    )
    
    print("📱 Instagram Post:\n")
    print(post['caption'])
    print(f"\n{post['hashtags']}")
    print(f"\n{post['cta']}\n")
    
    # Generate carousel content
    print("Generating carousel content...\n")
    slides = writer.generate_carousel_content(video_title, transcript, num_slides=5)
    
    print(f"🎨 Generated {len(slides)} carousel slides:\n")
    for i, slide in enumerate(slides, 1):
        print(f"Slide {i}: {slide['title']}")
        print(f"   {slide['content']}\n")


if __name__ == "__main__":
    main()
