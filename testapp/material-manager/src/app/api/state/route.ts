import { NextResponse } from "next/server";

import { getInventorySnapshot } from "../../../lib/store";

export const runtime = "nodejs";

export async function GET() {
  const snapshot = await getInventorySnapshot();
  return NextResponse.json(snapshot);
}