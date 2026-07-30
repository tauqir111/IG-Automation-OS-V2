import { useEffect } from 'react';
import './App.css';

// The dashboard is served by FastAPI (Jinja2) at /api/. The React frontend
// is only present as a preview-shell redirect.
export default function App() {
  useEffect(() => {
    window.location.replace('/api/');
  }, []);

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#08090c',
        color: '#e6e8ee',
        fontFamily: 'Inter, system-ui, sans-serif',
        letterSpacing: '-0.01em',
      }}
      data-testid="redirect-shell"
    >
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'monospace',
          color: '#c8ff2c',
          fontSize: 11,
          letterSpacing: '0.14em',
          marginBottom: 12,
        }}>
          IG AUTOMATION OS
        </div>
        <div style={{ fontSize: 18, marginBottom: 4 }}>Loading dashboard…</div>
        <a
          href="/api/"
          style={{ color: '#c8ff2c', textDecoration: 'underline', fontSize: 13 }}
          data-testid="manual-link"
        >
          Go to dashboard →
        </a>
      </div>
    </div>
  );
}
