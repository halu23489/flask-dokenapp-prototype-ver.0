import InventoryApp from "@/app/components/inventory-app";
import { getInventorySnapshot } from "../lib/store";

export default async function Home() {
  const snapshot = await getInventorySnapshot();

  return (
    <InventoryApp initialSnapshot={snapshot} />
  );
}
