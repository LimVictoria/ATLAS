import axios from "axios";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
  timeout: 300000, // 5 minutes — needed for 9 files on free tier
});

// ── Upload ────────────────────────────────────────────────────────────────────

export const uploadFiles = async (files, onProgress) => {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const response = await api.post("/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
  return response.data;
};

export const addFilesToSession = async (sessionId, files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const response = await api.post(`/upload/${sessionId}/add`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 300000,
  });
  return response.data;
};

export const closeSession = async (sessionId) => {
  await api.delete(`/upload/${sessionId}`);
};

// ── Chat ──────────────────────────────────────────────────────────────────────

export const sendChat = async (sessionId, prompt) => {
  const response = await api.post("/chat/", { session_id: sessionId, prompt });
  return response.data;
};

export const getChatHistory = async (sessionId) => {
  const response = await api.get(`/chat/history/${sessionId}`);
  return response.data;
};

export const clearChatHistory = async (sessionId) => {
  await api.delete(`/chat/history/${sessionId}`);
};

export const generateChart = async (sessionId, tableN, chartType, xCol, yCol, colorCol) => {
  const response = await api.post("/chat/chart", {
    session_id: sessionId,
    table_name: tableN,
    chart_type: chartType,
    x_col: xCol,
    y_col: yCol || null,
    color_col: colorCol || null,
  });
  return response.data;
};

export const getSchema = async (sessionId) => {
  const response = await api.get(`/chat/schema/${sessionId}`);
  return response.data;
};

export default api;

export const getTableCharts = async (sessionId, tableName, col = null) => {
  const params = col ? `?col=${encodeURIComponent(col)}` : "";
  const response = await api.get(`/upload/${sessionId}/charts/${tableName}${params}`);
  return response.data;
};
