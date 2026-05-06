import urllib.request
import json

url = "http://localhost:8080/api/purecf/admin/validate"
headers = {'Content-Type': 'application/json'}
payload = {
    "params": {
        "pin": "1234"
    }
}

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode('utf-8')
        print(f"Response: {res_body}")
except Exception as e:
    print(f"Error: {e}")
