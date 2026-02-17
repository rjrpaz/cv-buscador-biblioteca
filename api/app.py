from flask import Flask, render_template, request, jsonify, session
import os
import sys
import uuid
import secrets
import json
import random
import string
import time
import base64
import io
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

# Add parent directory to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Simple security configuration
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key or secret_key == 'your-secret-key-here-change-in-production':
    secret_key = secrets.token_urlsafe(32)

app.secret_key = secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

# Simple captcha manager for serverless
class SimpleCaptchaManager:
    def __init__(self):
        self.timeout_minutes = 15
        self.max_attempts = 3

    def generate_captcha(self, session_id):
        """Generate a simple captcha"""
        try:
            # Ensure randomness by seeding with current time and session
            random.seed(time.time_ns() + hash(session_id))

            # Generate 4-digit code
            code = ''.join(random.choices(string.digits, k=4))

            # Create simple image
            img = self._create_captcha_image(code)

            # Convert to base64
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

            # Store in session
            expires = datetime.now() + timedelta(minutes=self.timeout_minutes)
            session['captcha'] = {
                'code': code,
                'expires': expires.isoformat(),
                'attempts': 0
            }

            return {
                'image': f"data:image/png;base64,{img_base64}",
                'expires_at': expires.isoformat()
            }
        except Exception as e:
            return None

    def _create_captcha_image(self, code):
        """Create simple captcha image"""
        width, height = 160, 60
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # Add background noise
        for _ in range(30):
            x, y = random.randint(0, width), random.randint(0, height)
            draw.point((x, y), fill=(200, 200, 200))

        # Draw code
        try:
            font = ImageFont.load_default()
        except:
            font = None

        # Calculate position
        if font:
            bbox = draw.textbbox((0, 0), code, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        else:
            text_width, text_height = 40, 20

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Draw text with variations
        for i, char in enumerate(code):
            char_x = x + (i * text_width // len(code))
            char_y = y + random.randint(-3, 3)
            color = random.choice([(0, 0, 0), (50, 50, 50), (100, 100, 100)])
            draw.text((char_x, char_y), char, font=font, fill=color)

        # Add noise lines
        for _ in range(2):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=(150, 150, 150), width=1)

        return img

    def verify_captcha(self, session_id, user_input):
        """Verify captcha"""
        if 'captcha' not in session:
            return {'success': False, 'error': 'Captcha no encontrado. Genera uno nuevo.'}

        captcha_data = session['captcha']

        # Check expiry
        expires = datetime.fromisoformat(captcha_data['expires'])
        if datetime.now() > expires:
            session.pop('captcha', None)
            return {'success': False, 'error': 'Captcha expirado. Genera uno nuevo.'}

        # Check attempts
        if captcha_data['attempts'] >= self.max_attempts:
            session.pop('captcha', None)
            return {'success': False, 'error': 'Demasiados intentos. Genera un captcha nuevo.'}

        # Verify code
        if user_input.strip() == captcha_data['code']:
            session['captcha']['verified'] = True
            session['captcha']['verified_at'] = datetime.now().isoformat()
            # Reset search count after successful verification to give user grace period
            session['search_count'] = 0
            return {'success': True, 'message': 'Captcha verificado correctamente'}
        else:
            session['captcha']['attempts'] += 1
            remaining = self.max_attempts - session['captcha']['attempts']
            if remaining > 0:
                return {'success': False, 'error': f'Código incorrecto. Te quedan {remaining} intentos.'}
            else:
                session.pop('captcha', None)
                return {'success': False, 'error': 'Código incorrecto. Se agotaron los intentos.'}

    def is_verified(self, session_id):
        """Check if captcha is verified and still valid"""
        if 'captcha' not in session:
            return False

        captcha_data = session['captcha']

        # Check if verified
        if not captcha_data.get('verified', False):
            return False

        # Check expiry of the captcha itself
        expires = datetime.fromisoformat(captcha_data['expires'])
        if datetime.now() > expires:
            session.pop('captcha', None)
            return False

        # Check if verification is still within grace period (15 minutes from verification)
        verified_at = captcha_data.get('verified_at')
        if verified_at:
            verification_time = datetime.fromisoformat(verified_at)
            grace_period = timedelta(minutes=self.timeout_minutes)
            if datetime.now() > verification_time + grace_period:
                session.pop('captcha', None)
                return False

        return True

# Initialize captcha manager
captcha_manager = SimpleCaptchaManager()

# Simple Google Sheets integration for Vercel
def get_google_sheets_service():
    """Simple Google Sheets service initialization"""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials

        # Get environment variables
        project_id = os.getenv('GOOGLE_PROJECT_ID')
        private_key = os.getenv('GOOGLE_PRIVATE_KEY')
        client_email = os.getenv('GOOGLE_CLIENT_EMAIL')

        # Fix private key formatting - Handle various formats
        if private_key:
            # Remove outer quotes if present
            private_key = private_key.strip('"\'')

            # Handle JSON array format (key split into multiple strings)
            if private_key.startswith('"') or '","' in private_key:
                # Remove all quotes and commas, then join
                private_key = private_key.replace('"', '').replace(',', '\n')

            # Ensure proper line breaks
            private_key = private_key.replace('\\n', '\n')

            # If the key doesn't have proper headers, it might be malformed
            if 'BEGIN PRIVATE KEY' in private_key and '\n' not in private_key:
                # Split the key into proper lines
                private_key = private_key.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n')
                private_key = private_key.replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----')
                # Add line breaks every 64 characters in the key content
                parts = private_key.split('\n')
                if len(parts) == 3 and len(parts[1]) > 64:  # Long key without breaks
                    key_content = parts[1]
                    formatted_content = []
                    for i in range(0, len(key_content), 64):
                        formatted_content.append(key_content[i:i+64])
                    private_key = parts[0] + '\n' + '\n'.join(formatted_content) + '\n' + parts[2]


        # Check required fields first
        if not project_id:
            raise Exception("GOOGLE_PROJECT_ID is missing")
        if not private_key:
            raise Exception("GOOGLE_PRIVATE_KEY is missing")
        if not client_email:
            raise Exception("GOOGLE_CLIENT_EMAIL is missing")

        # Build service account info from environment variables
        service_account_info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
            "private_key": private_key,
            "client_email": client_email,
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_CERT_URL')
        }

        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        service = build('sheets', 'v4', credentials=creds)


        return service

    except Exception as e:
        return None

