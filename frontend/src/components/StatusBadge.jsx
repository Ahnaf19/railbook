const STATUS_STYLES = {
  reserved: { bg: "#fef9c3", color: "#854d0e", label: "Reserved" },
  confirmed: { bg: "#dcfce7", color: "#166534", label: "Confirmed" },
  cancelled: { bg: "#fee2e2", color: "#991b1b", label: "Cancelled" },
  refunded: { bg: "#dbeafe", color: "#1e40af", label: "Refunded" },
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || {
    bg: "#f3f4f6",
    color: "#374151",
    label: status,
  };
  return (
    <span
      className="badge"
      style={{ backgroundColor: style.bg, color: style.color }}
    >
      {style.label}
    </span>
  );
}
