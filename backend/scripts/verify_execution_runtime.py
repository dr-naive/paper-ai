"""Smoke-test the deployed Execution Runtime using configured admin credentials."""
import json
import os
import time
import urllib.request


BASE = os.getenv("PAPERAI_API_URL", "http://127.0.0.1:8000")


def request(method: str, path: str, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


login = request("POST", "/api/auth/login", {
    "username": "admin", "password": os.environ["DEFAULT_ADMIN_PASSWORD"],
})
token = login["access_token"]
projects = request("GET", "/api/v1/projects", token=token)
items = projects.get("items", projects if isinstance(projects, list) else [])
if not items:
    project = request("POST", "/api/v1/projects", {
        "title": "Runtime verification", "research_topic": "Agent runtime verification",
    }, token)
else:
    project = items[0]

execution = request("POST", f"/api/v1/projects/{project['id']}/executions", {
    "agent_type": "mock_agent", "goal": "Verify durable runtime",
}, token)
for _ in range(30):
    execution = request("GET", f"/api/v1/executions/{execution['id']}", token=token)
    if execution["status"] in {"completed", "failed", "cancelled"}:
        break
    time.sleep(0.2)
events = request("GET", f"/api/v1/executions/{execution['id']}/events", token=token)["items"]
assert execution["status"] == "completed", execution
assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
assert events[-1]["type"] == "execution_completed"
with urllib.request.urlopen(urllib.request.Request(
    BASE + f"/api/v1/executions/{execution['id']}/stream?after=2",
    headers={"Authorization": f"Bearer {token}"}), timeout=10) as response:
    replay = response.read().decode()
assert "execution_completed" in replay and "id: 3" in replay

cancelled = request("POST", f"/api/v1/projects/{project['id']}/executions", {
    "agent_type": "mock_agent", "goal": "Verify cancellation",
}, token)
request("POST", f"/api/v1/executions/{cancelled['id']}/cancel", token=token)
for _ in range(30):
    cancelled = request("GET", f"/api/v1/executions/{cancelled['id']}", token=token)
    if cancelled["status"] in {"completed", "failed", "cancelled"}:
        break
    time.sleep(0.2)
assert cancelled["status"] == "cancelled", cancelled
print(json.dumps({"execution_id": execution["id"], "status": execution["status"],
                  "event_count": len(events), "sse_replay": True,
                  "cancelled_execution_id": cancelled["id"], "cancel_status": cancelled["status"]}))
