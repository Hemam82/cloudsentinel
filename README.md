# cloudsentinel
CloudSentinel is a platform that monitors cloud infrastructure and alerts users about security and performance issues in real-time. It provides dashboards, automated notifications, and tools to optimize cloud resources.
## Features
- Real-time monitoring of cloud resources
- Alerts for security and performance issues
- Resource management and optimization
- Web-based interface built with React

## Tech Stack
- **Backend:** Python / FastAPI
- **Frontend:** React / PNPM
- **Database:** PostgreSQL / MongoDB

## How to Run Locally

### Backend
```bash
cd ~/Desktop/cloudsentinel
source .venv/bin/activate
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
Frontend
bash
cd ~/Desktop/cloudsentinel/apps/web
pnpm install
pnpm dev
License
This project is licensed under the MIT License.

Contact
For any questions or suggestions, contact: Hemam82

