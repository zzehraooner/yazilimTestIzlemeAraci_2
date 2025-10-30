import axios from "axios";

export const api = axios.create({
  baseURL: "http://localhost:8000",
  timeout: 8000,
});

export async function fetchRuns() {
  const response = await api.get("/runs");
  return response.data;
}

export async function fetchRun(runId) {
  const response = await api.get(`/runs/${runId}`);
  return response.data;
}

export async function fetchSamples(runId, params = {}) {
  const response = await api.get(`/runs/${runId}/samples`, { params });
  return response.data;
}

export async function fetchComparison(currentId, baseline = "latest-success") {
  const response = await api.get("/compare", { params: { current: currentId, baseline } });
  return response.data;
}
