import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProject,
  deleteProject,
  listProjects,
  openProject,
  type Project,
} from "../../lib/api";
import { AssetLibrary } from "../assets/AssetLibrary";

function ProjectCard({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
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
      {isOpen ? <AssetLibrary projectId={project.id} /> : null}
    </article>
  );
}

export function ProjectBrowser() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: ({ signal }) => listProjects(signal) });
  const createMutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      setShowForm(false);
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

      {projectsQuery.isPending ? <p className="empty-state">Loading local projects…</p> : null}
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
