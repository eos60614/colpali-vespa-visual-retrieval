"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useProjects } from "@/lib/hooks/use-projects";
import { useSessionStore } from "@/stores/session-store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function LandingPage() {
  const router = useRouter();
  const { projects, loading, error } = useProjects();
  const selectedProjectId = useSessionStore((s) => s.selectedProjectId);
  const setProject = useSessionStore((s) => s.setProject);

  // Auto-redirect to last-used project
  useEffect(() => {
    if (!loading && selectedProjectId && projects.some((p) => p.id === selectedProjectId)) {
      router.push(`/projects/${selectedProjectId}/search`);
    }
  }, [loading, selectedProjectId, projects, router]);

  const handleSelect = (id: string) => {
    setProject(id);
    router.push(`/projects/${id}/search`);
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-xl space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold">CoPoly</h1>
          <p className="text-muted-foreground">
            Visual document retrieval for construction projects
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Select a Project</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : projects.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No active projects found in Procore.
              </p>
            ) : (
              <div className="space-y-1 max-h-[60vh] overflow-y-auto">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => handleSelect(project.id)}
                    className="w-full text-left px-4 py-3 rounded-md border hover:bg-accent transition-colors"
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="font-medium text-sm">
                        {project.project_number ? `${project.project_number} -` : ""}
                      </span>
                      <span className="text-sm">{project.name}</span>
                    </div>
                    <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                      <span>{project.document_count} docs</span>
                      {project.document_counts.Drawing > 0 && (
                        <span>{project.document_counts.Drawing} drawings</span>
                      )}
                      {project.document_counts.Photo > 0 && (
                        <span>{project.document_counts.Photo} photos</span>
                      )}
                      {project.document_counts.RFI > 0 && (
                        <span>{project.document_counts.RFI} RFIs</span>
                      )}
                      {project.city && (
                        <span>{project.city}{project.state_code ? `, ${project.state_code}` : ""}</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
