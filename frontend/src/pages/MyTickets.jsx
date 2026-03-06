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

  const formatDate = (iso) => {
    if (!iso) return "";
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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
            {b.train_name && (
              <div className="ticket-card__train">
                <strong>{b.train_name}</strong>
                <span className="ticket-card__route">
                  {b.origin} &rarr; {b.destination}
                </span>
              </div>
            )}
            <div className="ticket-card__details">
              {b.departure_time && (
                <span>{formatDate(b.departure_time)}</span>
              )}
              {b.compartment_name && (
                <span>
                  {b.compartment_name} ({b.comp_type === "ac" ? "AC" : "Non-AC"}) &middot; Seat {b.seat_number}
                </span>
              )}
            </div>
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
