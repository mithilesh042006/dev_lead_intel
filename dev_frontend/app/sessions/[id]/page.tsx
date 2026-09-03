import { notFound } from "next/navigation";

import SessionDetailView from "./SessionDetailView";

// `params` is a Promise in Next 16, so this stays a Server Component and hands
// the resolved id to the client view.
export default async function SessionPage(props: PageProps<"/sessions/[id]">) {
  const { id } = await props.params;
  const numericId = Number(id);

  if (!Number.isInteger(numericId) || numericId < 1) {
    notFound();
  }

  return <SessionDetailView id={numericId} />;
}
