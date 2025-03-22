# TechTree Proxy Setup

This setup uses a proxy server to avoid CORS issues between the frontend and backend.

## How It Works

1. The proxy server runs on port 3000 and serves the frontend static files
2. API requests from the frontend are automatically forwarded to the backend
3. Since the frontend and API requests come from the same origin, there are no CORS issues

## Setup Instructions

1. Install the required dependencies:
   ```
   cd techtree-frontend
   npm install express http-proxy-middleware cors
   ```

2. Start the development environment:

   ### Option 1: Start everything with one command
   ```
   npm run dev-all
   ```
   This will start:
   - The backend server (Python FastAPI)
   - The proxy server (Node.js)

   ### Option 2: Start components separately

   Terminal 1 - Start the backend:
   ```
   cd backend
   python main.py
   ```

   Terminal 2 - Start the proxy server:
   ```
   cd techtree-frontend
   npm run proxy
   ```

   Terminal 3 - Start the frontend development server:
   ```
   cd techtree-frontend
   npm run dev
   ```

3. Access the application:
   - Open your browser to http://localhost:3000

## Troubleshooting

If you encounter any issues:

1. Make sure all servers are running
2. Check that the backend is running on port 8000
3. Check that the proxy server is running on port 3000
4. Clear your browser cache and cookies
5. Try using incognito/private browsing mode