def get_books_data():
    """Fetch books from all sheets"""
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    if not spreadsheet_id:
        raise Exception("GOOGLE_SPREADSHEET_ID not configured")

    # Clean spreadsheet ID - remove quotes if present
    spreadsheet_id = spreadsheet_id.strip('"\'')


    service = get_google_sheets_service()
    if not service:
        raise Exception("Could not initialize Google Sheets service")

    sheet_names = ["LIT. ADULTO", "LIT. JUVENIL ADOLESCENTE", "LIT. INFANTIL", "EDUCACIÓN", "MANUALES"]
    all_books = []

    for sheet_name in sheet_names:
        try:
            range_name = f"'{sheet_name}'!A:Z"
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])
            if not values:
                continue

            headers = values[0]
            for row in values[1:]:
                if not any(cell.strip() for cell in row if cell):
                    continue

                padded_row = row + [''] * (len(headers) - len(row))
                book = dict(zip(headers, padded_row))
                book['CATEGORÍA'] = sheet_name
                all_books.append(book)

        except Exception as e:
            continue

    return all_books

def search_books(query, category_filter=None):
    """Search books"""
    books = get_books_data()
    query_lower = query.lower()
    matching_books = []

    for book in books:
        if category_filter and book.get('CATEGORÍA', '').lower() != category_filter.lower():
            continue

        book_text = ' '.join(str(value).lower() for value in book.values())
        if query_lower in book_text:
            matching_books.append(book)

    return matching_books

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    captcha_code = request.args.get('captcha', '')

    if not query:
        return jsonify({'books': [], 'error': 'No se proporcionó término de búsqueda'})

    # Simple rate limiting - require captcha after a few searches
    session_id = session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

    # Track search count
    search_count = session.get('search_count', 0)
    search_count += 1
    session['search_count'] = search_count

    # Check if user has valid captcha verification
    captcha_verified = captcha_manager.is_verified(session_id)

    # Require captcha after 3 searches, unless already verified
    if search_count > 3 and not captcha_verified:
        if not captcha_code:
            return jsonify({
                'books': [],
                'captcha_required': True,
                'error': 'Se requiere verificación captcha'
            })

        # Try to verify the provided captcha
        verification_result = captcha_manager.verify_captcha(session_id, captcha_code)
        if not verification_result['success']:
            return jsonify({
                'books': [],
                'captcha_required': True,
                'error': verification_result['error']
            })

    try:
        books = search_books(query, category)
        return jsonify({'books': books, 'error': None})
    except Exception as e:
        return jsonify({'books': [], 'error': f'Error: {str(e)}'})

@app.route('/api/books')
def all_books():
    try:
        books = get_books_data()
        return jsonify({'books': books, 'error': None})
    except Exception as e:
        return jsonify({'books': [], 'error': f'Error: {str(e)}'})

@app.route('/api/categories')
def get_categories():
    return jsonify({
        'categories': ["LIT. ADULTO", "LIT. JUVENIL ADOLESCENTE", "LIT. INFANTIL", "EDUCACIÓN", "MANUALES"],
        'error': None
    })

@app.route('/api/captcha/generate', methods=['GET', 'POST'])
def generate_captcha():
    """Generate a new captcha"""
    try:
        session_id = session.get('session_id', str(uuid.uuid4()))
        session['session_id'] = session_id

        captcha_data = captcha_manager.generate_captcha(session_id)

        if captcha_data:
            return jsonify({
                'success': True,
                'captcha': captcha_data,
                'message': 'Captcha generado correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No se pudo generar el captcha'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500

@app.route('/api/captcha/verify', methods=['POST'])
def verify_captcha():
    """Verify captcha code"""
    try:
        data = request.get_json() or {}
        captcha_code = data.get('code', '')

        if not captcha_code:
            return jsonify({
                'success': False,
                'error': 'Código de captcha requerido'
            }), 400

        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Sesión no válida'
            }), 400

        result = captcha_manager.verify_captcha(session_id, captcha_code)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor'
        }), 500


# Vercel expects this
app = app