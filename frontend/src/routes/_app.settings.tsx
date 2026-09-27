import { createFileRoute } from "@tanstack/react-router";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const Route = createFileRoute("/_app/settings")({
  head: () => ({
    meta: [
      { title: "Settings — Minitally ERP" },
      { name: "description", content: "Company profile, users and audit trail." },
      { property: "og:title", content: "Settings — Minitally ERP" },
      { property: "og:description", content: "Company profile, users and audit trail." },
    ],
  }),
  component: () => <ModulePlaceholder title="Settings" description="Company profile, users and audit trail." />,
});
