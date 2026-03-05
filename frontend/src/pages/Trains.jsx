import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";

export default function Trains() {
  const [trains, setTrains] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/trains")
      .then(({ data }) => setTrains(data))
      .catch(() => setError("Failed to load trains"));
  }, []);

  return (
    <div className="trains-page">
      <h2>Available Trains</h2>
      <ErrorAlert message={error} onDismiss={() => setError("")} />
      <div className="train-list">
        {trains.map((train) => (
          <div key={train.id} className="train-card">
            <div className="train-card__header">
              <h3>{train.name}</h3>
              <span className="train-card__number">{train.train_number}</span>
            </div>
            <p className="train-card__route">
              {train.origin} &rarr; {train.destination}
            </p>
            <Link to={`/trains/${train.id}/schedules`} className="btn btn--primary">
              View Schedules
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
