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

export type Asset = {
  id: string;
  project_id: string;
  name: string;
  asset_type: "character" | "item" | "environment" | "tileset";
  style: "micro_pixel" | "eight_bit" | "custom";
  width: number;
  height: number;
  color_mode: string;
  active_version_id: string | null;
  thumbnail_path: string;
  created_at: string;
  updated_at: string;
};

export type AssetVersion = {
  id: string;
  asset_id: string;
  version_number: number;
  parent_version_id: string | null;
  checksum: string;
  source: string;
  change_summary: string;
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers:
      init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json", ...init.headers }
        : init?.headers,
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

export function listAssets(projectId: string, signal?: AbortSignal): Promise<Asset[]> {
  return request<Asset[]>(`/projects/${projectId}/assets`, { signal });
}

export function importAsset(projectId: string, payload: FormData): Promise<Asset> {
  return request<Asset>(`/projects/${projectId}/assets/import`, {
    method: "POST",
    body: payload,
  });
}

export function listAssetVersions(assetId: string, signal?: AbortSignal): Promise<AssetVersion[]> {
  return request<AssetVersion[]>(`/assets/${assetId}/versions`, { signal });
}

export function restoreAssetVersion(assetId: string, versionId: string): Promise<AssetVersion> {
  return request<AssetVersion>(`/assets/${assetId}/versions/${versionId}/restore`, {
    method: "POST",
  });
}

