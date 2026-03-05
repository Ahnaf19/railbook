import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="app">
      <nav className="nav">
        <div className="nav__left">
          <Link to="/" className="nav__brand">
            RailBook
          </Link>
          <Link to="/trains">Trains</Link>
          {user && <Link to="/my-tickets">My Tickets</Link>}
          <Link to="/demo">Race Demo</Link>
        </div>
        <div className="nav__right">
          {user ? (
            <>
              <span className="nav__user">{user.full_name}</span>
              <button onClick={handleLogout} className="btn btn--sm">
                Logout
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn--sm btn--primary">
              Login
            </Link>
          )}
        </div>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
