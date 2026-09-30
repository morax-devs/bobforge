import pytest
from fastapi.testclient import TestClient

from backend.main import app, RunRequest
from backend.model_client import parse_image_data
from backend.workflow import run_workflow


@pytest.fixture
def client():
    return TestClient(app)


def test_parse_image_data_uri():
    data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    mime, b64 = parse_image_data(data_uri)
    assert mime == "image/png"
    assert b64.startswith("iVBORw0")


def test_parse_image_raw_b64():
    raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    mime, b64 = parse_image_data(raw_b64)
    assert mime == "image/png"
    assert b64 == raw_b64


def test_create_run_with_image_and_no_prompt(client):
    payload = {
        "prompt": "",
        "language": "python",
        "images": ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="]
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "id" in data
    assert data["status"] == "queued"

    # Verify run record in API
    run_resp = client.get(f"/api/runs/{data['id']}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert len(run_data.get("images", [])) == 1
    assert "image" in run_data["prompt"].lower()


def test_create_run_without_prompt_and_without_images_fails(client):
    payload = {
        "prompt": "   ",
        "language": "python",
        "images": []
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 422


def test_workflow_threads_images(monkeypatch):
    captured_images = None

    def fake_build_code(prompt, language="python", images=None):
        nonlocal captured_images
        captured_images = images
        return {
            "code": "class Solution:\n    def solve(self): pass",
            "tests": "def test_solve(): pass",
            "challenge": "custom",
            "provider": "offline",
            "explanation": {"intent": "solve", "approach": "From screenshot"},
        }

    monkeypatch.setattr("backend.workflow.build_code", fake_build_code)

    test_imgs = ["data:image/png;base64,abc1234"]
    result = run_workflow("Solve problem from attached image", language="python", images=test_imgs, run_tests=False)
    assert captured_images == test_imgs
    assert result["images"] == test_imgs
