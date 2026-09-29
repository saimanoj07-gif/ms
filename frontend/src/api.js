import axios from 'axios'

const api = axios.create({ baseURL: '/' })

// ---------- content ----------
export const createContent = (data) => api.post('/api/content', data)
export const listContent = (params) => api.get('/api/content', { params })
export const analyzeContent = (contentId) => api.post('/api/content/analyze', { content_id: contentId })

// ---------- analytics / dashboard ----------
export const getAnalytics = () => api.get('/api/analytics')
export const getDashboard = () => api.get('/api/dashboard')
export const getGaps = () => api.get('/api/gaps')

// ---------- plans ----------
export const generatePlan = (data) => api.post('/api/plans/generate', data)
export const listPlans = () => api.get('/api/plans')

// ---------- memory ----------
export const getMemory = () => api.get('/api/memory')
export const getRawMemory = () => api.get('/api/memory/raw')
export const learnMemory = (text) => api.post('/api/memory/learn', { text })

// ---------- chat ----------
export const sendChat = (message) => api.post('/api/chat', { message })

// ---------- demo ----------
export const demoReset = () => api.post('/api/demo/reset')
export const demoSeed = (count = 64) => api.post('/api/demo/seed', { count })
