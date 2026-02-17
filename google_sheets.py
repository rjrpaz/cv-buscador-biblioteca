import os
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Configuration
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '').strip('"\'') if os.getenv('GOOGLE_SPREADSHEET_ID') else None
SHEET_NAMES = [
    "LIT. ADULTO",
    "LIT. JUVENIL ADOLESCENTE",
    "LIT. INFANTIL",
    "EDUCACIÓN",
    "MANUALES"
]

def get_google_sheets_service():
    """Initialize Google Sheets API service."""
    # Build service account info from individual environment variables
    service_account_info = {
        "type": os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE', 'service_account'),
        "project_id": os.getenv('GOOGLE_PROJECT_ID'),
        "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('GOOGLE_PRIVATE_KEY'),
        "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "auth_uri": os.getenv('GOOGLE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
        "token_uri": os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
        "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs'),
        "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_CERT_URL')
    }

    # Check required fields
    required_fields = ['project_id', 'private_key', 'client_email']
    missing_fields = [field for field in required_fields if not service_account_info.get(field)]

    if missing_fields:
        raise Exception(f"Faltan credenciales requeridas de Google: {', '.join(missing_fields.upper())}")

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    )

    service = build('sheets', 'v4', credentials=creds)
    return service

def get_books_data():
    """Fetch all books data from all sheets in Google Spreadsheet."""
    if not SPREADSHEET_ID:
        raise Exception("ID de hoja de cálculo de Google no encontrado. Configura la variable de entorno GOOGLE_SPREADSHEET_ID.")

    service = get_google_sheets_service()
    sheet = service.spreadsheets()

    all_books = []

    for sheet_name in SHEET_NAMES:
        try:
            # Fetch data from each sheet
            range_name = f"'{sheet_name}'!A:Z"
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name
            ).execute()

            values = result.get('values', [])

            if not values:
                continue

            # Assume first row contains headers
            headers = values[0]

            # Process each row in the sheet
            for row in values[1:]:
                # Skip empty rows
                if not any(cell.strip() for cell in row if cell):
                    continue

                # Pad row with empty strings if it's shorter than headers
                padded_row = row + [''] * (len(headers) - len(row))
                book = dict(zip(headers, padded_row))

                # Add category field based on sheet name
                book['CATEGORÍA'] = sheet_name

                all_books.append(book)

        except Exception as e:
            # Continue with other sheets if one fails
            print(f"Error reading sheet '{sheet_name}': {str(e)}")
            continue

    return all_books

def search_books(query, category_filter=None):
    """Search books based on query string and optional category filter."""
    books = get_books_data()
    query_lower = query.lower()

    matching_books = []

    for book in books:
        # Filter by category if specified
        if category_filter and book.get('CATEGORÍA', '').lower() != category_filter.lower():
            continue

        # Search in all fields of the book
        book_text = ' '.join(str(value).lower() for value in book.values())
        if query_lower in book_text:
            matching_books.append(book)

    return matching_books