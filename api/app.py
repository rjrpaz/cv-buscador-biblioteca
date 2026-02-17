from flask import Flask, render_template, request, jsonify, session
import os
import sys
import uuid
import secrets
import json
from datetime import datetime, timedelta

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

        # Debug: Check what we have
        print(f"Debug - project_id exists: {bool(project_id)}")
        print(f"Debug - private_key exists: {bool(private_key)}")
        print(f"Debug - client_email exists: {bool(client_email)}")

        if private_key:
            print(f"Debug - private_key length: {len(private_key)}")
            print(f"Debug - private_key starts with BEGIN: {private_key.startswith('-----BEGIN')}")

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

        print("Debug - Creating credentials...")
        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        print("Debug - Building service...")
        return build('sheets', 'v4', credentials=creds)

    except Exception as e:
        print(f"Google Sheets service error: {e}")
        return None

def get_books_data():
    """Fetch books from all sheets"""
    spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
    if not spreadsheet_id:
        raise Exception("GOOGLE_SPREADSHEET_ID not configured")

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
            print(f"Error reading sheet '{sheet_name}': {e}")
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

    if not query:
        return jsonify({'books': [], 'error': 'No se proporcionó término de búsqueda'})

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

@app.route('/debug/status')
def debug_status():
    # Test Google Sheets service
    service_status = "unknown"
    service_error = None
    try:
        service = get_google_sheets_service()
        if service:
            service_status = "success"
        else:
            service_status = "failed"
    except Exception as e:
        service_status = "error"
        service_error = str(e)

    return jsonify({
        'status': 'running',
        'flask_env': os.getenv('FLASK_ENV', 'not_set'),
        'environment_variables': {
            'has_secret_key': bool(os.getenv('FLASK_SECRET_KEY')),
            'has_spreadsheet_id': bool(os.getenv('GOOGLE_SPREADSHEET_ID')),
            'has_project_id': bool(os.getenv('GOOGLE_PROJECT_ID')),
            'has_private_key': bool(os.getenv('GOOGLE_PRIVATE_KEY')),
            'has_client_email': bool(os.getenv('GOOGLE_CLIENT_EMAIL')),
            'has_private_key_id': bool(os.getenv('GOOGLE_PRIVATE_KEY_ID')),
            'has_client_id': bool(os.getenv('GOOGLE_CLIENT_ID')),
            'has_client_cert_url': bool(os.getenv('GOOGLE_CLIENT_CERT_URL'))
        },
        'google_sheets_service': {
            'status': service_status,
            'error': service_error
        },
        'credentials_check': {
            'spreadsheet_id': os.getenv('GOOGLE_SPREADSHEET_ID', 'NOT_SET')[:20] + '...' if os.getenv('GOOGLE_SPREADSHEET_ID') else 'NOT_SET',
            'project_id': os.getenv('GOOGLE_PROJECT_ID', 'NOT_SET'),
            'client_email': os.getenv('GOOGLE_CLIENT_EMAIL', 'NOT_SET'),
            'private_key_length': len(os.getenv('GOOGLE_PRIVATE_KEY', '')) if os.getenv('GOOGLE_PRIVATE_KEY') else 0
        }
    })

# Vercel expects this
app = app