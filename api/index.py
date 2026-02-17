from flask import Flask, render_template, request, jsonify, session
import os
import sys
import uuid
import logging

# Add parent directory to path to import our modules
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Try to import with error handling
try:
    from google_sheets import get_books_data, search_books
    from captcha_manager import captcha_manager
    from security import SecurityManager, require_valid_input, security_headers
    IMPORTS_SUCCESS = True
except Exception as e:
    print(f"Import error: {e}")
    IMPORTS_SUCCESS = False

# Simplified rate limiting for Vercel
class SimpleLimiter:
    def limit(self, rate):
        def decorator(f):
            return f
        return decorator

# Use simplified limiter if Flask-Limiter fails
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except:
    Limiter = SimpleLimiter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Security configurations
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    # Generate a secure key for production
    import secrets
    secret_key = secrets.token_urlsafe(32)
    logger.warning("No FLASK_SECRET_KEY found, generated temporary key")
elif secret_key == 'your-secret-key-here-change-in-production':
    # Default key detected, generate a secure one
    import secrets
    secret_key = secrets.token_urlsafe(32)
    logger.warning("Default secret key detected, generated secure key")

app.secret_key = secret_key

# Session security
app.config['SESSION_COOKIE_SECURE'] = True if os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Rate limiting (simplified for Vercel)
try:
    if IMPORTS_SUCCESS:
        limiter = Limiter(
            app=app,
            key_func=lambda: SecurityManager.get_client_ip() if 'SecurityManager' in globals() else request.remote_addr,
            default_limits=["200 per day", "50 per hour"],
            storage_uri="memory://"
        )
    else:
        limiter = SimpleLimiter()
except Exception as e:
    logger.warning(f"Rate limiting disabled due to error: {e}")
    limiter = SimpleLimiter()

# Fallback decorators if imports failed
def fallback_decorator(f):
    return f

security_headers = security_headers if IMPORTS_SUCCESS else fallback_decorator
require_valid_input = require_valid_input if IMPORTS_SUCCESS else fallback_decorator

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
        if not IMPORTS_SUCCESS:
            return jsonify({'books': [], 'error': 'Servicio temporalmente no disponible'})

        books = search_books(query, category)
        return jsonify({'books': books, 'error': None})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'books': [], 'error': 'Error interno del servidor'})

@app.route('/api/books')
@limiter.limit("20 per minute")
@security_headers
def all_books():
    category = request.args.get('category', '')  # Optional category filter
    try:
        if not IMPORTS_SUCCESS:
            return jsonify({'books': [], 'error': 'Servicio temporalmente no disponible'})

        books = get_books_data()

        # Filter by category if specified
        if category:
            books = [book for book in books if book.get('CATEGORÍA', '').lower() == category.lower()]

        return jsonify({'books': books, 'error': None})
    except Exception as e:
        logger.error(f"Books API error: {e}")
        return jsonify({'books': [], 'error': 'Error interno del servidor'})

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

@app.route('/debug/status')
def debug_status():
    """Debug endpoint to check system status"""
    return jsonify({
        'status': 'running',
        'imports_success': IMPORTS_SUCCESS,
        'flask_env': os.getenv('FLASK_ENV', 'not_set'),
        'has_secret_key': bool(os.getenv('FLASK_SECRET_KEY')),
        'has_spreadsheet_id': bool(os.getenv('GOOGLE_SPREADSHEET_ID')),
        'python_path': sys.path[:3]  # First 3 entries
    })

# For Vercel
handler = app