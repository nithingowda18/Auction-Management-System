# BidBay — Auction Management System

A clean full-stack auction marketplace built with Python, Flask, SQLite, HTML, CSS and JavaScript. It includes registration/login, product listings, bidding, seller dashboards, bid history and demo transaction records.

## Features
- Passwords are stored as Werkzeug password hashes, never plain text.
- Create accounts, sign in/out and list auction items.
- Browse live auctions and see current highest bids and bid counts.
- Enforce minimum bid amounts and prevent sellers from bidding on their own items.
- Seller can close an auction; the highest bidder is recorded in a clearly labelled demo transaction table.
- Personal dashboard for listings, bids and transaction outcomes.
- Responsive layout and sample listings for interviewer demos.

## Run locally
Requires Python 3.10+.

```bash
# Windows PowerShell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
flask --app app seed-demo
python app.py
```

Open http://127.0.0.1:5000.

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal, or run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe app.py` without activating.

### Demo accounts
- Seller: `seller@example.com` / `DemoPass123!`
- Buyer: `buyer@example.com` / `DemoPass123!`

Use the seller to close a listing and the buyer to place bids. Seed data is inserted only when there are no listings. You can register your own accounts too.

## Database design
- `users`: account identity and password hash.
- `listings`: item, seller, starting price, deadline and status.
- `bids`: each bid references a listing and bidder.
- `transactions`: one demo outcome per closed listing with a winning bid.

The schema uses foreign keys and constraints. Current bid is calculated from the highest bid, falling back to the starting price. This is an educational demo, not a production auction engine: concurrent bidding would need database transactions/locking, CSRF protection, stronger configuration and deployment hardening. No real payment gateway is connected.

## Interview walkthrough (3–5 minutes)
1. Sign in as the demo seller and show active product cards.
2. Create a listing with a starting price and duration.
3. Sign out, sign in as the buyer and place a bid.
4. Show the new current bid and recent bid history.
5. Return to seller dashboard and close the auction; explain that the highest bid becomes a demo transaction.
6. Explain relational tables, foreign keys, password hashing and the route/template split.

## Main files
- `app.py`: Flask routes, validation and SQL operations.
- `templates/`: Jinja pages.
- `static/style.css`: responsive UI.
- `static/app.js`: browser interactions.
- `auction.db`: created automatically on first run (ignored by Git).
