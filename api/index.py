from flask import Flask, render_template, request, jsonify, session
import os
import sys
import uuid
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google_sheets import get_books_data, search_books
from captcha_manager import captcha_manager
from security import SecurityManager, require_valid_input, security_headers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Security configurations
secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
if not SecurityManager.validate_secret_key(secret_key):
    # Only require secure key in production, allow development with warning
    flask_env = os.getenv('FLASK_ENV', 'development').lower()
    if flask_env == 'production':
        raise ValueError("FLASK_SECRET_KEY must be set to a secure value in production")
    else:
        logger.warning("Using default secret key. Set FLASK_SECRET_KEY for production!")
        # Generate a temporary secure key for development
        import secrets
        secret_key = secrets.token_urlsafe(32)
        logger.info("Generated temporary secure key for development session")

app.secret_key = secret_key

# Session security
app.config['SESSION_COOKIE_SECURE'] = True if os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=lambda: SecurityManager.get_client_ip(),
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

@app.route('/')
@security_headers
def index():
    return render_template('index.html')

@app.route('/search')
@limiter.limit("30 per minute")
@security_headers
@require_valid_input
def search():
    query = request.args.get('q', '')
    category = request.args.get('category', '')  # Optional category filter
    captcha_code = request.args.get('captcha', '')

    if not query:
        return jsonify({'books': [], 'error': 'No se proporcionó término de búsqueda'})

    # Get or create session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']

    # Verify captcha
    if not captcha_manager.is_verified(session_id):
        if not captcha_code:
            return jsonify({'books': [], 'error': 'Captcha requerido', 'captcha_required': True})

        verification_result = captcha_manager.verify_captcha(session_id, captcha_code)
        if not verification_result['success']:
            return jsonify({'books': [], 'error': verification_result['error'], 'captcha_required': True})

    try:
        books = search_books(query, category)
        return jsonify({'books': books, 'error': None})
    except Exception as e:
        return jsonify({'books': [], 'error': str(e)})

@app.route('/api/books')
@limiter.limit("20 per minute")
@security_headers
def all_books():
    category = request.args.get('category', '')  # Optional category filter
    try:
        books = get_books_data()

        # Filter by category if specified
        if category:
            books = [book for book in books if book.get('CATEGORÍA', '').lower() == category.lower()]

        return jsonify({'books': books, 'error': None})
    except Exception as e:
        return jsonify({'books': [], 'error': str(e)})

@app.route('/api/categories')
@security_headers
def get_categories():
    """Get all available categories from the sheets"""
    try:
        from google_sheets import SHEET_NAMES
        return jsonify({'categories': SHEET_NAMES, 'error': None})
    except Exception as e:
        return jsonify({'categories': [], 'error': str(e)})

@app.route('/api/captcha/generate')
@limiter.limit("10 per minute")
@security_headers
def generate_captcha():
    """Generate a new captcha"""
    try:
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())

        session_id = session['session_id']
        captcha_data = captcha_manager.generate_captcha(session_id)

        logger.info(f"Captcha generated for session: {session_id[:8]}...")

        return jsonify({
            'success': True,
            'captcha': captcha_data
        })

    except Exception as e:
        logger.error(f"Error generating captcha: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@app.route('/api/captcha/verify')
@limiter.limit("20 per minute")
@security_headers
@require_valid_input
def verify_captcha():
    """Verify captcha code"""
    try:
        if 'session_id' not in session:
            return jsonify({'success': False, 'error': 'Sesión no encontrada'})

        session_id = session['session_id']
        captcha_code = request.args.get('code', '')

        if not captcha_code:
            return jsonify({'success': False, 'error': 'Código de captcha requerido'})

        result = captcha_manager.verify_captcha(session_id, captcha_code)

        if result.get('success'):
            logger.info(f"Captcha verified successfully for session: {session_id[:8]}...")
        else:
            logger.warning(f"Captcha verification failed for session: {session_id[:8]}... - {result.get('error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error verifying captcha: {str(e)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

# For Vercel
handler = app