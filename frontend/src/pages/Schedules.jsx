import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";

export default function Schedules() {
  const { trainId } = useParams();
  const [schedules, setSchedules] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/trains/${trainId}/schedules`)
      .then(({ data }) => setSchedules(data))
      .catch(() => setError("Failed to load schedules"));
  }, [trainId]);

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="schedules-page">
      <h2>Schedules</h2>
      <ErrorAlert message={error} onDismiss={() => setError("")} />
      <div className="schedule-list">
        {schedules.map((s) => (
          <div key={s.id} className="schedule-card">
            <div className="schedule-card__times">
              <div>
                <span className="label">Departure</span>
                <strong>{formatDate(s.departure_time)}</strong>
              </div>
              <div>
                <span className="label">Arrival</span>
                <strong>{formatDate(s.arrival_time)}</strong>
              </div>
            </div>
            <Link to={`/seats/${s.id}`} className="btn btn--primary">
              Select Seat
            </Link>
          </div>
        ))}
        {schedules.length === 0 && !error && <p>No upcoming schedules.</p>}
      </div>
    </div>
  );
}
