export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  workspace_configured: boolean;
  database_configured: boolean;
  comfyui_configured: boolean;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type Project = {
  id: string;
  name: string;
  slug: string;
  description: string;
  root_path: string;
  schema_version: number;
  created_at: string;
  updated_at: string;
  last_opened_at: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Backend returned ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function listProjects(signal?: AbortSignal): Promise<Project[]> {
  return request<Project[]>("/projects", { signal });
}

export function createProject(payload: { name: string; description: string }): Promise<Project> {
  return request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) });
}

export function updateProject(
  projectId: string,
  payload: { name?: string; description?: string },
): Promise<Project> {
  return request<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function openProject(projectId: string): Promise<Project> {
  return request<Project>(`/projects/${projectId}/open`, { method: "POST" });
}

export function deleteProject(projectId: string): Promise<void> {
  return request<void>(`/projects/${projectId}`, { method: "DELETE" });
}

