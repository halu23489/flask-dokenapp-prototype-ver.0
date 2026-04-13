import "server-only";

import { promises as fs } from "node:fs";
import path from "node:path";

import fontkit from "@pdf-lib/fontkit";
import { PDFDocument, rgb } from "pdf-lib";
import * as XLSX from "xlsx";

import type { InventorySnapshot } from "./types";

function buildInventoryRows(snapshot: InventorySnapshot) {
  return snapshot.materials.map((material) => ({
    資材名: material.name,
    在庫数量: `${material.quantity}${material.unit}`,
  }));
}

export function buildInventoryWorkbookBuffer(snapshot: InventorySnapshot) {
  const workbook = XLSX.utils.book_new();
  const sheet = XLSX.utils.json_to_sheet(buildInventoryRows(snapshot));

  XLSX.utils.book_append_sheet(workbook, sheet, "資材数量表");
  return XLSX.write(workbook, { type: "buffer", bookType: "xlsx" });
}

async function loadJapaneseFontBytes() {
  const candidatePaths = [
    path.join(
      /* turbopackIgnore: true */ process.cwd(),
      "node_modules",
      "@fontsource",
      "noto-sans-jp",
      "files",
      "noto-sans-jp-japanese-400-normal.woff",
    ),
  ];

  if (process.platform === "win32") {
    candidatePaths.unshift(path.join("C:", "Windows", "Fonts", "msgothic.ttc"));
  }

  for (const fontPath of candidatePaths) {
    try {
      await fs.access(fontPath);
      return fs.readFile(fontPath);
    } catch {
      // Try the next fallback font path.
    }
  }

  throw new Error("Japanese font file not found for PDF export.");
}

export async function buildInventoryPdfBuffer(snapshot: InventorySnapshot) {
  const pdf = await PDFDocument.create();
  pdf.registerFontkit(fontkit);

  const fontBytes = await loadJapaneseFontBytes();
  const font = await pdf.embedFont(fontBytes);
  const page = pdf.addPage([842, 595]);

  page.drawText("松戸ヤード資材数量表", {
    x: 40,
    y: 548,
    size: 18,
    font,
    color: rgb(0.08, 0.21, 0.16),
  });
  page.drawText(`出力日時: ${new Date().toLocaleString("ja-JP")}`, {
    x: 40,
    y: 525,
    size: 10,
    font,
  });

  let y = 490;
  page.drawText("資材名", { x: 40, y, size: 11, font });
  page.drawText("在庫数量", { x: 500, y, size: 11, font });

  for (const material of snapshot.materials.slice(0, 24)) {
    y -= 18;
    page.drawText(material.name.slice(0, 40), { x: 40, y, size: 10, font });
    page.drawText(`${material.quantity}${material.unit}`, { x: 500, y, size: 10, font });
  }

  return Buffer.from(await pdf.save());
}