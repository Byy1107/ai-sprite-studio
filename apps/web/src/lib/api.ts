export type HealthResponse = {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  workspace_configured: boolean;
  database_configured: boolean;
  comfyui_configured: boolean;
};

export type AIHealthResponse = {
  status: "ready" | "unavailable";
  provider: "fake" | "comfyui";
  message: string | null;
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

export type AnimationClip = {
  id: string;
  asset_id: string;
  name: string;
  direction: string;
  fps: number;
  loop_mode: "loop" | "once" | "ping_pong";
  canvas_width: number;
  canvas_height: number;
};

export type AnimationFrame = {
  id: string;
  animation_id: string;
  asset_version_id: string;
  frame_index: number;
  duration_ms: number;
  offset_x: number;
  offset_y: number;
  pivot_x: number;
  pivot_y: number;
  event_name: string | null;
};

export type ExportRecord = {
  id: string;
  project_id: string;
  asset_id: string;
  format: "png" | "spritesheet" | "gif";
  config: Record<string, unknown>;
  output_path: string;
  checksum: string;
  status: string;
  created_at: string;
};

export type GenerationJob = {
  id: string;
  project_id: string;
  asset_id: string | null;
  provider: string;
  workflow_id: string;
  workflow_version: string;
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  request: Record<string, unknown>;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type GenerationResult = {
  id: string;
  job_id: string;
  file_path: string;
  seed: number;
  metadata: Record<string, unknown>;
  selected: boolean;
};

export type GenerationPreset = {
  id: string;
  label: string;
  asset_type: "character" | "item" | "environment" | "tileset";
  description: string;
  prompt: string;
  negative_prompt: string;
  style: "micro_pixel" | "eight_bit";
  width: number;
  height: number;
  version: string;
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

export function getAIHealth(signal?: AbortSignal): Promise<AIHealthResponse> {
  return request<AIHealthResponse>("/system/ai/health", { signal });
}

export function getAICapabilities(signal?: AbortSignal): Promise<{
  provider: string;
  status: string;
  detected_nodes: string[];
  lora_models: string[];
  controlnet_models: string[];
  ipadapter_models: string[];
  clip_vision_models: string[];
  enabled_features: Record<string, boolean>;
  message: string;
}> {
  return request("/system/ai/capabilities", { signal });
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

export function assetVersionContentUrl(versionId: string): string {
  return `${apiBaseUrl}/asset-versions/${versionId}/content`;
}

export function listAnimations(assetId: string, signal?: AbortSignal): Promise<AnimationClip[]> {
  return request(`/assets/${assetId}/animations`, { signal });
}

export function createAnimation(assetId: string, payload: {
  name: string; direction: string; fps: number; loop_mode: AnimationClip["loop_mode"];
}): Promise<AnimationClip> {
  return request(`/assets/${assetId}/animations`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateAnimation(id: string, payload: Partial<Pick<AnimationClip, "name" | "direction" | "fps" | "loop_mode">>): Promise<AnimationClip> {
  return request(`/animations/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteAnimation(id: string): Promise<void> {
  return request(`/animations/${id}`, { method: "DELETE" });
}

export function listAnimationFrames(id: string, signal?: AbortSignal): Promise<AnimationFrame[]> {
  return request(`/animations/${id}/frames`, { signal });
}

export function addAnimationFrame(id: string, assetVersionId: string): Promise<AnimationFrame> {
  return request(`/animations/${id}/frames`, {
    method: "POST", body: JSON.stringify({ asset_version_id: assetVersionId }),
  });
}

export function updateAnimationFrame(id: string, payload: Partial<Pick<AnimationFrame, "duration_ms" | "offset_x" | "offset_y" | "pivot_x" | "pivot_y" | "event_name">>): Promise<AnimationFrame> {
  return request(`/animation-frames/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function duplicateAnimationFrame(id: string): Promise<AnimationFrame> {
  return request(`/animation-frames/${id}/duplicate`, { method: "POST" });
}

export function deleteAnimationFrame(id: string): Promise<void> {
  return request(`/animation-frames/${id}`, { method: "DELETE" });
}

export function reorderAnimationFrames(id: string, frameIds: string[]): Promise<AnimationFrame[]> {
  return request(`/animations/${id}/frames/reorder`, {
    method: "POST", body: JSON.stringify({ frame_ids: frameIds }),
  });
}

export function listExports(projectId: string, signal?: AbortSignal): Promise<ExportRecord[]> {
  return request(`/projects/${projectId}/exports`, { signal });
}

export function createExport(payload: {
  asset_id: string;
  format: ExportRecord["format"];
  version_id?: string;
  animation_id?: string;
  scale: 1 | 2 | 4 | 8;
  columns?: number;
  spacing?: number;
  padding?: number;
}): Promise<ExportRecord> {
  return request("/exports", { method: "POST", body: JSON.stringify(payload) });
}

export function exportFileUrl(exportId: string, kind: "png" | "json" | "gif"): string {
  return `${apiBaseUrl}/exports/${exportId}/files/${kind}`;
}

export function publishManualVersion(
  assetId: string,
  file: Blob,
  changeSummary: string,
): Promise<AssetVersion> {
  const payload = new FormData();
  payload.set("file", file, "manual-edit.png");
  payload.set("change_summary", changeSummary);
  return request<AssetVersion>(`/assets/${assetId}/versions`, {
    method: "POST",
    body: payload,
  });
}

export function listGenerationJobs(projectId: string, signal?: AbortSignal): Promise<GenerationJob[]> {
  return request<GenerationJob[]>(`/generation-jobs?project_id=${encodeURIComponent(projectId)}`, {
    signal,
  });
}

export function listGenerationPresets(signal?: AbortSignal): Promise<GenerationPreset[]> {
  return request<GenerationPreset[]>("/generation-presets", { signal });
}

export function createGenerationJob(payload: {
  project_id: string;
  asset_id?: string | null;
  prompt: string;
  asset_type: "character" | "item" | "environment" | "tileset";
  style: "micro_pixel" | "eight_bit";
  width: number;
  height: number;
  seed: number;
  preset_id?: string | null;
  negative_prompt?: string;
  reference_asset_id?: string | null;
  reference_version_id?: string | null;
  reference_weight?: number;
  lora_name?: string | null;
  lora_weight?: number;
  controlnet_name?: string | null;
  controlnet_strength?: number;
  controlnet_start?: number;
  controlnet_end?: number;
  ipadapter_model?: string | null;
  clip_vision_model?: string | null;
  operation?: "text_to_sprite" | "variation" | "inpaint";
  mask_x?: number | null;
  mask_y?: number | null;
  mask_width?: number | null;
  mask_height?: number | null;
}): Promise<GenerationJob> {
  return request<GenerationJob>("/generation-jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cancelGenerationJob(jobId: string): Promise<GenerationJob> {
  return request<GenerationJob>(`/generation-jobs/${jobId}/cancel`, { method: "POST" });
}

export function listGenerationResults(jobId: string): Promise<GenerationResult[]> {
  return request<GenerationResult[]>(`/generation-jobs/${jobId}/results`);
}

export function acceptGenerationResult(resultId: string): Promise<{ version_id: string }> {
  return request<{ version_id: string }>(`/generation-results/${resultId}/accept`, {
    method: "POST",
  });
}

