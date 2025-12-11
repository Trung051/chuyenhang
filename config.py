"""
Configuration file for Shipment Management App
Contains user credentials, status values, and default suppliers data
"""

# User credentials for simple authentication
USERS = {
    'admin': 'admin123',
    'user': 'user123',
    'staff': 'staff123'
}

# Shipment status values
STATUS_VALUES = ['Đang gửi', 'Đã nhận', 'Hư hỏng', 'Mất']

# Default status for new shipments
DEFAULT_STATUS = 'Đang gửi'

# Default suppliers data (will be seeded into database)
DEFAULT_SUPPLIERS = [
    {
        'id': 1,
        'name': 'GHN',
        'contact': '0987654321',
        'address': 'Hà Nội',
        'is_active': True
    },
    {
        'id': 2,
        'name': 'J&T',
        'contact': '0912345678',
        'address': 'TP.HCM',
        'is_active': True
    },
    {
        'id': 3,
        'name': 'Ahamove',
        'contact': '0998765432',
        'address': 'TP.HCM',
        'is_active': True
    }
]

# Database file path
DB_PATH = 'shipments.db'

# Telegram settings
TELEGRAM_TOKEN = '8292303287:AAFn5UVMHgVAmuBdkdlCnfbwME7noLyHDIw'
# Group/Chat ID (negative for groups). Updated to new group.
TELEGRAM_CHAT_ID = -1003093937806
