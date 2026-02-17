"""
Security utilities and configurations
"""
import os
import re
import secrets
from functools import wraps
from flask import request, jsonify, current_app
from werkzeug.exceptions import TooManyRequests
import bleach

class SecurityManager:
    """Handles security-related operations"""

    # Allowed HTML tags and attributes for sanitization
    ALLOWED_TAGS = []
    ALLOWED_ATTRIBUTES = {}

    @staticmethod
    def generate_secret_key():
        """Generate a secure secret key"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_secret_key(key):
        """Validate that secret key is secure enough"""
        if not key or key == 'your-secret-key-here-change-in-production':
            return False
        if len(key) < 32:
            return False
        return True

    @staticmethod
    def sanitize_input(text):
        """Sanitize user input to prevent XSS"""
        if not isinstance(text, str):
            return str(text)

        # Remove any HTML tags
        clean_text = bleach.clean(text, tags=SecurityManager.ALLOWED_TAGS,
                                attributes=SecurityManager.ALLOWED_ATTRIBUTES, strip=True)

        # Additional cleaning for search queries
        clean_text = clean_text.strip()

        # Limit length
        if len(clean_text) > 1000:
            clean_text = clean_text[:1000]

        return clean_text

    @staticmethod
    def validate_search_query(query):
        """Validate search query parameters"""
        if not query:
            return False, "Consulta vacía"

        query = query.strip()

        if len(query) < 1:
            return False, "Consulta muy corta"

        if len(query) > 500:
            return False, "Consulta muy larga"

        # Check for suspicious patterns
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'on\w+\s*=',
            r'eval\s*\(',
            r'document\.',
            r'window\.',
        ]

        query_lower = query.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return False, "Consulta contiene caracteres no permitidos"

        return True, "OK"

    @staticmethod
    def validate_captcha_input(captcha_code):
        """Validate captcha input"""
        if not isinstance(captcha_code, str):
            return False

        # Should be exactly 4 digits
        if not re.match(r'^\d{4}$', captcha_code.strip()):
            return False

        return True

    @staticmethod
    def get_client_ip():
        """Get client IP address, considering proxies"""
        # Check for forwarded IP (common in production with reverse proxies)
        if 'X-Forwarded-For' in request.headers:
            # Take the first IP in the chain
            ip = request.headers['X-Forwarded-For'].split(',')[0].strip()
            if ip:
                return ip

        if 'X-Real-IP' in request.headers:
            ip = request.headers['X-Real-IP'].strip()
            if ip:
                return ip

        return request.remote_addr or '127.0.0.1'

def require_valid_input(f):
    """Decorator to validate and sanitize input parameters"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validate search query if present
        if 'q' in request.args:
            query = request.args.get('q', '')
            is_valid, message = SecurityManager.validate_search_query(query)
            if not is_valid:
                return jsonify({'error': f'Entrada no válida: {message}'}), 400

            # Sanitize the query
            sanitized_query = SecurityManager.sanitize_input(query)
            request.args = request.args.copy()
            request.args['q'] = sanitized_query

        # Validate captcha if present
        if 'captcha' in request.args:
            captcha = request.args.get('captcha', '')
            if not SecurityManager.validate_captcha_input(captcha):
                return jsonify({'error': 'Formato de captcha inválido'}), 400

        return f(*args, **kwargs)
    return decorated_function

def security_headers(f):
    """Add security headers to responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)

        # Convert string responses to proper Response objects
        if isinstance(response, str):
            from flask import make_response
            response = make_response(response)
        elif isinstance(response, tuple):
            from flask import make_response
            response = make_response(*response)

        # Add security headers
        if hasattr(response, 'headers'):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

            # Only add HSTS in production HTTPS
            if request.is_secure:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response
    return decorated_function