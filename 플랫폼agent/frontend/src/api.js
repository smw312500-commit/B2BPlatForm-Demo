import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getDashboardSummary = () => api.get('/dashboard/summary')
export const getCollectedReleases = (params) => api.get('/collected-release', { params })
export const getLabelCodeStatus = (code) => api.get(`/labelcode/${code}/status`)
export const getDispatches = () => api.get('/dispatch')
export const getDispatchAvailability = () => api.get('/dispatch/availability')
export const rematchDispatch = (dispatchId) => api.post(`/dispatch/${dispatchId}/match`)
export const getInsights = () => api.get('/insights')
export const analyzeInsights = () => api.post('/insights/analyze')
export const getDemoSupplyChainData = () => api.get('/insights/demo-supply-chain')
export const getReportChannels = () => api.get('/report-channels')
export const getReportChannelMessages = (channel, params) => api.get(`/report-channels/${channel}/messages`, { params })
export const getPackingListDownloadUrl = (packingListId) => `/api/packing-lists/${packingListId}/download`
export const queryInsight = (question) => api.post('/insights/query', { question })
