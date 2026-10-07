"""
Carousel Creator
Generates beautiful carousel images for social media
"""

import os
from typing import List, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont
import textwrap


class CarouselCreator:
    """Create carousel images for social media posts"""
    
    # Standard sizes for different platforms
    SIZES = {
        'instagram': (1080, 1080),  # Square
        'linkedin': (1200, 627),    # Landscape
        'facebook': (1200, 630),    # Landscape
        'square': (1080, 1080),
        'landscape': (1200, 675)
    }
    
    # Color schemes
    COLOR_SCHEMES = {
        'modern_blue': {
            'background': '#1a1a2e',
            'primary': '#0f3460',
            'accent': '#16213e',
            'text': '#ffffff',
            'highlight': '#00adb5'
        },
        'vibrant': {
            'background': '#6a0572',
            'primary': '#ab83a1',
            'accent': '#f9ed69',
            'text': '#ffffff',
            'highlight': '#f08a5d'
        },
        'minimal': {
            'background': '#ffffff',
            'primary': '#2d3436',
            'accent': '#dfe6e9',
            'text': '#2d3436',
            'highlight': '#0984e3'
        },
        'dark': {
            'background': '#0a0a0a',
            'primary': '#1a1a1a',
            'accent': '#2a2a2a',
            'text': '#ffffff',
            'highlight': '#ff6b6b'
        },
        'gradient_purple': {
            'background': '#667eea',
            'primary': '#764ba2',
            'accent': '#f093fb',
            'text': '#ffffff',
            'highlight': '#feca57'
        }
    }
    
    def __init__(self, output_dir: str = 'output/carousels'):
        """
        Initialize carousel creator
        
        Args:
            output_dir: Directory to save carousel images
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def create_carousel(self,
                       slides: List[Dict[str, str]],
                       platform: str = 'instagram',
                       color_scheme: str = 'modern_blue',
                       title: str = None) -> List[str]:
        """
        Create a full carousel
        
        Args:
            slides: List of slide data [{'title': '', 'content': ''}]
            platform: Target platform (instagram, linkedin, facebook)
            color_scheme: Color scheme name
            title: Optional carousel title
            
        Returns:
            List of file paths to generated images
        """
        size = self.SIZES.get(platform, self.SIZES['square'])
        colors = self.COLOR_SCHEMES.get(color_scheme, self.COLOR_SCHEMES['modern_blue'])
        
        file_paths = []
        
        # Create title slide if provided
        if title:
            title_slide = self.create_title_slide(title, size, colors)
            path = os.path.join(self.output_dir, f'slide_00_title.png')
            title_slide.save(path, quality=95)
            file_paths.append(path)
        
        # Create content slides
        for i, slide in enumerate(slides, 1):
            img = self.create_content_slide(
                slide.get('title', ''),
                slide.get('content', ''),
                size,
                colors,
                slide_number=i,
                total_slides=len(slides)
            )
            path = os.path.join(self.output_dir, f'slide_{i:02d}.png')
            img.save(path, quality=95)
            file_paths.append(path)
        
        # Create CTA slide
        cta_slide = self.create_cta_slide(size, colors)
        path = os.path.join(self.output_dir, f'slide_{len(slides)+1:02d}_cta.png')
        cta_slide.save(path, quality=95)
        file_paths.append(path)
        
        return file_paths
    
    def create_title_slide(self, 
                          title: str, 
                          size: Tuple[int, int],
                          colors: Dict[str, str]) -> Image.Image:
        """Create the title/intro slide"""
        img = Image.new('RGB', size, color=colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Try to load font, fall back to default
        try:
            title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 80)
        except:
            title_font = ImageFont.load_default()
        
        # Draw title with text wrapping
        max_width = int(size[0] * 0.8)
        wrapped_title = self._wrap_text(title, title_font, max_width, draw)
        
        # Calculate text position (centered)
        bbox = draw.textbbox((0, 0), wrapped_title, font=title_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2
        
        # Draw accent rectangle behind text
        padding = 40
        draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=colors['primary']
        )
        
        # Draw title text
        draw.text((x, y), wrapped_title, fill=colors['text'], font=title_font)
        
        return img
    
    def create_content_slide(self,
                           title: str,
                           content: str,
                           size: Tuple[int, int],
                           colors: Dict[str, str],
                           slide_number: int = 1,
                           total_slides: int = 1) -> Image.Image:
        """Create a content slide"""
        img = Image.new('RGB', size, color=colors['background'])
        draw = ImageDraw.Draw(img)
        
        # Load fonts
        try:
            title_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 60)
            content_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40)
            small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 30)
        except:
            title_font = ImageFont.load_default()
            content_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        margin = 60
        current_y = margin
        
        # Draw slide number
        slide_text = f"{slide_number}/{total_slides}"
        draw.text((size[0] - margin - 100, margin), slide_text, 
                 fill=colors['highlight'], font=small_font)
        
        # Draw title
        if title:
            max_width = size[0] - (2 * margin)
            wrapped_title = self._wrap_text(title, title_font, max_width, draw)
            
            # Highlight bar
            draw.rectangle(
                [margin - 20, current_y, margin, current_y + 60],
                fill=colors['highlight']
            )
            
            draw.text((margin + 20, current_y), wrapped_title, 
                     fill=colors['text'], font=title_font)
            
            bbox = draw.textbbox((margin + 20, current_y), wrapped_title, font=title_font)
            current_y = bbox[3] + 40
        
        # Draw content
        if content:
            max_width = size[0] - (2 * margin)
            wrapped_content = self._wrap_text(content, content_font, max_width, draw)
            
            # Background box
            content_bbox = draw.textbbox((margin, current_y), wrapped_content, font=content_font)
            padding = 30
            draw.rectangle(
                [margin - padding, current_y - padding,
                 size[0] - margin + padding, content_bbox[3] + padding],
                fill=colors['primary'],
                outline=colors['accent'],
                width=3
            )
            
            draw.text((margin, current_y), wrapped_content, 
                     fill=colors['text'], font=content_font)
        
        return img
    
    def create_cta_slide(self,
                        size: Tuple[int, int],
                        colors: Dict[str, str]) -> Image.Image:
        """Create a call-to-action slide"""
        img = Image.new('RGB', size, color=colors['background'])
        draw = ImageDraw.Draw(img)
        
        try:
            big_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 70)
            small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40)
        except:
            big_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Main CTA text
        cta_text = "Thanks for\nReading!"
        
        # Calculate centered position
        bbox = draw.textbbox((0, 0), cta_text, font=big_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2 - 100
        
        draw.text((x, y), cta_text, fill=colors['text'], font=big_font, align='center')
        
        # Sub text
        sub_text = "Follow for more content!"
        bbox2 = draw.textbbox((0, 0), sub_text, font=small_font)
        sub_width = bbox2[2] - bbox2[0]
        
        sub_x = (size[0] - sub_width) // 2
        sub_y = y + text_height + 50
        
        # Highlight box for sub text
        padding = 20
        draw.rectangle(
            [sub_x - padding, sub_y - padding,
             sub_x + sub_width + padding, sub_y + 60],
            fill=colors['highlight']
        )
        
        draw.text((sub_x, sub_y), sub_text, fill=colors['background'], font=small_font)
        
        return img
    
    def _wrap_text(self, text: str, font, max_width: int, draw) -> str:
        """Wrap text to fit within max_width"""
        lines = []
        words = text.split()
        
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)


def main():
    """Test the carousel creator"""
    print("🎨 Carousel Creator Test\n")
    
    creator = CarouselCreator()
    
    # Sample slides
    slides = [
        {
            'title': 'Introduction',
            'content': 'This is an automated carousel created from video transcripts. Learn how to automate your content!'
        },
        {
            'title': 'Key Point 1',
            'content': 'First important insight from the video that viewers should know about.'
        },
        {
            'title': 'Key Point 2',
            'content': 'Second major takeaway that adds value to your audience.'
        },
        {
            'title': 'Key Point 3',
            'content': 'Third essential lesson from the video content.'
        },
        {
            'title': 'Conclusion',
            'content': 'Summary of the main points and actionable steps you can take.'
        }
    ]
    
    print("Creating carousel with 5 slides...\n")
    
    file_paths = creator.create_carousel(
        slides=slides,
        platform='instagram',
        color_scheme='modern_blue',
        title='AI Automation\nTutorial'
    )
    
    print(f"✅ Created {len(file_paths)} slides:\n")
    for path in file_paths:
        print(f"   📄 {path}")
    
    print("\n✨ Carousel ready for posting!")


if __name__ == "__main__":
    main()
