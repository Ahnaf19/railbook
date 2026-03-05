import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import StatusBadge from "../components/StatusBadge";

export default function Booking() {
  const { bookingId } = useParams();
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(false);
  const [countdown, setCountdown] = useState(null);

  useEffect(() => {
    api
      .get(`/bookings/${bookingId}`)
      .then(({ data }) => setBooking(data))
      .catch(() => setError("Failed to load booking"));
  }, [bookingId]);

  // Countdown timer for reservation expiry
  useEffect(() => {
    if (!booking?.expires_at || booking.status !== "reserved") return;
    const update = () => {
      const remaining = Math.max(
        0,
        Math.floor((new Date(booking.expires_at) - Date.now()) / 1000)
      );
      setCountdown(remaining);
      if (remaining <= 0) {
        setBooking((b) => ({ ...b, status: "cancelled" }));
      }
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [booking?.expires_at, booking?.status]);

  const handlePay = async () => {
    setPaying(true);
    setError("");
    try {
      const { data } = await api.post(`/bookings/${bookingId}/pay`, {
        idempotency_key: uuidv4(),
      });
      setBooking(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Payment failed");
    } finally {
      setPaying(false);
    }
  };

  if (!booking) return <div className="loading">Loading...</div>;

  const minutes = countdown !== null ? Math.floor(countdown / 60) : 0;
  const seconds = countdown !== null ? countdown % 60 : 0;

  return (
    <div className="booking-page">
      <h2>Booking Details</h2>
      <ErrorAlert message={error} onDismiss={() => setError("")} />
      <div className="booking-card">
        <div className="booking-card__row">
          <span className="label">Status</span>
          <StatusBadge status={booking.status} />
        </div>
        <div className="booking-card__row">
          <span className="label">Amount</span>
          <strong>&#2547; {booking.total_amount}</strong>
        </div>
        {booking.status === "reserved" && countdown !== null && (
          <div className="booking-card__row">
            <span className="label">Expires in</span>
            <strong className={countdown < 60 ? "text-danger" : ""}>
              {minutes}:{seconds.toString().padStart(2, "0")}
            </strong>
          </div>
        )}
        {booking.status === "reserved" && countdown > 0 && (
          <button
            className="btn btn--primary btn--full"
            onClick={handlePay}
            disabled={paying}
          >
            {paying ? "Processing Payment..." : "Pay Now"}
          </button>
        )}
        {booking.status === "confirmed" && (
          <div className="booking-card__success">Payment confirmed!</div>
        )}
        {booking.status === "cancelled" && (
          <div className="booking-card__cancelled">
            {countdown === 0
              ? "Reservation expired."
              : "Payment failed. Booking cancelled."}
          </div>
        )}
      </div>
    </div>
  );
}
