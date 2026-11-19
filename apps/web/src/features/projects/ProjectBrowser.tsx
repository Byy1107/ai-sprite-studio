import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  backupProjectUrl,
  clearProjectCache,
  createProject,
  deleteProject,
  inspectProject,
  listProjects,
  openProject,
  restoreProject,
  type Project,
} from "../../lib/api";
import { AssetLibrary } from "../assets/AssetLibrary";
import { GeneratorPanel } from "../generator/GeneratorPanel";

function ProjectCard({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const integrityQuery = useQuery({
    queryKey: ["project-integrity", project.id],
    queryFn: ({ signal }) => inspectProject(project.id, signal),
    enabled: false,
  });
  const openMutation = useMutation({
    mutationFn: () => openProject(project.id),
    onSuccess: () => {
      setIsOpen(true);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(project.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
  const cacheMutation = useMutation({ mutationFn: () => clearProjectCache(project.id) });

  return (
    <article className="project-card">
      <div>
        <p className="project-card__slug">{project.slug}</p>
        <h3>{project.name}</h3>
        <p>{project.description || "No description yet."}</p>
      </div>
      <div className="project-card__actions">
        <button type="button" onClick={() => openMutation.mutate()} disabled={openMutation.isPending}>
          {openMutation.isPending ? "Opening…" : "Open project"}
        </button>
        <button type="button" onClick={() => integrityQuery.refetch()} disabled={integrityQuery.isFetching}>
          {integrityQuery.isFetching ? "Checking files…" : "Check files"}
        </button>
        <a href={backupProjectUrl(project.id)} download={`${project.slug}.zip`}>Download backup</a>
        <button type="button" disabled={cacheMutation.isPending} onClick={() => {
          if (window.confirm(`Permanently clear disposable cache files for ${project.name}? Published assets and trash are retained.`)) cacheMutation.mutate();
        }}>{cacheMutation.isPending ? "Clearing cache…" : "Clear cache"}</button>
        <button
          className="button--danger"
          type="button"
          onClick={() => {
            if (window.confirm(`Move ${project.name} to trash?`)) deleteMutation.mutate();
          }}
          disabled={deleteMutation.isPending}
        >
          Move to trash
        </button>
      </div>
      {openMutation.isError || deleteMutation.isError ? (
        <p className="form-error" role="alert">
          {(openMutation.error ?? deleteMutation.error)?.message}
        </p>
      ) : null}
      {integrityQuery.isError ? <p className="form-error" role="alert">{integrityQuery.error.message}</p> : null}
      {cacheMutation.isError ? <p className="form-error" role="alert">{cacheMutation.error.message}</p> : null}
      {cacheMutation.data ? <p role="status">Removed {cacheMutation.data.removed_files} cache files.</p> : null}
      {integrityQuery.data?.status === "ok" ? <p role="status">Project files are present.</p> : null}
      {integrityQuery.data?.status === "issues" ? (
        <div role="alert" className="form-error">
          <p>{integrityQuery.data.issues.length} missing or unsafe project files. No files were changed.</p>
          <ul>{integrityQuery.data.issues.map((issue) => (
            <li key={`${issue.kind}:${issue.reference_id}:${issue.path}`}>{issue.kind}: {issue.path}</li>
          ))}</ul>
        </div>
      ) : null}
      {isOpen ? (
        <>
          <GeneratorPanel projectId={project.id} />
          <AssetLibrary projectId={project.id} />
        </>
      ) : null}
    </article>
  );
}

export function ProjectBrowser() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [showRestore, setShowRestore] = useState(false);
  const [backupFile, setBackupFile] = useState<File | null>(null);
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: ({ signal }) => listProjects(signal) });
  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const restoreMutation = useMutation({
    mutationFn: restoreProject,
    onSuccess: () => {
      setShowRestore(false);
      setBackupFile(null);
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    createMutation.mutate({
      name: String(form.get("name") ?? ""),
      description: String(form.get("description") ?? ""),
    });
  }

  return (
    <section className="projects" aria-labelledby="projects-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Project workspace</p>
          <h2 id="projects-title">Your local projects</h2>
        </div>
        <button type="button" onClick={() => setShowForm((visible) => !visible)}>
          {showForm ? "Cancel" : "New project"}
        </button>
        <button type="button" onClick={() => setShowRestore((visible) => !visible)}>
          {showRestore ? "Cancel restore" : "Restore backup"}
        </button>
      </div>

      {showForm ? (
        <form className="project-form" onSubmit={submit}>
          <label>
            Project name
            <input name="name" required maxLength={120} autoFocus />
          </label>
          <label>
            Description
            <textarea name="description" maxLength={2000} rows={3} />
          </label>
          {createMutation.isError ? <p className="form-error" role="alert">{createMutation.error.message}</p> : null}
          <button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating…" : "Create project"}
          </button>
        </form>
      ) : null}
      {showRestore ? (
        <form className="project-form" onSubmit={(event) => {
          event.preventDefault();
          if (backupFile) restoreMutation.mutate(backupFile);
        }}>
          <p>Restore a local ZIP backup into an empty workspace. Existing projects are never replaced.</p>
          <label>Backup ZIP <input name="backup" type="file" accept=".zip,application/zip" onChange={(event) => setBackupFile(event.target.files?.[0] ?? null)} /></label>
          {restoreMutation.isError ? <p className="form-error" role="alert">{restoreMutation.error.message}</p> : null}
          <button type="submit" disabled={restoreMutation.isPending || !backupFile}>
            {restoreMutation.isPending ? "Restoring…" : "Restore project"}
          </button>
        </form>
      ) : null}

      {projectsQuery.isPending ? <p className="empty-state" role="status">Loading local projects…</p> : null}
      {projectsQuery.isError ? <p className="form-error" role="alert">{projectsQuery.error.message}</p> : null}
      {projectsQuery.data?.length === 0 ? (
        <div className="empty-state">
          <strong>No projects yet.</strong>
          <span>Create a private workspace stored only on this computer.</span>
        </div>
      ) : null}
      <div className="project-grid">
        {projectsQuery.data?.map((project) => <ProjectCard key={project.id} project={project} />)}
      </div>
    </section>
  );
}
