import requests

url = "http://localhost:8000/api/upload"
files = {
    'file': ('test.pdf', b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF', 'application/pdf')
}

try:
    resp = requests.post(url, files=files)
    print('Status:', resp.status_code)
    print('Headers:', resp.headers)
    try:
        print('JSON body:', resp.json())
    except Exception:
        print('Text body:', resp.text)
except Exception as e:
    print('Request error:', e)
