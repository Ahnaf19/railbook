import uuid

import requests

from config import BASE_URL


def register_user(session=None):
    """Register a new user and return (email, token)."""
    email = f"loadtest-{uuid.uuid4().hex[:8]}@test.com"
    password = "loadtest123"
    s = session or requests
    resp = s.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "full_name": "Load Tester"},
    )
    if resp.status_code == 201:
        return email, resp.json()["access_token"]
    # Try login if user already exists
    resp = s.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    return email, resp.json()["access_token"]


def get_auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def get_available_seat(client, schedule_id, headers):
    """Find an available seat for a schedule."""
    resp = client.get(f"/trains/schedules/{schedule_id}/seats", headers=headers)
    if resp.status_code != 200:
        return None
    seats = resp.json().get("seats", [])
    for seat in seats:
        if not seat.get("booking_status"):
            return seat["id"]
    return None
