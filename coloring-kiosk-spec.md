# Kids' Coloring Page Kiosk — Project Spec

## 1. Goal

A closed, self-hosted, kid-safe web app that lets young children (pre-reading /
early-reading, no internet experience) browse a curated library of coloring
pages by picture, select one, and print it on a home network printer —
with zero ability to navigate anywhere else. Parent (admin) manages the
library through a separate gated interface.

Two consumers of the same backend:
- **Kid UI**: full-screen, icon-driven, no text-input, no navigation chrome.
- **Admin UI**: password-gated, used only by the parent to add/organize pages.

---

## 2. Architecture

```
┌─────────────────────┐        ┌──────────────────────────┐
│ Kiosk device         │  HTTP  │ FastAPI backend (Docker)  │
│ (tablet / touchscreen│◄──────►│  - SQLite DB              │
│  in kiosk browser)   │        │  - image storage on disk  │
└─────────────────────┘        │  - IPP client → printer   │
                                └────────────┬─────────────┘
                                             │ IPP (network)
                                             ▼
                                   ┌───────────────────┐
                                   │ Network printer    │
                                   │ (WiFi/ethernet IP) │
                                   └───────────────────┘
```

- **Backend**: Python, FastAPI, SQLite, served via Docker on the homelab
  (same pattern as existing self-hosted stack), reachable on LAN via
  hostname (mDNS/Pi-hole DNS already in place).
- **Frontend**: server-rendered HTML + HTMX (matches existing stack
  preference) *or* a small React app — either works; HTMX is simpler to keep
  fully offline/local with no build step, recommended default.
- **Printing**: `ipp` or `pyipp` Python library talks directly to the
  printer's IP over IPP — no CUPS setup needed on the server.
- **Storage**: coloring page images (PNG/JPG or single-page PDF) + generated
  thumbnails, stored on disk, referenced by path in SQLite.

---

## 3. Data model (SQLite)

**categories**
| field | type | notes |
|---|---|---|
| id | int PK | |
| name | text | e.g. "Dinosaurs" |
| icon_image_path | text | thumbnail representing the category tile |
| sort_order | int | controls tile order in kid UI |

**pages**
| field | type | notes |
|---|---|---|
| id | int PK | |
| category_id | int FK | |
| title | text | admin-facing only, not shown to kids |
| image_path | text | full-res printable file |
| thumb_path | text | generated small preview |
| source | text | "seed" / "admin_upload" / "ai_generated" |
| created_at | datetime | |

**print_log** (optional, nice for troubleshooting/limits)
| field | type | notes |
|---|---|---|
| id | int PK | |
| page_id | int FK | |
| printed_at | datetime | |
| status | text | success/failed |

---

## 4. Kid-facing UI flow

1. **Home screen**: full-screen grid of category tiles, each a large image +
   short label (optional, since pre-readers). Minimum tap target ~150px.
2. **Category screen**: grid of page thumbnails within that category. Back
   button (large, icon-only, top-left, always present).
3. **Preview screen**: large preview of the selected page, one big
   **Print** button, one **Back** button. No other controls.
4. On print tap: show a simple animated "Printing..." confirmation
   (checkmark/spinner), then auto-return to the category screen after a few
   seconds.

Hard constraints:
- No address bar, no browser UI (kiosk mode handles this at the OS level).
- No text input fields anywhere in the kid UI.
- No links that leave the app's own domain.
- No visible way to reach the admin interface from the kid UI (different
  path, e.g. `/admin`, not linked anywhere in kid-facing pages).

---

## 5. Admin UI flow

- Path: `/admin`, protected by a simple password (env var + session cookie;
  no need for full auth system given single-user LAN-only use).
- Features:
  - Create/edit/reorder categories (upload a tile icon, set name).
  - Bulk-upload images into a category → auto-generate thumbnails
    (Pillow) → insert into `pages` table.
  - Delete/re-categorize pages.
  - (Phase 2) "Generate new page" form: text prompt → calls an image-gen
    API/local model → saves result as a new page pending admin approval
    before it appears in the kid UI.

