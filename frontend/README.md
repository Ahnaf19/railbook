# RailBook Frontend

Single-page application built with **React 18**, **Vite**, and **React Router v6**. Provides a UI for browsing trains, selecting seats on an interactive grid, booking tickets, making payments, and viewing booking history.

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server (port 5173)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## API Proxy

Vite is configured to proxy `/api/*` requests to the backend at `http://localhost:8000`, stripping the `/api` prefix. This means the frontend dev server and backend can run simultaneously without CORS issues during development. See `vite.config.js` for details.

## Pages

| Route | Component | Description |
|---|---|---|
| `/` or `/trains` | `Trains` | Lists all trains with origin/destination |
| `/trains/:trainId/schedules` | `Schedules` | Shows future schedules for a train |
| `/seats/:scheduleId` | `SeatMap` | Interactive seat grid; select a seat and reserve |
| `/booking/:bookingId` | `Booking` | Booking detail: pay, view status, request refund (protected) |
| `/my-tickets` | `MyTickets` | Lists all bookings for the logged-in user (protected) |
| `/login` | `Login` | Login / register form with demo account shortcuts |
| `/demo` | `ConcurrencyDemo` | Fires concurrent booking requests to visualize race conditions |

## Key Components

| Component | Purpose |
|---|---|
| `SeatGrid` | Groups seats by compartment, renders a grid of `SeatCell` components with color-coded availability |
| `SeatCell` | Individual seat button, color-coded: green (available), yellow (reserved), red (booked), blue (selected) |
| `StatusBadge` | Color-coded booking status label (reserved/confirmed/cancelled/refunded) |
| `Layout` | Shared navigation bar with auth-aware links |
| `ProtectedRoute` | Redirects to `/login` if not authenticated |
| `ErrorAlert` | Dismissible error banner |

## Architecture

```
src/
  main.jsx                 # ReactDOM entry point
  App.jsx                  # BrowserRouter + AuthProvider + route definitions
  api/client.js            # Axios instance with JWT interceptor (auto-attaches Bearer token)
  context/AuthContext.jsx  # Auth state: login, register, logout, token storage
  hooks/useAuth.js         # useContext wrapper for AuthContext
  utils/constants.js       # Seat color/label mappings
  pages/                   # Route-level page components
  components/              # Reusable UI components
```

## Demo Accounts

The login page includes quick-fill buttons for demo accounts seeded by the backend:

| Name | Email | Password |
|---|---|---|
| Alice | `alice@example.com` | `password123` |
| Bob | `bob@example.com` | `password123` |

## Dependencies

- **react** / **react-dom** 18.3 -- UI framework
- **react-router-dom** 6.28 -- Client-side routing
- **axios** 1.7 -- HTTP client with interceptors
- **uuid** 10 -- Idempotency key generation
- **vite** 6 + **@vitejs/plugin-react** -- Build tooling
