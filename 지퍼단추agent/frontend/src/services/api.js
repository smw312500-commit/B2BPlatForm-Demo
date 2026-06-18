import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8003',
})

// 재고
export const getStock        = ()        => api.get('/stock/')
export const deleteStockBulk = (ids)     => api.delete('/stock/bulk', { data: ids })

// 발주
export const getOrders     = ()     => api.get('/orders/')
export const createOrder   = (data) => api.post('/orders/', data)
export const cancelOrder   = (id)   => api.patch(`/orders/${id}/cancel`)
export const receiveOrder  = (id)   => api.patch(`/orders/${id}/receive`)

// 출고
export const getReleases        = ()          => api.get('/releases/')
export const createRelease      = (data)      => api.post('/releases/', data)
export const completeRelease    = (id, times) => api.post(`/releases/${id}/complete`, times ?? {})
export const deleteReleasesBulk  = (ids)       => api.delete('/releases/bulk', { data: ids })
export const downloadPackingList = (from, to)  => api.get(`/releases/packing-list?from=${from}&to=${to}`, { responseType: 'blob' })

// AI Agent
export const analyzeOrder   = (data) => api.post('/agent/analyze', data)
export const validateItem   = (name) => api.get(`/agent/validate/${encodeURIComponent(name)}`)
export const getAgentStatus = ()     => api.get('/agent/status')
