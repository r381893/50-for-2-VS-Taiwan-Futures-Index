
import requests

try:
    print("Testing connectivity to finance.yahoo.com...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    r = requests.get("https://finance.yahoo.com", headers=headers, timeout=10)
    print(f"Status Code: {r.status_code}")
    print(f"Response (first 100 chars): {r.text[:100]}")
    
    if r.status_code == 200:
        print("Connectivity OK. The issue is likely with the API endpoint specific blocking.")
    else:
        print("Connectivity blocked/limited on main site.")

except Exception as e:
    print(f"Connectivity Test Failed: {e}")
