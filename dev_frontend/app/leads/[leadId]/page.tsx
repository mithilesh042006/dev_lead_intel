import { notFound } from "next/navigation";

import SavedLeadView from "./SavedLeadView";

// `params` is a Promise in Next 16, so this stays a Server Component and hands
// the resolved id to the client view.
export default async function SavedLeadPage(props: PageProps<"/leads/[leadId]">) {
  const { leadId } = await props.params;

  // lead_id is a 12-character hex digest; anything else cannot exist.
  if (!/^[0-9a-f]{12}$/.test(leadId)) {
    notFound();
  }

  return <SavedLeadView leadId={leadId} />;
}
