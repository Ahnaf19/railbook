import { SEAT_COLORS, SEAT_LABELS } from "../utils/constants";

export default function SeatCell({ seat, selected, onClick, disabled }) {
  const status = selected ? "selected" : seat.booking_status || "available";
  const color = SEAT_COLORS[status] || SEAT_COLORS.available;
  const isClickable = status === "available" || selected;

  return (
    <button
      className={`seat seat--${status}`}
      style={{ backgroundColor: color }}
      title={`Seat ${seat.seat_number} (${seat.position}) - ${SEAT_LABELS[status] || status}`}
      onClick={() => isClickable && onClick?.(seat)}
      disabled={disabled || !isClickable}
    >
      {seat.seat_number}
    </button>
  );
}
