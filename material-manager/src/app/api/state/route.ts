import { NextResponse } from "next/server";

import { getInventorySnapshot } from "../../../lib/store";

export const runtime = "nodejs";

export async function GET() {
  try {
    const snapshot = await getInventorySnapshot();
    return NextResponse.json(snapshot);
  } catch (error) {
    const message = error instanceof Error ? error.message : "在庫データの取得に失敗しました。";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}