---

## 6. Printing implementation notes

- Use `pyipp` (or raw IPP via `ipp` package) to send the print job directly
  to the printer's IP — avoids needing CUPS installed anywhere.
- Convert images to PDF at print time if the printer/driver prefers PDF
  (use Pillow → PDF, single page, fit to Letter/A4).
- Add a basic rate limit (e.g. max N prints per hour) at the backend level
  to prevent a curious toddler from mashing "Print" and draining the ink
  cartridge/paper tray — configurable via env var.
- Handle printer offline/error gracefully: kid UI shows a friendly "Oops,
  ask a grown-up!" state rather than an error trace.

---

## 7. Content sourcing for starter library

- Seed library from public-domain / free-to-use coloring page sources
  (bulk-downloaded once by the admin, not fetched live by the kid UI).
- Organize into initial categories: Animals, Dinosaurs, Vehicles, Space,
  Princesses/Fantasy, Holidays, Numbers/Letters.
- Phase 2: AI-generated custom pages (line-art style prompt template) added
  via the admin "Generate new page" form, so the library can grow without
  needing to source new files manually.

---

## 8. Device / kiosk options (pick one now, others stay compatible later)

All options point at the same backend URL — no backend changes needed to
switch or add devices later.

**A. Spare/cheap Android tablet**
- Install **Fully Kiosk Browser** (free/paid), set start URL to the
  backend's LAN address, enable kiosk lockdown (disables home button,
  notifications, etc.).

**B. iPad**
- Use Safari + **Guided Access** (Settings → Accessibility), pinned to the
  app's URL as a home-screen web app (Add to Home Screen) for a full-screen,
  chrome-free look.

**C. Wall-mounted touchscreen**
- Raspberry Pi (4 or 5) or small mini-PC + HDMI touchscreen.
- Chromium launched with `--kiosk --app=http://<backend-host>.local`, set
  to auto-launch on boot (systemd service or `.xinitrc` autostart).
- More permanent/furniture-like; good phase-2 upgrade once the app is
  proven on a tablet.

Recommendation: start with whatever tablet is easiest to get hold of first
(Option A or B) to validate the UI/print flow with the kids, then invest in
a mounted touchscreen (Option C) once it's clear it's getting used.

---

## 9. Deployment

- Single `docker-compose.yml`:
  - `app` service: FastAPI + HTMX frontend, mounts `./data` (SQLite +
    images) as a volume.
  - Reachable via existing homelab reverse proxy / local DNS, e.g.
    `coloring.home.local`.
- No external internet access required for the container itself except to
  reach the printer's LAN IP (and optionally an image-gen API in phase 2).

---

## 10. Build phases

**Phase 1 (MVP)**
- DB schema + FastAPI backend
- Kid UI: home → category → preview → print
- Admin UI: category/page management + bulk upload
- IPP printing to configured printer IP
- Seed with 5–7 categories, ~10–20 pages each from downloaded public-domain
  sets

**Phase 2**
- Print rate-limiting + friendly error states
- AI-generated page creation flow in admin
- Wall-mounted touchscreen deployment (Pi + kiosk autostart)

**Phase 3 (optional)**
- Simple "favorites" or "recently printed" row for kids
- Seasonal/holiday auto-rotating categories
- Multiple printer support (pick nearest/default)

---

## 11. Open questions for implementation kickoff

- Printer make/model + confirm it supports IPP (nearly all modern network
  printers do) — needed to finalize the print-job code path.
- Preferred frontend: confirm HTMX (simplest, matches existing stack) vs.
  React (only needed if richer animations/interactions are wanted later).
- Where in the homelab this should live (which host/VM, reverse proxy
  domain name) to fold into existing Docker/Proxmox setup.
