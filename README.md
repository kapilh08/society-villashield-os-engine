# 🛡️ VillaShield OS - System Documentation Index

Welcome to the official documentation suite for **VillaShield OS Engine**, an integrated security, visitor access control, and domestic staff management platform tailored for gated villa societies and residential communities.

---

## 📌 Documentation Suite Index

| Document | Description |
| :--- | :--- |
| 🏗️ [**Architecture & System Design**](./architecture_and_design.md) | High-level system architecture, database ERD, WebSocket alert manager, and hardware monitoring subsystem. |
| 🔄 [**User Flows & Sequence Diagrams**](./user_flows_and_sequence.md) | Comprehensive step-by-step user flows, state transitions, and Mermaid sequence diagrams for Guard, Resident, Staff, and Admin interactions. |
| 🔌 [**API Contract & Reference**](./api_reference.md) | OpenAPI REST specification, FastAPI Web Engine form handlers, WebSocket payloads, and Bruno collection mapping. |
| 🚀 [**Deployment & Setup Guide**](./deployment_and_setup.md) | Docker Compose configuration, `.env` parameters, automated master database seeding, and Streamlit execution guide. |
| 🎯 [**App Evaluation & Enhancements**](./app_evaluation_and_enhancements.md) | UX credibility scorecard, Guard/Resident/Admin usability analysis, concrete improvement suggestions, and commercialization roadmap. |

---

## 🚀 Core Capabilities at a Glance

### 1. 💂 Guard Gate Access Control Terminal
- **Visitor Pre-Registration**: Onboard visitors with target villa ID, vehicle plate details, and purpose of visit.
- **Instant Gate Push**: Dispatches instant real-time alerts directly to the target resident's application/browser.
- **Domestic Staff Punch Clock Engine**: Validates domestic workers (maids, drivers, cooks, maintenance) using secure hashed passcodes/PINs to track automated clock-in/check-out timestamps.

### 2. 🏡 Resident Authorization Panel
- **Real-Time Push Notifications**: Instant notification upon visitor arrival at the perimeter gate.
- **One-Tap Decision Engine**: Authorize (`APPROVED`) or decline (`DENIED`) visitor entry with live feedback broadcast back to guard monitors.

### 3. 📊 Executive Committee Command Tower (Admin)
- **Perimeter Telemetry & Metrics**: Real-time counter of total crossings, approved entries, turned-away visitors, and active staff inside.
- **Hourly Traffic Load Analysis**: Peak entry hour distribution graphs for capacity planning.
- **Audit Log Exports**: One-click CSV downloads for full visitor entry history and staff attendance logs formatted for compliance reporting.
- **Guard & Staff Management**: Onboard domestic workers, issue passcode PINs, and evict unauthorized guard accounts.

---

## 🛠️ Technology Stack Breakdown

| Layer | Technology Used |
| :--- | :--- |
| **Backend Core Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+) |
| **Database ORM & Migration** | [SQLAlchemy](https://www.sqlalchemy.org/) & PostgreSQL |
| **Real-Time Communication** | Native Async WebSockets (`ConnectionManager`) |
| **Authentication & Security** | JWT (PyJWT/python-jose), HTTP Cookies, Native `bcrypt` PIN/Password Hashing |
| **Frontend Web Engines** | Jinja2 Templates (HTML5/CSS3) + [Streamlit](https://streamlit.io/) Management Terminal (`ui.py`) |
| **Hardware Telemetry** | Async background ICMP network ping monitoring loop |
| **API Testing Suite** | [Bruno](https://www.usebruno.com/) API Collection (`bruno_collection/`) |
| **Containerization** | Docker & Docker Compose |

---

## 📁 Repository File Map

```
villashield_backend/
├── app/
│   ├── auth.py                   # Password hashing, JWT creation & authentication dependencies
│   ├── config.py                 # Pydantic Settings reading environment variables from .env
│   ├── database.py               # SQLAlchemy database engine and session generator
│   ├── main.py                   # Main FastAPI application, Jinja2 routes, background tasks & seeding
│   ├── ui.py                     # Streamlit dashboard interface
│   ├── models/
│   │   └── models.py             # SQLAlchemy DB schemas (User, VisitorLog, DomesticStaff, StaffAttendance)
│   ├── routers/
│   │   ├── admin.py              # Executive Committee analytics metrics endpoints
│   │   ├── auth.py               # REST API authentication endpoints
│   │   ├── staff.py              # Domestic staff registration and clock-in/out endpoints
│   │   └── visitors.py           # Visitor registration and decision action endpoints
│   ├── schemas/
│   │   └── schemas.py            # Pydantic data validation schemas
│   ├── services/
│   │   ├── hardware_monitor.py   # Background ICMP perimeter camera status monitor
│   │   └── websocket_manager.py  # WebSocket connection manager for live alerts
│   └── templates/                # Jinja2 HTML templates
│       ├── dashboard.html        # Executive Committee Admin dashboard
│       ├── guard.html            # Guard gate entry portal
│       ├── login.html            # Authentication gate
│       ├── register.html         # User onboarding screen
│       └── resident.html         # Resident decision panel
├── bruno_collection/             # Bruno REST API test collection (.bru)
├── docs/                         # Detailed system documentation
├── Dockerfile                    # Container configuration
└── docker-compose.yml            # Multi-container orchestra (web, db, streamlit)
```
