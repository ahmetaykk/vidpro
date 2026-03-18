"""
Input validation utilities for VidPro
"""
import os
import re
from urllib.parse import urlparse

def validate_file_path(path, allow_absolute=True, base_dir=None):
    """
    Validate file path to prevent directory traversal attacks
    
    Args:
        path (str): Input file path
        allow_absolute (bool): Whether absolute paths are allowed
        base_dir (str): Base directory for relative paths
        
    Returns:
        tuple: (is_valid, safe_path, error_message)
    """
    if not path or not isinstance(path, str):
        return False, None, "Invalid path: path must be a non-empty string"
    
    # Remove any null bytes
    path = path.replace('\x00', '')
    
    # Check for directory traversal attempts
    if '..' in path or path.startswith('/'):
        if not allow_absolute or '..' in path:
            return False, None, "Invalid path: directory traversal not allowed"
    
    # If relative path and base_dir provided, resolve it
    if base_dir and not os.path.isabs(path):
        safe_path = os.path.abspath(os.path.join(base_dir, path))
    else:
        safe_path = os.path.abspath(path)
    
    # Additional security check: ensure safe_path is within base_dir if provided
    if base_dir and not safe_path.startswith(os.path.abspath(base_dir)):
        return False, None, "Invalid path: path outside allowed directory"
    
    return True, safe_path, None

def validate_url(url):
    """
    Validate URL format and check for suspicious patterns
    
    Args:
        url (str): Input URL
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "Invalid URL: must be a non-empty string"
    
    url = url.strip()
    
    # Basic URL format check
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL: missing scheme or domain"
        
        # Only allow common schemes
        allowed_schemes = ['http', 'https']
        if parsed.scheme.lower() not in allowed_schemes:
            return False, f"Invalid URL: scheme '{parsed.scheme}' not allowed"
            
        # Check for localhost/private IPs in production (optional security)
        # This could be enhanced based on requirements
        
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"
    
    return True, None

def validate_json_input(data, required_fields=None, optional_fields=None):
    """
    Validate JSON input data
    
    Args:
        data (dict): Input data
        required_fields (list): List of required field names
        optional_fields (list): List of optional field names
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Invalid input: must be a JSON object"
    
    if required_fields:
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    if optional_fields:
        # Check for unexpected fields
        allowed_fields = set(required_fields or []) | set(optional_fields)
        unexpected_fields = [field for field in data if field not in allowed_fields]
        if unexpected_fields:
            return False, f"Unexpected fields: {', '.join(unexpected_fields)}"
    
    return True, None

def sanitize_filename(filename):
    """
    Sanitize filename to prevent filesystem issues
    
    Args:
        filename (str): Input filename
        
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "untitled"
    
    # Replace dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    # Ensure it's not empty after sanitization
    if not filename.strip():
        return "untitled"
    
    return filename.strip()

def validate_cookie_file_path(path):
    """
    Validate cookie file path with additional security checks
    
    Args:
        path (str): Cookie file path
        
    Returns:
        tuple: (is_valid, safe_path, error_message)
    """
    is_valid, safe_path, error = validate_file_path(
        path, 
        allow_absolute=True, 
        base_dir=os.path.dirname(__file__)
    )
    
    if not is_valid:
        return False, None, error
    
    # Additional check: ensure it's a .txt file
    if not safe_path.endswith('.txt'):
        return False, None, "Cookie file must be a .txt file"
    
    return True, safe_path, None
