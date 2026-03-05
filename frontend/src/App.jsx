import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import Booking from "./pages/Booking";
import ConcurrencyDemo from "./pages/ConcurrencyDemo";
import Login from "./pages/Login";
import MyTickets from "./pages/MyTickets";
import Schedules from "./pages/Schedules";
import SeatMap from "./pages/SeatMap";
import Trains from "./pages/Trains";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Trains />} />
            <Route path="/login" element={<Login />} />
            <Route path="/trains" element={<Trains />} />
            <Route path="/trains/:trainId/schedules" element={<Schedules />} />
            <Route path="/seats/:scheduleId" element={<SeatMap />} />
            <Route
              path="/booking/:bookingId"
              element={
                <ProtectedRoute>
                  <Booking />
                </ProtectedRoute>
              }
            />
            <Route
              path="/my-tickets"
              element={
                <ProtectedRoute>
                  <MyTickets />
                </ProtectedRoute>
              }
            />
            <Route path="/demo" element={<ConcurrencyDemo />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
