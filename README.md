# Book Search Engine

A Flask-based web application to search through your personal book collection stored in Google Spreadsheets.

## Features

- Search through your book collection stored in Google Sheets
- Clean, responsive web interface
- Docker support for local development
- Vercel deployment ready
- Built-in security features (rate limiting, captcha, input validation)
- Multi-sheet support with categories

## Setup

### Prerequisites

1. A Google Spreadsheet containing your book collection
2. Google Service Account credentials with access to Google Sheets API

### Google Sheets Setup

1. Create a Google Cloud Project
2. Enable the Google Sheets API
3. Create a Service Account and download the JSON credentials
4. Share your Google Spreadsheet with the service account email

### Local Development with Docker

1. Copy `.env.example` to `.env` and fill in your credentials:

   ```bash
   cp .env.example .env
   ```

2. Build and run with Docker Compose:

   ```bash
   docker compose up --build
   ```

3. Open <http://localhost:8080>

### Local Development without Docker

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:

   ```bash
   export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
   export GOOGLE_PROJECT_ID=your-project-id
   export GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nyour-private-key\n-----END PRIVATE KEY-----\n"
   export GOOGLE_CLIENT_EMAIL=your-service-account@your-project-id.iam.gserviceaccount.com
   # ... and other variables from your JSON file
   ```

3. Run the application:

   ```bash
   python app.py
   ```

### Vercel Deployment

1. Install Vercel CLI:

   ```bash
   npm i -g vercel
   ```

2. Deploy:

   ```bash
   vercel
   ```

3. Set environment variables in Vercel dashboard:
   - `GOOGLE_SPREADSHEET_ID`
   - `GOOGLE_PROJECT_ID`
   - `GOOGLE_PRIVATE_KEY`
   - `GOOGLE_CLIENT_EMAIL`
   - `GOOGLE_PRIVATE_KEY_ID`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_CERT_URL`
   - `FLASK_SECRET_KEY`

## Environment Variables

- `GOOGLE_SPREADSHEET_ID`: The ID of your Google Spreadsheet (found in the URL)

### Service Account Credentials (individual JSON fields):

- `GOOGLE_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_PRIVATE_KEY`: Private key (includes -----BEGIN PRIVATE KEY----- and -----END PRIVATE KEY-----)
- `GOOGLE_CLIENT_EMAIL`: Service account email
- `GOOGLE_PRIVATE_KEY_ID`: Private key ID
- `GOOGLE_CLIENT_ID`: Client ID
- `GOOGLE_CLIENT_CERT_URL`: Client certificate URL

### Security Configuration:
- `FLASK_SECRET_KEY`: Strong secret key for session security (32+ characters)
- `HTTPS_ENABLED`: Set to `true` in production with HTTPS
- `FLASK_ENV`: Set to `production` for production deployment

## Google Sheets Format

Your spreadsheet should have headers in the first row. The application will automatically detect and use all columns.

### Supported Sheet Structure:
- Multiple sheets with names: "LIT. ADULTO", "LIT. JUVENIL ADOLESCENTE", "LIT. INFANTIL", "EDUCACIÓN", "MANUALES"
- Common columns include:
  - CODIGO (Code)
  - NOMBRE DEL LIBRO (Book Name)
  - NOMBRE DEL AUTOR (Author Name)
  - EDITORIAL (Publisher)
  - OBSERVACIONES (Notes)
  - EJEMPLARES (Copies)

The search function will look through all columns and sheets for matches.

## Security Features

- Rate limiting on all endpoints
- Input validation and sanitization
- CAPTCHA protection against automation
- Secure session management
- XSS and CSRF protection
- Security headers implementation

See [SECURITY.md](SECURITY.md) for detailed security information.

## API Endpoints

- `GET /` - Main search interface
- `GET /search?q=query` - Search books
- `GET /api/books` - Get all books
- `GET /api/captcha/generate` - Generate captcha
- `GET /debug/config` - Debug configuration (development)
- `GET /debug/test-connection` - Test Google Sheets connection (development)
