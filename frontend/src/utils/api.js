import axios from "axios";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000",
  timeout: 120000,
});

// ── Upload ────────────────────────────────────────────────────────────────────

export const uploadFiles = async (files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const response = await api.post("/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
};

export const addFilesToSession = async (sessionId, files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const response = await api.post(`/upload/${sessionId}/add`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
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
