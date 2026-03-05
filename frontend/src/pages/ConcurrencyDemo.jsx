import { useEffect, useState } from "react";
import api from "../api/client";
import ErrorAlert from "../components/ErrorAlert";
import SeatGrid from "../components/SeatGrid";

export default function ConcurrencyDemo() {
  const [trains, setTrains] = useState([]);
  const [selectedTrain, setSelectedTrain] = useState(null);
  const [schedules, setSchedules] = useState([]);
  const [selectedSchedule, setSelectedSchedule] = useState(null);
  const [seatData, setSeatData] = useState(null);
  const [selectedSeat, setSelectedSeat] = useState(null);
  const [racing, setRacing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/trains").then(({ data }) => setTrains(data));
  }, []);

  useEffect(() => {
    if (!selectedTrain) return;
    api
      .get(`/trains/${selectedTrain}/schedules`)
      .then(({ data }) => setSchedules(data));
  }, [selectedTrain]);

  useEffect(() => {
    if (!selectedSchedule) return;
    api
      .get(`/trains/schedules/${selectedSchedule}/seats`)
      .then(({ data }) => setSeatData(data));
  }, [selectedSchedule]);

  const handleRace = async () => {
    if (!selectedSchedule || !selectedSeat) return;
    setRacing(true);
    setResult(null);
    setError("");
    try {
      const { data } = await api.post("/demo/race-condition", {
        schedule_id: selectedSchedule,
        seat_id: selectedSeat,
      });
      setResult(data);
      // Refresh seat data
      const { data: fresh } = await api.get(
        `/trains/schedules/${selectedSchedule}/seats`
      );
      setSeatData(fresh);
      setSelectedSeat(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Race failed");
    } finally {
      setRacing(false);
    }
  };

  return (
    <div className="demo-page">
      <h2>Concurrency Race Demo</h2>
      <p className="demo-page__desc">
        Two users (Alice &amp; Bob) try to book the <strong>same seat</strong>{" "}
        at the exact same time. PostgreSQL row-level locking ensures only one
        succeeds.
      </p>
      <ErrorAlert message={error} onDismiss={() => setError("")} />

      <div className="demo-page__controls">
        <div className="form-group">
          <label>Train</label>
          <select
            value={selectedTrain || ""}
            onChange={(e) => {
              setSelectedTrain(e.target.value);
              setSelectedSchedule(null);
              setSeatData(null);
              setSelectedSeat(null);
              setResult(null);
            }}
          >
            <option value="">Select a train</option>
            {trains.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.train_number})
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Schedule</label>
          <select
            value={selectedSchedule || ""}
            onChange={(e) => {
              setSelectedSchedule(e.target.value);
              setSelectedSeat(null);
              setResult(null);
            }}
            disabled={!selectedTrain}
          >
            <option value="">Select a schedule</option>
            {schedules.map((s) => (
              <option key={s.id} value={s.id}>
                {new Date(s.departure_time).toLocaleString()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {seatData && (
        <>
          <h3>Pick an available seat for the race:</h3>
          <SeatGrid
            seats={seatData.seats}
            selectedSeatId={selectedSeat}
            onSeatClick={(seat) => setSelectedSeat(seat.id)}
            disabled={racing}
          />
        </>
      )}

      {selectedSeat && (
        <div className="demo-page__race-btn">
          <button
            className="btn btn--primary btn--lg"
            onClick={handleRace}
            disabled={racing}
          >
            {racing ? "Racing..." : "Race! (Alice vs Bob)"}
          </button>
        </div>
      )}

      {result && (
        <div className="demo-page__results">
          <h3>Race Results</h3>
          <div className="race-panels">
            <RacePanel
              label="Alice (User A)"
              attempt={result.attempt_a}
              isWinner={result.winner === "A"}
            />
            <div className="race-panels__vs">VS</div>
            <RacePanel
              label="Bob (User B)"
              attempt={result.attempt_b}
              isWinner={result.winner === "B"}
            />
          </div>
          {result.winner && (
            <p className="race-winner">
              Winner: <strong>{result.winner === "A" ? "Alice" : "Bob"}</strong>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function RacePanel({ label, attempt, isWinner }) {
  const success = attempt.status_code === 201;
  return (
    <div className={`race-panel ${isWinner ? "race-panel--winner" : ""}`}>
      <h4>{label}</h4>
      <div
        className={`race-panel__status ${success ? "race-panel__status--success" : "race-panel__status--fail"}`}
      >
        {success ? "BOOKED" : "REJECTED"}
      </div>
      <div className="race-panel__detail">{attempt.detail}</div>
      <div className="race-panel__time">{attempt.elapsed_ms}ms</div>
    </div>
  );
}
