import requests
r = requests.post(
    "http://127.0.0.1:5000/api/v1/messung",
    json={"knoten_id": "DE-001", "kanal": 1, "wert_uv": 1234.5}
)
print(r.status_code)
print(r.text)