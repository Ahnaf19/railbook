# Frontend — React 18 + Vite

## File Map

```
src/
  main.jsx                  → ReactDOM.createRoot, renders <App />
  App.jsx                   → BrowserRouter, AuthProvider, all <Route> definitions
  index.css                 → All styles (~350 lines, BEM-ish class names, CSS variables)
  api/
    client.js               → Axios instance, base URL, JWT interceptor, 401 redirect
  context/
    AuthContext.jsx          → createContext, login/register/logout/fetchUser, localStorage token
  hooks/
    useAuth.js              → useContext(AuthContext) shorthand
  utils/
    constants.js            → API_BASE_URL, color constants
  components/
    Layout.jsx              → Nav bar + <Outlet />, shows user name, logout button
    ProtectedRoute.jsx      → Redirects to /login if not authenticated
    SeatGrid.jsx            → Renders 2 compartments × 25 seats, handles selection callback
    SeatCell.jsx            → Individual seat (color by status: green/red/yellow/blue)
    StatusBadge.jsx         → Booking status pill (reserved/confirmed/cancelled/refunded)
    ErrorAlert.jsx          → Red error banner, auto-dismiss
  pages/
    Login.jsx               → Login + register toggle, demo account quick-login buttons
    Trains.jsx              → GET /trains → train cards with origin/destination
    Schedules.jsx           → GET /trains/:id/schedules → schedule list for selected train
    SeatMap.jsx             → GET /trains/schedules/:id/seats → seat grid + booking trigger
    Booking.jsx             → Booking detail + payment with countdown timer (5-min TTL)
    MyTickets.jsx           → GET /bookings → booking list with refund buttons
    ConcurrencyDemo.jsx     → Split-screen: select train→schedule→seat, "Race!" button
```

## Routes

| Path | Page | Auth | Description |
|------|------|------|-------------|
| `/login` | Login | No | Login/register |
| `/` | Trains | No | Train listing (redirects here) |
| `/trains/:id/schedules` | Schedules | No | Schedule picker |
| `/schedules/:id/seats` | SeatMap | Yes | Seat grid + book |
| `/bookings/:id` | Booking | Yes | Pay/countdown |
| `/my-tickets` | MyTickets | Yes | History + refund |
| `/demo` | ConcurrencyDemo | No | Race condition demo |

## API Client (api/client.js)

- Base URL: `http://localhost:8000` (hardcoded, change for production)
- Request interceptor: injects `Authorization: Bearer {token}` from localStorage
- Response interceptor: on 401, clears token and redirects to `/login`
- All API calls use this Axios instance

## Key Patterns

### Auth Flow
- `AuthContext` stores `user` and `token` in state + localStorage
- On mount, if token exists in localStorage, calls `GET /auth/me` to validate
- `login()` → `POST /auth/login` → stores tokens → fetches user
- `register()` → `POST /auth/register` → stores tokens → fetches user
- `logout()` → clears state + localStorage

### Seat Grid (SeatGrid.jsx)
- Groups seats by compartment (A-B)
- Color coding: green=#22c55e (available), red=#ef4444 (booked), yellow=#eab308 (reserved), blue=#3b82f6 (selected)
- `onSelect` callback fires with seat object when clicking available seat
- Compartment headers show type (AC/Non-AC) and price

### Concurrency Demo (ConcurrencyDemo.jsx)
- Two panels: Alice and Bob
- User selects train → schedule → seat (shared across both panels)
- "Race!" button fires `Promise.allSettled([bookA(), bookB()])` simultaneously
- Results show BOOKED (green) or REJECTED (red) with elapsed time
- Each attempt uses a separate Axios call with different auth tokens

### Booking Page (Booking.jsx)
- Countdown timer shows remaining time before reservation expires
- Timer turns red under 60 seconds
- "Pay Now" button calls `POST /bookings/:id/pay` with a new UUID idempotency key
- On payment success: shows confirmed state
- On payment failure: shows error with retry option

## Development

```bash
npm install          # Install dependencies
npm run dev          # Dev server at http://localhost:5173 (proxied to :8000 for API)
npm run build        # Production build → dist/
npm run preview      # Preview production build
```

## When Modifying

- **New page**: Add component in `pages/`, add `<Route>` in `App.jsx`, add nav link in `Layout.jsx` if needed
- **New API call**: Use the `api/client.js` Axios instance (already handles auth)
- **Protected page**: Wrap route with `<ProtectedRoute>` in `App.jsx`
- **Styles**: All in `index.css` (no CSS modules, no Tailwind)
- **New component**: Add in `components/`, keep stateless where possible

## Gotchas

- No TypeScript — plain JSX only
- No state management library — just React Context
- UUID generation uses `uuid` npm package (for idempotency keys)
- `vite.config.js` has proxy config for `/api` → not currently used (direct URL in client.js)
- Nginx config (`nginx.conf`) handles SPA routing in Docker production build
