import urllib.request

try:
    resp = urllib.request.urlopen("https://evil.example.com", timeout=5)
    print(resp.read())
except Exception as e:
    print(f"BLOCKED: {e}")
