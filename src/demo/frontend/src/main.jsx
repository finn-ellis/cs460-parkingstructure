import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

/* minimal global reset */
document.documentElement.style.margin = '0';
document.documentElement.style.padding = '0';
document.body.style.margin = '0';
document.body.style.padding = '0';
document.body.style.background = '#1a1a2e';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
