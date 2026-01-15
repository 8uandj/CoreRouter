import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Topology from './views/Topology';
import Monitoring from './views/Monitoring';
import axios from 'axios';
import AISecurityPanel from './components/AISecurityPanel';

const API_BASE = "http://localhost:8001/api";

const App = () => {
  const [vnfs, setVnfs] = useState([]);
  const [pipelineProgress, setPipelineProgress] = useState(null);

  const fetchData = async () => {
    try {
      // 1. Lấy danh sách VNF cho Topology
      // (Backend mới đã refactor logic này vào services/topology_service.py)
      const vnfRes = await axios.get(`${API_BASE}/vnfs`);
      setVnfs(vnfRes.data);

      // 2. Lấy trạng thái Pipeline cho Activity Panel
      const pipeRes = await axios.get(`${API_BASE}/pipelineruns/latest`);
      // console.log("Pipeline Data:", pipeRes.data); // Bỏ comment nếu cần debug
      setPipelineProgress(pipeRes.data);
    } catch (e) {
      console.error("Data fetch error", e);
    }
  };

  const handleDeploy = async (formData) => {
    try {
      console.log("Sending deploy request:", formData); 
      
      const res = await axios.post(`${API_BASE}/deploy`, formData);
      
      console.log("Server Response:", res); 

      if (res.data && res.data.message) {
        alert(`System: ${res.data.message}`);
      } else {
        alert("System: Deployment triggered (No message from backend)");
      }
      
      fetchData(); 
      
    } catch (e) {
      console.error("Deploy Error Detailed:", e);
      const errorMsg = e.response?.data?.message || e.message || "Unknown error";
      alert(`Deployment Failed: ${errorMsg}`);
    }
  };

  // Polling dữ liệu định kỳ
  useEffect(() => {
    fetchData();
    // Giảm thời gian polling xuống 3s để hệ thống phản ứng nhanh hơn khi Demo
    const interval = setInterval(fetchData, 3000); 
    return () => clearInterval(interval);
  }, []);

  return (
    <Router>
      <Layout pipelineProgress={pipelineProgress}>
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
          
          <Routes>
            <Route path="/" element={<Topology vnfs={vnfs} onDeploy={handleDeploy} />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/pipelines" element={<div className="p-10">Pipeline History List...</div>} />
            <Route path="/security" element={<div className="p-10">AI Security Dashboard...</div>} />
          </Routes>
          <AISecurityPanel />
          
        </div>
      </Layout>
    </Router>
  );
};

export default App;