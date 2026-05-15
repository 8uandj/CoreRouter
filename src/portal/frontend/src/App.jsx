import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Topology from './views/Topology';
import { vnfService } from './services/api';

const App = () => {
  const [vnfs, setVnfs] = useState({ nodes: [] });

  const fetchData = async () => {
    try {
      const data = await vnfService.fetchVnfs();
      setVnfs(data);
    } catch {
      // API unreachable
    }
  };

  const handleDeploy = async (formData) => {
    try {
      const res = await vnfService.deployVnf(formData);
      alert(res.message || 'Deployment initiated.');
      fetchData();
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : (detail || e.message);
      alert(`Deploy Error: ${msg}`);
    }
  };

  const handleDelete = async (vnfName) => {
    if (!window.confirm(`Delete VNF: ${vnfName}?`)) return;
    try {
      await vnfService.deleteVnf(vnfName);
      fetchData();
    } catch (e) {
      alert(`Delete failed: ${e.message}`);
    }
  };

  useEffect(() => {
    queueMicrotask(fetchData);
    const t = setInterval(fetchData, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <Router>
      <div className="w-screen h-screen overflow-hidden bg-[#020617] font-sans">
        <Routes>
          <Route path="/" element={<Topology vnfs={vnfs} onDeploy={handleDeploy} onDelete={handleDelete} />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;
