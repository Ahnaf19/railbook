import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { v4 as uuidv4 } from "uuid";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import SeatGrid from "../components/SeatGrid";
import { useAuth } from "../hooks/useAuth";

export default function SeatMap() {
  const { scheduleId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [seatData, setSeatData] = useState(null);
  const [selectedSeat, setSelectedSeat] = useState(null);
  const [error, setError] = useState("");
  const [booking, setBooking] = useState(false);

  useEffect(() => {
    api
      .get(`/trains/schedules/${scheduleId}/seats`)
      .then(({ data }) => setSeatData(data))
      .catch(() => setError("Failed to load seats"));
  }, [scheduleId]);

  const handleBook = async () => {
    if (!user) {
      navigate("/login");
      return;
    }
    if (!selectedSeat) return;
    setBooking(true);
    setError("");
    try {
      const { data } = await api.post("/bookings", {
        schedule_id: scheduleId,
        seat_id: selectedSeat,
        idempotency_key: uuidv4(),
      });
      navigate(`/booking/${data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Booking failed");
    } finally {
      setBooking(false);
    }
  };

  if (!seatData) return <div className="loading">Loading seats...</div>;

  return (
    <div className="seatmap-page">
      <div className="seatmap-page__header">
        <h2>Select Your Seat</h2>
        <div className="seatmap-page__stats">
          <span>
            Available: {seatData.available_seats}/{seatData.total_seats}
          </span>
        </div>
      </div>
      <ErrorAlert message={error} onDismiss={() => setError("")} />
      <div className="seatmap-page__legend">
        <span className="legend-item">
          <span className="legend-color" style={{ background: "#22c55e" }} />
          Available
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ background: "#eab308" }} />
          Reserved
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ background: "#ef4444" }} />
          Booked
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ background: "#3b82f6" }} />
          Selected
        </span>
      </div>
      <SeatGrid
        seats={seatData.seats}
        selectedSeatId={selectedSeat}
        onSeatClick={(seat) => setSelectedSeat(seat.id)}
        disabled={booking}
      />
      {selectedSeat && (
        <div className="seatmap-page__action">
          <button
            className="btn btn--primary btn--lg"
            onClick={handleBook}
            disabled={booking}
          >
            {booking ? "Booking..." : "Book This Seat"}
          </button>
        </div>
      )}
    </div>
  );
}
