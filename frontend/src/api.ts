import type { HealthInfo, RunRecord, Template } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthInfo> {
  const response = await fetch(`${API_BASE}/health`);
  return parse<HealthInfo>(response);
}

export async function fetchTemplates(): Promise<Template[]> {
  const response = await fetch(`${API_BASE}/templates`);
  return (await parse<{ templates: Template[] }>(response)).templates;
}

export async function createRun(payload: { prompt: string; language: string; max_iterations: number; run_tests: boolean }) {
  const response = await fetch(`${API_BASE}/runs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  return parse<{ id: string; status: string }>(response);
}

export async function fetchRun(id: string): Promise<RunRecord> {
  const response = await fetch(`${API_BASE}/runs/${id}`);
  return parse(response);
}


