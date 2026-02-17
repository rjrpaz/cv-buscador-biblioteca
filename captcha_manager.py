import random
import string
import time
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import base64

class CaptchaManager:
    def __init__(self):
        self.captchas = {}  # Store captcha data: {session_id: {'code': str, 'expires': datetime, 'attempts': int}}
        self.max_attempts = 3
        self.timeout_minutes = 15

    def generate_captcha(self, session_id):
        """Generate a new captcha for the given session"""
        # Clean expired captchas
        self.clean_expired()

        # Generate random code
        code = ''.join(random.choices(string.digits, k=4))

        # Create image manually
        img = self._create_captcha_image(code)

        # Convert to base64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

        # Store captcha data
        expires = datetime.now() + timedelta(minutes=self.timeout_minutes)
        self.captchas[session_id] = {
            'code': code,
            'expires': expires,
            'attempts': 0,
            'verified': False
        }

        return {
            'image': f"data:image/png;base64,{img_base64}",
            'expires_at': expires.isoformat()
        }

    def _create_captcha_image(self, code):
        """Create a simple captcha image"""
        width, height = 160, 60

        # Create image with white background
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Add some background noise
        for _ in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(200, 200, 200))

        # Draw the code
        try:
            # Try to use a default font
            font_size = 32
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Calculate text position
        bbox = draw.textbbox((0, 0), code, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Draw text with slight variations
        colors = [(0, 0, 0), (50, 50, 50), (100, 100, 100)]

        for i, char in enumerate(code):
            char_x = x + (i * text_width // len(code))
            char_y = y + random.randint(-5, 5)  # Slight vertical variation
            color = random.choice(colors)
            draw.text((char_x, char_y), char, font=font, fill=color)

        # Add some lines for noise
        for _ in range(3):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=(150, 150, 150), width=1)

        return img

    def verify_captcha(self, session_id, user_input):
        """Verify captcha code for the given session"""
        if session_id not in self.captchas:
            return {'success': False, 'error': 'Captcha no encontrado. Genera uno nuevo.'}

        captcha_data = self.captchas[session_id]

        # Check if expired
        if datetime.now() > captcha_data['expires']:
            del self.captchas[session_id]
            return {'success': False, 'error': 'Captcha expirado. Genera uno nuevo.'}

        # Check attempts
        if captcha_data['attempts'] >= self.max_attempts:
            del self.captchas[session_id]
            return {'success': False, 'error': 'Demasiados intentos fallidos. Genera un captcha nuevo.'}

        # Verify code
        if user_input.strip() == captcha_data['code']:
            captcha_data['verified'] = True
            return {'success': True, 'message': 'Captcha verificado correctamente'}
        else:
            captcha_data['attempts'] += 1
            remaining = self.max_attempts - captcha_data['attempts']
            if remaining > 0:
                return {'success': False, 'error': f'Código incorrecto. Te quedan {remaining} intentos.'}
            else:
                del self.captchas[session_id]
                return {'success': False, 'error': 'Código incorrecto. Se agotaron los intentos.'}

    def is_verified(self, session_id):
        """Check if session has verified captcha"""
        if session_id not in self.captchas:
            return False

        captcha_data = self.captchas[session_id]

        # Check if expired
        if datetime.now() > captcha_data['expires']:
            del self.captchas[session_id]
            return False

        return captcha_data.get('verified', False)

    def clean_expired(self):
        """Clean expired captchas"""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, data in self.captchas.items()
            if now > data['expires']
        ]
        for session_id in expired_sessions:
            del self.captchas[session_id]

# Global captcha manager instance
captcha_manager = CaptchaManager()