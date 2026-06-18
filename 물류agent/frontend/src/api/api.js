import axios from 'axios';

const BASE = 'http://localhost:8004/api';

export const api = axios.create({ baseURL: BASE });

// 기사
export const getDrivers = () => api.get('/drivers/');
export const createDriver = (data) => api.post('/drivers/', data);
export const updateDriver = (id, data) => api.put(`/drivers/${id}`, data);
export const deleteDriver = (id) => api.delete(`/drivers/${id}`);

// 차량
export const getVehicles = () => api.get('/vehicles/');
export const createVehicle = (data) => api.post('/vehicles/', data);
export const updateVehicle = (id, data) => api.put(`/vehicles/${id}`, data);
export const deleteVehicle = (id) => api.delete(`/vehicles/${id}`);

// 화물/배차
export const getDeliveries = () => api.get('/deliveries/');
export const createDelivery = (data) => api.post('/deliveries/', data);
export const completeDelivery = (id) => api.post(`/deliveries/${id}/complete`);
export const assignDriver = (deliveryId, driverId, vehicleId, pickupDate) => {
  const params = { driver_id: driverId, vehicle_id: vehicleId };
  if (pickupDate) {
    params.pickup_date = pickupDate;
  }

  return api.put(`/deliveries/${deliveryId}/assign`, null, { params });
};

// AI 패널
export const getAIPanel = () => api.get('/ai/panel');
export const autoDispatch = (deliveryId) => api.post(`/ai/dispatch/${deliveryId}`);
export const getPlatformChannel = (limit = 30) =>
  api.get('/platform/channel', { params: { limit } });
