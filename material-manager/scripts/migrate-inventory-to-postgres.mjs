import { readFile } from "node:fs/promises";
import path from "node:path";

import { sql } from "@vercel/postgres";

const inventoryStateId = 1;
const dataFilePath = path.join(process.cwd(), "data", "inventory.json");

function requirePostgresConfig() {
  if (
    !process.env.POSTGRES_URL &&
    !process.env.POSTGRES_URL_NON_POOLING &&
    !process.env.POSTGRES_PRISMA_URL
  ) {
    throw new Error("POSTGRES_URL 系の環境変数が未設定です。");
  }
}

async function loadInventoryData() {
  const content = await readFile(dataFilePath, "utf8");
  const parsed = JSON.parse(content);

  if (!parsed || typeof parsed !== "object") {
    throw new Error("inventory.json の内容が不正です。");
  }

  return parsed;
}

async function migrate() {
  requirePostgresConfig();

  const data = await loadInventoryData();

  await sql`
    CREATE TABLE IF NOT EXISTS inventory_state (
      id INTEGER PRIMARY KEY,
      data JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `;

  await sql`
    INSERT INTO inventory_state (id, data, updated_at)
    VALUES (${inventoryStateId}, ${JSON.stringify(data)}::jsonb, NOW())
    ON CONFLICT (id)
    DO UPDATE SET
      data = EXCLUDED.data,
      updated_at = EXCLUDED.updated_at
  `;

  console.log("inventory.json を Postgres に移行しました。");
}

migrate().catch((error) => {
  console.error(error instanceof Error ? error.message : "移行に失敗しました。");
  process.exitCode = 1;
});