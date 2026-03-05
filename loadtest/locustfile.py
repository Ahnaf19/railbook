import uuid

from locust import HttpUser, between, constant, task

from helpers import get_auth_headers, get_available_seat, register_user


class TicketBuyer(HttpUser):
    """Normal user: browse trains, view seats, occasionally book."""

    weight = 8
    wait_time = between(1, 3)

    def on_start(self):
        _, self.token = register_user()
        self.headers = get_auth_headers(self.token)
        self.trains = []
        self.schedules = []

    @task(5)
    def browse_trains(self):
        resp = self.client.get("/trains", headers=self.headers)
        if resp.status_code == 200:
            self.trains = resp.json()

    @task(3)
    def view_seats(self):
        if not self.trains:
            return
        train = self.trains[0]
        resp = self.client.get(
            f"/trains/{train['id']}/schedules", headers=self.headers
        )
        if resp.status_code == 200:
            self.schedules = resp.json()
        if self.schedules:
            schedule = self.schedules[0]
            self.client.get(
                f"/trains/schedules/{schedule['id']}/seats",
                headers=self.headers,
                name="/trains/schedules/[id]/seats",
            )

    @task(1)
    def book_and_pay(self):
        if not self.schedules:
            return
        schedule = self.schedules[0]
        seat_id = get_available_seat(
            self.client, schedule["id"], self.headers
        )
        if not seat_id:
            return

        # Book
        resp = self.client.post(
            "/bookings",
            json={
                "schedule_id": schedule["id"],
                "seat_id": seat_id,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=self.headers,
        )
        if resp.status_code not in (201, 409):
            return

        if resp.status_code == 201:
            booking_id = resp.json()["id"]
            # Pay
            self.client.post(
                f"/bookings/{booking_id}/pay",
                json={"idempotency_key": str(uuid.uuid4())},
                headers=self.headers,
                name="/bookings/[id]/pay",
            )


class SeatSniper(HttpUser):
    """Aggressive user trying to grab a specific seat rapidly."""

    weight = 1
    wait_time = constant(0)

    def on_start(self):
        _, self.token = register_user()
        self.headers = get_auth_headers(self.token)
        # Get first available schedule
        resp = self.client.get("/trains", headers=self.headers)
        trains = resp.json() if resp.status_code == 200 else []
        self.target_schedule = None
        if trains:
            resp = self.client.get(
                f"/trains/{trains[0]['id']}/schedules", headers=self.headers
            )
            schedules = resp.json() if resp.status_code == 200 else []
            if schedules:
                self.target_schedule = schedules[0]["id"]

    @task
    def snipe_seat(self):
        if not self.target_schedule:
            return
        seat_id = get_available_seat(
            self.client, self.target_schedule, self.headers
        )
        if not seat_id:
            return
        self.client.post(
            "/bookings",
            json={
                "schedule_id": self.target_schedule,
                "seat_id": seat_id,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=self.headers,
        )


class MixedLoad(HttpUser):
    """Rapid mixed traffic testing various endpoints."""

    weight = 1
    wait_time = between(0.5, 1)

    def on_start(self):
        _, self.token = register_user()
        self.headers = get_auth_headers(self.token)

    @task(3)
    def browse(self):
        self.client.get("/trains", headers=self.headers)

    @task(2)
    def health(self):
        self.client.get("/health")

    @task(1)
    def my_bookings(self):
        self.client.get("/bookings", headers=self.headers)

    @task(1)
    def demo_config(self):
        self.client.get("/demo/config")
