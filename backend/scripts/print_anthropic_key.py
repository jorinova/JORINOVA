from dotenv import load_dotenv
import os

# Loads environment variables from a .env file.
# By default, python-dotenv looks for a .env in the current working directory.
# If you run this script from backend/, it will pick backend/.env automatically.
load_dotenv()

key = os.getenv("ANTHROPIC_API_KEY", "")
if not key:
    print("ANTHROPIC_API_KEY: NOT SET")
else:
    # Never print secrets in CI/logs. Mask most of the key.
    masked = f"{key[:6]}...{key[-4:]}" if len(key) >= 10 else "***"
    print(f"ANTHROPIC_API_KEY: {masked}")


