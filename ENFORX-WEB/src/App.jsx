import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import SystemConsole from './pages/SystemConsole';
import SetupWizard from './pages/SetupWizard';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/web" element={<SystemConsole />} />
      <Route path="/console" element={<Navigate to="/web" replace />} />
      <Route path="/setup" element={<SetupWizard />} />
    </Routes>
  );
}

export default App;
