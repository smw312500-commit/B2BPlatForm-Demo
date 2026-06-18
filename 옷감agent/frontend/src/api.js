import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:8002' });

export const stockApi = {
  getAll:  ()         => api.get('/stock/'),
  create:  (data)     => api.post('/stock/', data),
  update:  (id, data) => api.patch(`/stock/${id}`, data),
  delete:  (id)       => api.delete(`/stock/${id}`),
};

export const productionApi = {
  getAll:       ()          => api.get('/production/'),
  getCompleted: ()          => api.get('/production/completed'),
  create:       (data)      => api.post('/production/', data),
  updateStage:  (id, stage) => api.patch(`/production/${id}/stage`, { stage }),
  delete:       (id)        => api.delete(`/production/${id}`),
};

export const orderApi = {
  getAll:    () => api.get('/order/'),
  getActive: () => api.get('/order/active'),
  create:    (data) => api.post('/order/', data),
  complete:  (id)   => api.patch(`/order/${id}/complete`),
  cancel:    (id)   => api.patch(`/order/${id}/cancel`),
};

export const releaseApi = {
  getAll:    () => api.get('/release/'),
  getActive: () => api.get('/release/active'),
  create:    (data) => api.post('/release/', data),
  complete:  (id)   => api.patch(`/release/${id}/complete`),
  downloadPackingList: async (from, to) => {
    const res = await api.get('/release/packing-list', {
      params: { from, to },
      responseType: 'blob',
    });
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `packing_list_${from}_${to}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

export const agentApi = {
  getStatus:      ()          => api.get('/agent/status'),
  validate:       (code)      => api.get(`/agent/validate/${encodeURIComponent(code)}`),
  analyze:        (data)      => api.post('/agent/analyze', data),
  parseBL:        (formData)  => api.post('/agent/parse-bl', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  reportIncident: (id, data)  => api.post(`/production/${id}/incident`, data),
};
