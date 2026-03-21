import requests
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
import json
from django.conf import settings

host = 'https://jooble.org'
key = settings.JOOBLE_API_KEY
url = f"{host}/api/{key}"
headers = {
    "Content-type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
body = {"keywords": "data-scientist", "location": ""}

try:
    response = requests.post(url, json=body, headers=headers)
    print(f"Status Code: {response.status_code}")
    print("Response:", response.text[:500])
except Exception as e:
    print("Exception:", e)
