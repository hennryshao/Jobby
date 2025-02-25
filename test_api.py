import requests
import json

# 发送请求到API
response = requests.post(
    'http://localhost:8081/api/search',
    json={
        'job_title': 'AI Consultant',
        'location': 'PARIS',
        'experience': None,
        'job_type': None,
        'date_posted': None,
        'include_french': False
    }
)

# 打印响应状态码
print(f"Status Code: {response.status_code}")

# 打印响应内容
data = response.json()
print("Response Data Keys:", list(data.keys()))

# 检查数据结构
if 'success' in data:
    print(f"\nSuccess: {data['success']}")
    
if 'jobs' in data:
    print(f"Jobs count: {len(data['jobs'])}")
    if len(data['jobs']) > 0:
        print("\nFirst job keys:", list(data['jobs'][0].keys()))
