import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/query-state";

export function ModulePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-4">
      <PageHeader title={title} description={description} />
      <Card>
        <EmptyState
          title={`${title} module is being connected`}
          description="The API layer for this module is ready; the workspace screens are being built next."
        />
      </Card>
    </div>
  );
}
