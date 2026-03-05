import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import StatusBadge from "../components/StatusBadge";

export default function MyTickets() {
  const [bookings, setBookings] = useState([]);
  const [error, setError] = useState("");
  const [refunding, setRefunding] = useState(null);

  useEffect(() => {
    api
      .get("/bookings")
      .then(({ data }) => setBookings(data))
      .catch(() => setError("Failed to load bookings"));
  }, []);

  const handleRefund = async (id) => {
    setRefunding(id);
    setError("");
    try {
      const { data } = await api.post(`/bookings/${id}/refund`);
      setBookings((prev) => prev.map((b) => (b.id === id ? data : b)));
    } catch (err) {
      setError(err.response?.data?.detail || "Refund failed");
    } finally {
      setRefunding(null);
    }
  };

  return (
    <div className="tickets-page">
      <h2>My Tickets</h2>
      <ErrorAlert message={error} onDismiss={() => setError("")} />
      {bookings.length === 0 && <p>No bookings yet.</p>}
      <div className="ticket-list">
        {bookings.map((b) => (
          <div key={b.id} className="ticket-card">
            <div className="ticket-card__top">
              <StatusBadge status={b.status} />
              <span className="ticket-card__amount">
                &#2547; {b.total_amount}
              </span>
            </div>
            <div className="ticket-card__id">Booking: {b.id.slice(0, 8)}...</div>
            <div className="ticket-card__actions">
              {b.status === "reserved" && (
                <Link to={`/booking/${b.id}`} className="btn btn--primary btn--sm">
                  Pay
                </Link>
              )}
              {b.status === "confirmed" && (
                <button
                  className="btn btn--sm btn--danger"
                  onClick={() => handleRefund(b.id)}
                  disabled={refunding === b.id}
                >
                  {refunding === b.id ? "Refunding..." : "Refund"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
