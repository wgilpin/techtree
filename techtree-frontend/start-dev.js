// Script to start both the backend and the proxy server
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.join(__dirname, '..', 'backend');

// Start the backend server
const backend = spawn('python', ['main.py'], {
  cwd: backendDir,
  stdio: 'inherit',
  shell: true
});

// Start the proxy server
const proxy = spawn('node', ['proxy-server.js'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true
});

// Handle process termination
process.on('SIGINT', () => {
  console.log('Shutting down servers...');
  backend.kill();
  proxy.kill();
  process.exit();
});

console.log('Development servers started. Press Ctrl+C to stop.');