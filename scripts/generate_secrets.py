"""
Generate strong secrets for production .env.production
Run this BEFORE first deployment.
"""
import secrets
import string
import sys

def strong_password(length=24):
    chars = string.ascii_letters + string.digits + '@#$%!&'
    while True:
        pwd = ''.join(secrets.choice(chars) for _ in range(length))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_special= any(c in '@#$%!&' for c in pwd)
        if has_upper and has_lower and has_digit and has_special:
            return pwd

print('=' * 60)
print('JORINOVA NEXUS ALIS-X — Production Secrets Generator')
print('Copy these into backend/.env.production')
print('=' * 60)
print()

jwt_secret   = secrets.token_hex(32)
db_password  = strong_password(24)
redis_password = secrets.token_urlsafe(24)
flower_password = strong_password(16)

print(f'SECRET_KEY={jwt_secret}')
print()
print(f'DB_PASSWORD={db_password}')
print()
print(f'REDIS_PASSWORD={redis_password}')
print(f'REDIS_URL=redis://:{redis_password}@redis:6379/0')
print(f'CELERY_BROKER_URL=redis://:{redis_password}@redis:6379/0')
print(f'CELERY_RESULT_BACKEND=redis://:{redis_password}@redis:6379/1')
print()
print(f'FLOWER_PASSWORD={flower_password}')
print()
print('=' * 60)
print('⚠️  Store these safely. Do NOT commit to Git.')
print('⚠️  Run this only ONCE per deployment environment.')
