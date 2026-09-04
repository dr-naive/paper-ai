"""Smoke-test deployed project notes/evidence APIs and clean created records."""
import json
import os
import urllib.request

BASE = os.getenv("PAPERAI_API_URL", "http://127.0.0.1:8000")

def request(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response) if response.status != 204 else None

token = request("POST", "/api/auth/login", {"username": "admin", "password": os.environ["DEFAULT_ADMIN_PASSWORD"]})["access_token"]
projects = request("GET", "/api/v1/projects", token=token)["items"]
assert projects, "需要至少一个项目"
project_id = projects[0]["id"]
papers = []
for candidate in projects:
    candidate_papers = request("GET", f"/api/v1/projects/{candidate['id']}/papers", token=token)["items"]
    if candidate_papers:
        project_id, papers = candidate["id"], candidate_papers
        break
note = request("POST", f"/api/v1/projects/{project_id}/notes", {"type": "finding", "title": "Runtime verification", "content": "Structured note verification"}, token)
notes = request("GET", f"/api/v1/projects/{project_id}/notes", token=token)["items"]
assert any(item["id"] == note["id"] for item in notes)
evidence_id = None
if papers:
    evidence = request("POST", f"/api/v1/projects/{project_id}/evidence", {"paper_id": papers[0]["paper_id"], "evidence_type": "quote", "snippet": "Structured evidence verification", "normalized_claim": "Evidence API persists source metadata"}, token)
    evidence_id = evidence["id"]
    rows = request("GET", f"/api/v1/projects/{project_id}/evidence", token=token)["items"]
    assert any(item["id"] == evidence_id for item in rows)
    request("DELETE", f"/api/v1/projects/{project_id}/evidence/{evidence_id}", token=token)
request("DELETE", f"/api/v1/projects/{project_id}/notes/{note['id']}", token=token)
print(json.dumps({"notes": "verified", "evidence": "verified" if evidence_id else "skipped:no_project_paper"}))
