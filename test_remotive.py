import requests
res = requests.get('https://remotive.io/api/remote-jobs?search=data-scientist')
data = res.json()
for j in data.get('jobs', [])[:1]:
    print(f"Title: {j.get('title')}, Company: {j.get('company_name')}, Loc: {j.get('candidate_required_location')}, URL: {j.get('url')}")
