import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../lib/api";
import { ProjectBrowser } from "../features/projects/ProjectBrowser";

type StatusCardProps = {
  label: string;
  detail: string;
  state: "ready" | "waiting" | "unavailable";
};

function StatusCard({ label, detail, state }: StatusCardProps) {
  return (
    <article className="status-card">
      <div className="status-card__heading">
        <span className={`status-dot status-dot--${state}`} aria-hidden="true" />
        <h2>{label}</h2>
      </div>
      <p>{detail}</p>
      <span className="status-card__state">{state}</span>
    </article>
  );
}

export function DashboardPage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: 30_000,
  });

  const health = healthQuery.data;
  const backendReady = health?.status === "ok";

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Local production workspace</p>
          <h1>AI Sprite Studio</h1>
          <p className="hero__copy">
            An offline-first home for crisp micro-pixel and 8-bit game assets.
          </p>
        </div>
        <div className="build-tag">Sprint 3 · Pixel editor</div>
      </header>

      <section className="notice" aria-label="Sprint status">
        <strong>Manual pixel editor active.</strong>
        <span>
          Pixel editing and version publishing are ready. Animation and AI remain disabled.
        </span>
      </section>

      <ProjectBrowser />

      <section className="status-grid" aria-label="System status">
        <StatusCard label="Studio UI" detail="React workspace is running locally." state="ready" />
        <StatusCard
          label="Backend API"
          detail={
            backendReady
              ? `${health.service} ${health.version} is healthy.`
              : healthQuery.isError
                ? "Start the FastAPI service on port 8000."
                : "Checking the local API…"
          }
          state={backendReady ? "ready" : healthQuery.isError ? "unavailable" : "waiting"}
        />
        <StatusCard
          label="Local workspace"
          detail="Project storage and CRUD are configured locally."
          state={healthQuery.data?.workspace_configured ? "ready" : "waiting"}
        />
        <StatusCard
          label="ComfyUI adapter"
          detail="Endpoint configuration is reserved; generation is not implemented yet."
          state="waiting"
        />
      </section>

      <footer className="footer-note">
        <span>Offline-first</span>
        <span>Windows-focused</span>
        <span>No model downloads</span>
      </footer>
    </main>
  );
}
