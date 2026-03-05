import asyncio
import random
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4


@dataclass
class PaymentResult:
    status: str
    gateway_ref: str | None = None
    failure_reason: str | None = None


@dataclass
class RefundResult:
    status: str
    refund_ref: str | None = None


class MockPaymentGateway:
    def __init__(self, failure_rate: float = 0.0, latency_ms: int = 500):
        self.failure_rate = failure_rate
        self.latency_ms = latency_ms
        self._processed: dict[str, PaymentResult] = {}

    async def charge(self, amount: Decimal, idempotency_key: str) -> PaymentResult:
        await asyncio.sleep(self.latency_ms / 1000)
        if idempotency_key in self._processed:
            return self._processed[idempotency_key]
        if random.random() < self.failure_rate:
            result = PaymentResult(
                status="failed", failure_reason="Card declined (simulated)"
            )
        else:
            result = PaymentResult(status="success", gateway_ref=f"MOCK-{uuid4().hex[:8]}")
        self._processed[idempotency_key] = result
        return result

    async def refund(self, gateway_ref: str) -> RefundResult:
        await asyncio.sleep(self.latency_ms / 1000)
        return RefundResult(status="success", refund_ref=f"REFUND-{uuid4().hex[:8]}")


# Module-level singleton
payment_gateway = MockPaymentGateway()
