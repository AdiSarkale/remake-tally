import { createFileRoute } from "@tanstack/react-router";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const Route = createFileRoute("/_app/reports")({
  head: () => ({
    meta: [
      { title: "Reports — Minitally ERP" },
      { name: "description", content: "Manufacturing, inventory and financial reports." },
      { property: "og:title", content: "Reports — Minitally ERP" },
      { property: "og:description", content: "Manufacturing, inventory and financial reports." },
    ],
  }),
  component: () => <ModulePlaceholder title="Reports" description="Manufacturing, inventory and financial reports." />,
});
