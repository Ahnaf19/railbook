# RailBook User Guide

RailBook is a train ticket booking application for Bangladesh Railways. This guide walks you through every feature of the application, from creating an account to managing your tickets.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Browsing Trains and Schedules](#browsing-trains-and-schedules)
3. [Viewing the Seat Map](#viewing-the-seat-map)
4. [Making a Booking](#making-a-booking)
5. [Managing Tickets](#managing-tickets)
6. [Understanding Pricing](#understanding-pricing)
7. [Concurrency Demo](#concurrency-demo)
8. [Demo Accounts](#demo-accounts)

---

## Getting Started

### Accessing the Application

The RailBook frontend runs on port **5173** in development mode. Open your browser and navigate to:

```
http://localhost:5173
```

The home page (`/` or `/trains`) displays the list of available trains. You can browse trains and schedules without an account, but you must sign in to book seats.

### Creating an Account

1. Click **Sign In** in the navigation bar, or try to book a seat (you will be redirected to the login page automatically).
2. On the login page, click the **Register** link at the bottom.
3. Fill in the registration form:
   - **Full Name** (required)
   - **Phone** (optional)
   - **Email** (required)
   - **Password** (required, minimum 6 characters)
4. Click **Register**. You will be signed in automatically and redirected to the trains listing.

If you already have an account, use the **Sign In** form with your email and password.

### Quick Start with Demo Accounts

The login page provides one-click buttons to auto-fill credentials for the demo accounts (Alice and Bob). Click either name to populate the email and password fields, then click **Sign In**. See the [Demo Accounts](#demo-accounts) section for full details.

---

## Browsing Trains and Schedules

### Train Listing

The trains page (`/trains`) shows all available trains as cards. Each card displays:

- **Train name** (e.g., Subarna Express, Ekota Express, Mohanagar Provati)
- **Train number** (e.g., SE-701, EE-501, MP-301)
- **Route** showing origin and destination (e.g., Dhaka to Chittagong)
- A **View Schedules** button

The seed data includes three trains:

| Train             | Number | Route                |
|-------------------|--------|----------------------|
| Subarna Express   | SE-701 | Dhaka to Chittagong  |
| Ekota Express     | EE-501 | Dhaka to Rajshahi    |
| Mohanagar Provati | MP-301 | Dhaka to Sylhet      |

### Viewing Schedules

Click **View Schedules** on a train card to navigate to `/trains/:trainId/schedules`. This page lists upcoming departures for the next 7 days, each showing:

- **Departure time** (formatted as weekday, date, and time)
- **Arrival time** (calculated from departure plus journey duration)
- A **Select Seat** button

Departure times vary by train:

| Train             | Departure | Journey Duration |
|-------------------|-----------|------------------|
| Subarna Express   | 7:00 AM   | 5 hours          |
| Ekota Express     | 10:30 AM  | 6 hours          |
| Mohanagar Provati | 6:30 AM   | 7 hours          |

If no upcoming schedules exist, a message reads "No upcoming schedules."

---

## Viewing the Seat Map

Click **Select Seat** on any schedule card to open the seat map at `/seats/:scheduleId`. This page displays:

### Header Information

- The title "Select Your Seat"
- An availability counter showing available seats vs total seats (e.g., "Available: 48/50")

### Color Legend

The seat map uses a four-color system to indicate seat status:

| Color                              | Status      | Meaning                                                   |
|------------------------------------|-------------|-----------------------------------------------------------|
| **Green** (`#22c55e`)              | Available   | The seat is free and can be selected for booking           |
| **Yellow** (`#eab308`)             | Reserved    | Another user has reserved this seat and is completing payment |
| **Red** (`#ef4444`)                | Booked      | The seat has been paid for and is confirmed                |
| **Blue** (`#3b82f6`)              | Selected    | You have selected this seat (click to deselect)           |

### Compartment Layout

Seats are organized by compartment. Each train has 2 compartments (A and B):

- **Compartment A** is **AC** (air-conditioned) -- 1500 BDT per seat
- **Compartment B** is **Non-AC** -- 800 BDT per seat

Each compartment has 25 seats, giving a total of 50 seats per train. Seat positions alternate between **window** and **corridor** based on seat number (digits ending in 1, 4, 5, or 8 are window seats).

The compartment name and type (AC or Non-AC) are displayed above each seat group.

### Selecting a Seat

- Click any **green** (available) seat to select it. It turns **blue**.
- Click the blue seat again to deselect it.
- Only one seat can be selected at a time.
- Yellow (reserved) and red (booked) seats cannot be clicked.

Once a seat is selected, a **Book This Seat** button appears at the bottom of the page.

---

## Making a Booking

The booking flow has three stages: seat selection, reservation, and payment.

### Step 1: Select and Reserve

1. On the seat map, click an available (green) seat to select it.
2. Click the **Book This Seat** button.
3. If you are not logged in, you will be redirected to the login page. After signing in, return to the seat map and try again.
4. The system sends a booking request to the server with:
   - The schedule ID
   - The seat ID
   - A unique idempotency key (UUID v4, generated automatically) to prevent duplicate bookings
5. On the server side, the seat is locked using `SELECT FOR UPDATE` to prevent race conditions. If another user has already reserved or confirmed this seat, you will see the error "Seat already booked for this schedule."
6. The system also checks for overlapping journeys -- you cannot hold two active bookings whose journey times overlap.
7. If successful, a booking is created with status **"reserved"** and you are redirected to the booking details page at `/booking/:bookingId`.

### Step 2: The 5-Minute Countdown

Once on the booking details page, you will see:

- **Status**: "reserved" (shown as a badge)
- **Amount**: The ticket price in BDT (with the Bangladeshi Taka symbol)
- **Expires in**: A live countdown timer starting from 5 minutes (e.g., "4:59", "4:58", ...)

The countdown timer ticks every second. When less than 60 seconds remain, the timer text turns red to create urgency.

If the timer reaches 0:00:
- The booking status changes to "cancelled" on the client side
- The message "Reservation expired." is displayed
- The **Pay Now** button disappears
- On the server, a background cleanup task runs every 60 seconds to cancel any reservations past their expiry time, freeing the seat for other users

### Step 3: Pay

1. While the countdown is still active, click the **Pay Now** button.
2. The button changes to "Processing Payment..." and is disabled to prevent double clicks.
3. A new idempotency key is generated to ensure payment safety.
4. The server processes the payment through a mock payment gateway:
   - On success: the booking status changes to **"confirmed"**, and you see "Payment confirmed!"
   - On failure: the booking is cancelled, and an error message is displayed.
5. Every state transition is recorded in the audit trail.

---

## Managing Tickets

### Viewing Your Bookings

Navigate to **My Tickets** (`/my-tickets`) from the navigation bar. This page requires authentication.

Your bookings are listed as cards, each showing:

- **Status badge** (reserved, confirmed, cancelled, or refunded)
- **Amount** in BDT
- **Booking ID** (first 8 characters shown)
- **Action buttons** depending on status:
  - **Reserved** bookings show a **Pay** link that takes you to the booking details page to complete payment
  - **Confirmed** bookings show a **Refund** button

If you have no bookings, the page displays "No bookings yet."

### Requesting a Refund

1. On the My Tickets page, find a **confirmed** booking.
2. Click the **Refund** button.
3. The button changes to "Refunding..." while processing.
4. The server checks the refund eligibility:
   - The booking must be in **"confirmed"** status
   - The train departure must be **more than 1 hour away**. If the departure is within 1 hour, the refund is rejected with the error "Cannot refund within 1 hour of departure."
5. If eligible, the payment is reversed through the mock gateway, the booking status changes to **"refunded"**, and the seat becomes available again for other users.

### The 1-Hour Cutoff Rule

Refunds are only permitted when the scheduled departure time is at least 1 hour in the future. This rule is enforced server-side. Once you are within the 1-hour window before departure, your confirmed ticket is final and cannot be refunded.

---

## Understanding Pricing

Ticket prices are determined by the compartment type:

| Compartment Type | Compartments | Price per Seat |
|------------------|--------------|----------------|
| AC               | A            | 1,500 BDT      |
| Non-AC           | B            | 800 BDT        |

Prices are fixed and calculated automatically when a booking is created. The amount is displayed on the booking details page and the My Tickets list. The currency is Bangladeshi Taka (BDT), shown with the Taka symbol.

---

## Concurrency Demo

The concurrency demo page (`/demo`) demonstrates how RailBook handles race conditions when two users try to book the same seat at the same instant. It uses PostgreSQL row-level locking (`SELECT FOR UPDATE`) to guarantee that only one booking succeeds.

### How to Use the Demo

1. Navigate to `/demo` in your browser (no login required to access the page).
2. **Select a Train** from the dropdown. The available trains are loaded from the server.
3. **Select a Schedule** from the second dropdown (populated after choosing a train).
4. The seat map loads, showing all seats with their current status.
5. **Click an available (green) seat** to select it for the race.
6. Click the **Race! (Alice vs Bob)** button.

### What Happens During the Race

The server receives the race request and simultaneously attempts to book the selected seat for both Alice and Bob at the same time. Both requests hit the database concurrently, but PostgreSQL's `SELECT FOR UPDATE` lock ensures only one transaction can proceed -- the other is blocked until the first completes, and then fails because the seat is already taken.

### Reading the Results

After the race completes, the results panel shows two side-by-side cards:

- **Alice (User A)** and **Bob (User B)**
- Each card displays:
  - **BOOKED** (green, if they won) or **REJECTED** (red, if they lost)
  - A detail message explaining the outcome
  - The elapsed time in milliseconds
- Below the cards, a banner announces the **Winner** (either Alice or Bob)

The seat map refreshes automatically after the race to show the newly booked seat in its updated color. The selected seat is cleared so you can run another race with a different seat.

### Key Takeaway

No matter how many times you run the demo, exactly one user always wins and one always loses. Double bookings are impossible thanks to the database-level locking strategy.

---

## Demo Accounts

The application is seeded with three accounts for testing:

| Account          | Email                | Password      | Role   | Name          |
|------------------|----------------------|---------------|--------|---------------|
| Alice            | alice@example.com    | password123   | user   | Alice Rahman  |
| Bob              | bob@example.com      | password123   | user   | Bob Hasan     |
| Admin            | admin@railbook.com   | admin123      | admin  | Admin User    |

**Alice and Bob** are standard user accounts used in the concurrency demo. They are also convenient for manually testing the booking flow from two different perspectives (use two browser sessions or incognito mode).

**Admin** has the admin role, which grants access to admin-specific endpoints such as statistics and system monitoring.

The login page provides quick-fill buttons for Alice and Bob (but not Admin) to speed up testing.
