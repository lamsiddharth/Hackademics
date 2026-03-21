import http.client
import json

def fetch_jobs(keywords, location):
    # Jooble API Host and API Key
    host = 'jooble.org'
    key = '1d0939bd-d781-471a-85c9-4a75cb8b1882'

    # Establish HTTPS connection
    connection = http.client.HTTPSConnection(host)

    # Request headers
    headers = {"Content-type": "application/json"}

    # JSON query body
    body = json.dumps({
        "keywords": keywords,
        "location": location
    })

    # Send POST request to Jooble API
    connection.request('POST', f'/api/{key}', body, headers)

    # Get the response
    response = connection.getresponse()
    print("Status:", response.status, response.reason)

    # Parse the response data
    data = response.read().decode()
    parsed_data = json.loads(data)

    # Extract array of jobs
    job_list = parsed_data.get("jobs", [])  # Returns an empty list if 'jobs' key is not present

    return job_list

# Example usage
jobs = fetch_jobs("english teacher", "India")
for idx, job in enumerate(jobs, 1):
    print(f"\nJob {idx}:")
    print(json.dumps(job, indent=2))
