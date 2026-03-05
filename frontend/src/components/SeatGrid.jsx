import SeatCell from "./SeatCell";

export default function SeatGrid({
  seats = [],
  selectedSeatId,
  onSeatClick,
  disabled,
}) {
  // Group seats by compartment
  const compartments = {};
  for (const seat of seats) {
    const comp = seat.compartment_name;
    if (!compartments[comp]) compartments[comp] = [];
    compartments[comp].push(seat);
  }

  return (
    <div className="seat-grid">
      {Object.entries(compartments).map(([compName, compSeats]) => (
        <div key={compName} className="seat-grid__compartment">
          <h4 className="seat-grid__comp-name">
            {compName} ({compSeats[0]?.comp_type === "ac" ? "AC" : "Non-AC"})
          </h4>
          <div className="seat-grid__seats">
            {compSeats.map((seat) => (
              <SeatCell
                key={seat.id}
                seat={seat}
                selected={seat.id === selectedSeatId}
                onClick={onSeatClick}
                disabled={disabled}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
