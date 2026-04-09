import { NextRequest, NextResponse } from "next/server";
import * as XLSX from "xlsx";

import { getInventorySnapshot } from "../../../../lib/store";

export const runtime = "nodejs";

function rowsForLogs(logs: Awaited<ReturnType<typeof getInventorySnapshot>>["additionLogs"]) {
  return logs.map((log) => ({
    時刻: log.createdAt,
    資材名: log.materialName,
    種別: log.kind === "addition" ? "追加" : "使用",
    数量: log.quantity,
    実行者: log.actor,
    メモ: log.note,
    実行後在庫: log.resultingQuantity,
  }));
}

export async function GET(request: NextRequest) {
  const type = request.nextUrl.searchParams.get("type") ?? "all";
  const snapshot = await getInventorySnapshot();
  const workbook = XLSX.utils.book_new();

  if (type === "addition" || type === "all") {
    XLSX.utils.book_append_sheet(
      workbook,
      XLSX.utils.json_to_sheet(rowsForLogs(snapshot.additionLogs)),
      "追加ログ",
    );
  }

  if (type === "usage" || type === "all") {
    XLSX.utils.book_append_sheet(
      workbook,
      XLSX.utils.json_to_sheet(rowsForLogs(snapshot.usageLogs)),
      "使用ログ",
    );
  }

  const buffer = XLSX.write(workbook, { type: "buffer", bookType: "xlsx" });

  return new NextResponse(buffer, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": 'attachment; filename="inventory-logs.xlsx"',
    },
  });
}