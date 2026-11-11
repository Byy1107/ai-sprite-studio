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

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, { signal });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}

