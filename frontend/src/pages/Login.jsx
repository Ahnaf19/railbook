import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ErrorAlert from "../components/ErrorAlert";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password, fullName, phone);
      } else {
        await login(email, password);
      }
      navigate("/trains");
    } catch (err) {
      setError(
        err.response?.data?.detail || "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>{isRegister ? "Create Account" : "Sign In"}</h2>
        <ErrorAlert message={error} onDismiss={() => setError("")} />
        <form onSubmit={handleSubmit}>
          {isRegister && (
            <>
              <div className="form-group">
                <label>Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label>Phone (optional)</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
            </>
          )}
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <button type="submit" className="btn btn--primary btn--full" disabled={loading}>
            {loading ? "Please wait..." : isRegister ? "Register" : "Sign In"}
          </button>
        </form>
        <p className="auth-card__toggle">
          {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
          <button className="link-btn" onClick={() => setIsRegister(!isRegister)}>
            {isRegister ? "Sign In" : "Register"}
          </button>
        </p>
        <div className="auth-card__demo">
          <p>Demo accounts:</p>
          <button
            className="link-btn"
            onClick={() => {
              setEmail("alice@example.com");
              setPassword("password123");
              setIsRegister(false);
            }}
          >
            Alice
          </button>{" "}
          |{" "}
          <button
            className="link-btn"
            onClick={() => {
              setEmail("bob@example.com");
              setPassword("password123");
              setIsRegister(false);
            }}
          >
            Bob
          </button>
        </div>
      </div>
    </div>
  );
}
