import axios from 'axios';

const API_BASE = "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const vnfService = {
  fetchVnfs: async () => {
    const res = await apiClient.get('/vnfs');
    if (Array.isArray(res.data)) {
      return { nodes: res.data };
    }
    return res.data;
  },

  deployVnf: async (formData) => {
    const payload = {
      name: formData.name,
      type: formData.type,
      profile: formData.profile || 'standard',
      location: formData.location || 'auto',
    };
    const res = await apiClient.post('/deploy', payload);
    return res.data;
  },

  deleteVnf: async (vnfName) => {
    const res = await apiClient.delete(`/vnfs/${vnfName}`);
    return res.data;
  },

  getMetrics: async () => {
    const res = await apiClient.get('/metrics/router');
    return res.data;
  },
  
  getSimulationStatus: async () => {
    const res = await apiClient.get('/ai/status');
    return res.data;
  }
};
