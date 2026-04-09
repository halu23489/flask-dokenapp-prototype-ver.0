import { NextRequest, NextResponse } from "next/server";

import { buildInventoryFileName } from "../../../../lib/inventory-file-name";
import { buildInventoryWorkbookBuffer } from "../../../../lib/inventory-export";
import { getInventorySnapshot } from "../../../../lib/store";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const format = request.nextUrl.searchParams.get("format") ?? "xlsx";

  if (format !== "xlsx") {
    return NextResponse.json(
      {
        error: "現在は画像とExcel出力のみ対応しています。",
      },
      { status: 400 },
    );
  }

  const snapshot = await getInventorySnapshot();

  const buffer = buildInventoryWorkbookBuffer(snapshot);
  const fileName = buildInventoryFileName("xlsx");
  return new NextResponse(buffer, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
    },
  });
}