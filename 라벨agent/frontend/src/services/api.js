import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// 재고
export const getStock = () => api.get('/stock/')
export const deleteStockBulk = (ids) => api.delete('/stock/bulk', { data: ids })

// 발주
export const getOrders = () => api.get('/orders/')
export const createOrder = (data) => api.post('/orders/', data)
export const cancelOrder = (id) => api.patch(`/orders/${id}/cancel`)
export const receiveOrder = (id) => api.patch(`/orders/${id}/receive`)

// 출고
export const getReleases = () => api.get('/releases/')
export const createRelease = (data) => api.post('/releases/', data)
export const completeRelease = (id, times = {}) => api.post(`/releases/${id}/complete`, times)
export const deleteReleasesBulk = (ids) => api.delete('/releases/bulk', { data: ids })
export const reportIncident = (id, data) => api.post(`/releases/${id}/incident`, data)
export const getMachines = () => api.get('/machines/')
export const machineAction = (id, data) => api.post(`/machines/${id}/action`, data)

// AI Agent
export const analyzeOrder = (data) => api.post('/agent/analyze', data)
export const validateLabelCode = (code) => api.get(`/agent/validate/${code}`)
export const getAgentStatus = () => api.get('/agent/status')
export const parseBL = (formData) =>
  api.post('/agent/parse-bl', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

const PACKING_LIST_MIME = {
  csv: 'text/csv',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

const readFilenameFromDisposition = (contentDisposition) => {
  if (!contentDisposition) return null

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }

  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i)
  return plainMatch?.[1] || null
}

const triggerBlobDownload = (data, headers, fallbackName, format) => {
  const mimeType = PACKING_LIST_MIME[format] || PACKING_LIST_MIME.csv
  const filename = readFilenameFromDisposition(headers?.['content-disposition']) || fallbackName
  const url = URL.createObjectURL(new Blob([data], { type: mimeType }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 패킹리스트 다운로드 (날짜 범위)
export const downloadPackingList = async (from, to, format = 'csv') => {
  const res = await api.get('/releases/packing-list', {
    params: { from, to, format },
    responseType: 'blob',
  })
  triggerBlobDownload(res.data, res.headers, `packing_list_${from}_${to}.${format}`, format)
}

// 패킹리스트 다운로드 (선택 출고건)
export const downloadSelectedPackingList = async (releaseIds, format = 'csv') => {
  const res = await api.post(
    '/releases/packing-list/selected',
    { release_ids: releaseIds },
    {
      params: { format },
      responseType: 'blob',
    },
  )
  triggerBlobDownload(
    res.data,
    res.headers,
    `packing_list_selected_${releaseIds.length}items.${format}`,
    format,
  )
}
