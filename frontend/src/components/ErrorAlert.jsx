export default function ErrorAlert({ message, onDismiss }) {
  if (!message) return null;
  return (
    <div className="alert alert--error">
      <span>{message}</span>
      {onDismiss && (
        <button className="alert__close" onClick={onDismiss}>
          &times;
        </button>
      )}
    </div>
  );
}
