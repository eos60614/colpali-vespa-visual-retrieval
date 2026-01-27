"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProjects } from "@/lib/hooks/use-projects";
import { useSessionStore } from "@/stores/session-store";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const { projects, loading } = useProjects();
  const setProject = useSessionStore((s) => s.setProject);

  useEffect(() => {
    if (projectId) {
      setProject(projectId);
    }
  }, [projectId, setProject]);

  const handleSelectProject = (id: string) => {
    setProject(id);
    router.push(`/projects/${id}/search`);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        projects={projects}
        selectedProjectId={projectId}
        onSelectProject={handleSelectProject}
      />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar projectId={projectId} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
