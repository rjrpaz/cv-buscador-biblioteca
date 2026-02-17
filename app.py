from flask import Flask, render_template, request, jsonify, session
import os
import uuid
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google_sheets import get_books_data, search_books
from captcha_manager import captcha_manager
from security import SecurityManager, require_valid_input, security_headers

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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
def get_categories():
    """Get all available categories from the sheets"""
    try:
        from google_sheets import SHEET_NAMES
        return jsonify({'categories': SHEET_NAMES, 'error': None})
    except Exception as e:
        return jsonify({'categories': [], 'error': str(e)})

@app.route('/debug/config')
def debug_config():
    """Debug endpoint to check configuration"""
    config_status = {
        'GOOGLE_SPREADSHEET_ID': bool(os.getenv('GOOGLE_SPREADSHEET_ID')),
        'GOOGLE_PROJECT_ID': bool(os.getenv('GOOGLE_PROJECT_ID')),
        'GOOGLE_PRIVATE_KEY': bool(os.getenv('GOOGLE_PRIVATE_KEY')),
        'GOOGLE_CLIENT_EMAIL': bool(os.getenv('GOOGLE_CLIENT_EMAIL')),
        'GOOGLE_PRIVATE_KEY_ID': bool(os.getenv('GOOGLE_PRIVATE_KEY_ID')),
        'GOOGLE_CLIENT_ID': bool(os.getenv('GOOGLE_CLIENT_ID')),
        'GOOGLE_CLIENT_CERT_URL': bool(os.getenv('GOOGLE_CLIENT_CERT_URL'))
    }

    # Show actual values for non-sensitive data
    config_values = {
        'GOOGLE_SPREADSHEET_ID': os.getenv('GOOGLE_SPREADSHEET_ID', 'NOT_SET'),
        'GOOGLE_PROJECT_ID': os.getenv('GOOGLE_PROJECT_ID', 'NOT_SET'),
        'GOOGLE_CLIENT_EMAIL': os.getenv('GOOGLE_CLIENT_EMAIL', 'NOT_SET'),
    }

    return jsonify({
        'config_status': config_status,
        'config_values': config_values,
        'sheets_to_read': ['LIT. ADULTO', 'LIT. JUVENIL ADOLESCENTE', 'LIT. INFANTIL', 'EDUCACIÓN', 'MANUALES']
    })

@app.route('/debug/test-credentials')
def test_credentials():
    """Test if the service account credentials are valid"""
    try:
        from google_sheets import get_google_sheets_service

        service = get_google_sheets_service()

        # Try to access a simple API endpoint to test credentials
        from googleapiclient.discovery import build

        # Get service account info
        drive_service = build('drive', 'v3', credentials=service._http.credentials)

        # Try to list some files to test if credentials work
        results = drive_service.files().list(pageSize=1, fields="files(id,name)").execute()

        return jsonify({
            'success': True,
            'message': 'Credentials are working',
            'service_account_can_access_drive': True
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'message': 'There is an issue with the service account credentials',
            'traceback': traceback.format_exc()
        })

@app.route('/debug/test-connection')
def test_connection():
    """Test Google Sheets connection"""
    try:
        from google_sheets import get_google_sheets_service, SPREADSHEET_ID

        if not SPREADSHEET_ID:
            return jsonify({'error': 'GOOGLE_SPREADSHEET_ID no está configurado'})

        # Clean the spreadsheet ID (remove quotes if present)
        clean_id = SPREADSHEET_ID.strip('"\'')

        service = get_google_sheets_service()

        # First, check if we can access the document via Drive API
        try:
            from googleapiclient.discovery import build

            drive_service = build('drive', 'v3', credentials=service._http.credentials)

            # Get file metadata
            file_metadata = drive_service.files().get(
                fileId=clean_id,
                fields='id,name,mimeType'
            ).execute()

            # If we can access via Drive but not Sheets, it's likely a permissions issue
            sheets_error = None
            try:
                spreadsheet = service.spreadsheets().get(spreadsheetId=clean_id).execute()
                sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]

                return jsonify({
                    'success': True,
                    'spreadsheet_title': spreadsheet['properties']['title'],
                    'available_sheets': sheet_names,
                    'expected_sheets': ['LIT. ADULTO', 'LIT. JUVENIL ADOLESCENTE', 'LIT. INFANTIL', 'EDUCACIÓN', 'MANUALES']
                })

            except Exception as sheets_error:
                return jsonify({
                    'success': False,
                    'drive_access': True,
                    'sheets_access': False,
                    'document_info': {
                        'name': file_metadata.get('name'),
                        'mimeType': file_metadata.get('mimeType'),
                        'is_google_sheets': file_metadata.get('mimeType') == 'application/vnd.google-apps.spreadsheet'
                    },
                    'diagnosis': 'Can access document via Drive API but not Sheets API',
                    'solutions': [
                        'Try sharing the document as "Editor" instead of "Viewer"',
                        'Make sure the document is shared with the exact email from debug/config',
                        'Wait a few minutes for permissions to propagate',
                        'Check if the Google Sheets API is enabled in your Google Cloud project'
                    ],
                    'sheets_error': str(sheets_error)
                })

        except Exception as drive_error:
            return jsonify({
                'success': False,
                'drive_access': False,
                'error': str(drive_error),
                'diagnosis': 'Cannot access document via Drive API',
                'solutions': [
                    'Verify the SPREADSHEET_ID is correct',
                    'Make sure the service account email is shared with the document',
                    'Check that the service account credentials are valid'
                ]
            })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'spreadsheet_id_used': clean_id if 'clean_id' in locals() else 'N/A',
            'traceback': traceback.format_exc()
        })

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)