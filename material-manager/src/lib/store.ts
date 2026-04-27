import "server-only";

import { promises as fs } from "node:fs";
import path from "node:path";

import { createPool } from "@vercel/postgres";

import type {
  AdjustMaterialInput,
  CreateMaterialInput,
  GlobalNotificationSettings,
  InventoryData,
  InventoryLog,
  InventorySnapshot,
  Material,
  UpdateAlertInput,
  UpdateGlobalNotificationInput,
} from "./types";

const bundledDataFilePath = path.join(process.cwd(), "data", "inventory.json");
const localDataFilePath = process.env.VERCEL
  ? path.join("/tmp", "material-manager", "inventory.json")
  : bundledDataFilePath;
const isVercelRuntime = Boolean(process.env.VERCEL);
const inventoryStateId = 1;
const postgresUrl = process.env.POSTGRES_URL?.trim() || "";
const directConnectionString = postgresUrl;
const activeConnectionVar = "POSTGRES_URL";
const hasPostgresConfig = Boolean(
  postgresUrl,
);
const postgresPool = hasPostgresConfig
  ? createPool({ connectionString: directConnectionString })
  : null;

let postgresReadyPromise: Promise<void> | null = null;

function assertPersistentStoreAvailable() {
  if (isVercelRuntime && !hasPostgresConfig) {
    throw new Error(
      "本番環境でPostgreSQL接続が未設定です。POSTGRES_URL を確認してください。",
    );
  }
}

function resolveConnectionTarget(connectionString: string): string {
  try {
    const url = new URL(connectionString);
    const port = url.port || "5432";
    return `${url.hostname}:${port}${url.pathname}`;
  } catch {
    return "接続文字列を解析できません";
  }
}

function buildPostgresErrorMessage(action: "読み取り" | "書き込み", error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error);
  const target = resolveConnectionTarget(directConnectionString);
  return `PostgreSQL${action}に失敗しました。使用変数: ${activeConnectionVar} / 接続先: ${target} / 詳細: ${detail}`;
}

const now = () => new Date().toISOString();

async function runSql<T extends Record<string, unknown> = Record<string, unknown>>(
  strings: TemplateStringsArray,
  ...values: unknown[]
): Promise<{ rows: T[]; rowCount: number }> {
  if (!postgresPool) {
    throw new Error("PostgreSQL接続文字列が未設定です。");
  }

  // テンプレートリテラルのパーツからパラメータ化クエリを構築する。
  // 型制約由来のビルドエラーを回避するため、query() を直接呼ぶ。
  const text = strings.reduce(
    (acc, part, i) => acc + part + (i < values.length ? `$${i + 1}` : ""),
    ""
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const result = await (postgresPool as any).query(text, values) as {
    rows: unknown[];
    rowCount: number | null;
  };
  return {
    rows: (result.rows ?? []) as T[],
    rowCount: result.rowCount ?? 0,
  };
}

const defaultNotificationSettings = (): GlobalNotificationSettings => ({
  emailEnabled: false,
  commonEmails: [],
  forwardEmails: [],
  lineWorksEnabled: false,
  lineWorksWebhookUrl: "",
});

function normalizeMaterial(raw: Partial<Material>): Material {
  return {
    id: raw.id ?? crypto.randomUUID(),
    name: (raw.name ?? "").trim(),
    category: (raw.category ?? "未分類").trim() || "未分類",
    location: (raw.location ?? "棚未設定").trim() || "棚未設定",
    unit: (raw.unit ?? "個").trim() || "個",
    quantity: Math.max(0, Math.trunc(Number(raw.quantity ?? 0))),
    threshold:
      raw.threshold === undefined ? null : normalizeThreshold(raw.threshold ?? null),
    notes: (raw.notes ?? "").trim(),
    createdAt: raw.createdAt ?? now(),
    updatedAt: raw.updatedAt ?? now(),
    lastAlertAt: raw.lastAlertAt ?? null,
    lastAlertQuantity:
      raw.lastAlertQuantity === undefined || raw.lastAlertQuantity === null
        ? null
        : Math.max(0, Math.trunc(Number(raw.lastAlertQuantity))),
  };
}

function normalizeInventoryData(raw?: Partial<InventoryData>): InventoryData {
  return {
    materials: [...(raw?.materials ?? [])]
      .map((material) => normalizeMaterial(material))
      .sort((left, right) => left.name.localeCompare(right.name, "ja")),
    additionLogs: raw?.additionLogs ?? [],
    usageLogs: raw?.usageLogs ?? [],
    notificationSettings: sanitizeNotificationSettings(raw?.notificationSettings),
    lastUpdatedAt: raw?.lastUpdatedAt ?? now(),
  };
}

function parseStoredInventoryData(raw: unknown): Partial<InventoryData> {
  if (!raw) {
    return {};
  }

  if (typeof raw === "string") {
    return JSON.parse(raw) as Partial<InventoryData>;
  }

  return raw as Partial<InventoryData>;
}

function sanitizeEmails(raw: string[]): string[] {
  return raw
    .map((value) => value.trim())
    .filter(Boolean)
    .filter((value, index, list) => list.indexOf(value) === index);
}

function sanitizeNotificationSettings(
  raw?: Partial<GlobalNotificationSettings>,
): GlobalNotificationSettings {
  const fallback = defaultNotificationSettings();

  return {
    emailEnabled: raw?.emailEnabled ?? fallback.emailEnabled,
    commonEmails: sanitizeEmails(raw?.commonEmails ?? fallback.commonEmails),
    forwardEmails: sanitizeEmails(raw?.forwardEmails ?? fallback.forwardEmails),
    lineWorksEnabled: raw?.lineWorksEnabled ?? fallback.lineWorksEnabled,
    lineWorksWebhookUrl: (raw?.lineWorksWebhookUrl ?? fallback.lineWorksWebhookUrl).trim(),
  };
}

function normalizeThreshold(value: number | null): number | null {
  if (value === null || Number.isNaN(value)) {
    return null;
  }

  return Math.max(0, Math.trunc(value));
}

const createMaterialRecord = (
  partial: Omit<CreateMaterialInput, "quantity"> & {
    name: string;
    quantity: number;
  },
): Material => ({
  id: crypto.randomUUID(),
  name: partial.name.trim(),
  category: partial.category.trim() || "未分類",
  location: partial.location.trim() || "棚未設定",
  unit: partial.unit.trim() || "個",
  quantity: Math.max(0, Math.trunc(partial.quantity)),
  threshold: partial.threshold,
  notes: partial.notes.trim(),
  createdAt: now(),
  updatedAt: now(),
  lastAlertAt: null,
  lastAlertQuantity: null,
});

const defaultData = (): InventoryData => {
  const materials = [
    createMaterialRecord({
      name: "M10ボルト",
      category: "締結材",
      location: "A-01",
      unit: "本",
      quantity: 180,
      threshold: 50,
      notes: "標準在庫",
    }),
    createMaterialRecord({
      name: "安全手袋",
      category: "消耗品",
      location: "B-02",
      unit: "双",
      quantity: 36,
      threshold: 12,
      notes: "現場配布用",
    }),
    createMaterialRecord({
      name: "コンクリートアンカー",
      category: "施工材",
      location: "C-05",
      unit: "箱",
      quantity: 14,
      threshold: 5,
      notes: "1箱50本入り",
    }),
  ];

  return {
    materials,
    additionLogs: [],
    usageLogs: [],
    notificationSettings: defaultNotificationSettings(),
    lastUpdatedAt: now(),
  };
};

async function ensureStore(): Promise<void> {
  assertPersistentStoreAvailable();

  if (hasPostgresConfig) {
    return;
  }

  try {
    await fs.access(localDataFilePath);
  } catch {
    const seed = (await readLocalSeedData()) ?? defaultData();
    await fs.mkdir(path.dirname(localDataFilePath), { recursive: true });
    await fs.writeFile(localDataFilePath, JSON.stringify(seed, null, 2), "utf8");
  }
}

async function readLocalSeedData(): Promise<InventoryData | null> {
  try {
    const content = await fs.readFile(bundledDataFilePath, "utf8");
    const parsed = JSON.parse(content) as Partial<InventoryData>;
    const normalized = normalizeInventoryData(parsed);

    if (
      normalized.materials.length > 0 ||
      normalized.additionLogs.length > 0 ||
      normalized.usageLogs.length > 0
    ) {
      return normalized;
    }
  } catch {
    return null;
  }

  return null;
}

async function ensurePostgresStore(): Promise<void> {
  if (!hasPostgresConfig) {
    return;
  }

  if (!postgresReadyPromise) {
    postgresReadyPromise = (async () => {
      await runSql`
        CREATE TABLE IF NOT EXISTS inventory_state (
          id INTEGER PRIMARY KEY,
          data JSONB NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
      `;

      const existing = await runSql<{ data: unknown }>`
        SELECT data
        FROM inventory_state
        WHERE id = ${inventoryStateId}
        LIMIT 1
      `;

      if (existing.rowCount === 0) {
        const seed = defaultData();
        await runSql`
          INSERT INTO inventory_state (id, data, updated_at)
          VALUES (${inventoryStateId}, ${JSON.stringify(seed)}::jsonb, NOW())
        `;
      }
    })().catch((error) => {
      postgresReadyPromise = null;
      throw error;
    });
  }

  await postgresReadyPromise;
}

async function readStore(): Promise<InventoryData> {
  if (hasPostgresConfig) {
    try {
      await ensurePostgresStore();
      const result = await runSql<{ data: unknown }>`
        SELECT data
        FROM inventory_state
        WHERE id = ${inventoryStateId}
        LIMIT 1
      `;

      return normalizeInventoryData(parseStoredInventoryData(result.rows[0]?.data));
    } catch (error) {
      if (isVercelRuntime) {
        throw new Error(buildPostgresErrorMessage("読み取り", error));
      }
      console.error("PostgreSQL読み取りに失敗したためローカルストアへフォールバックします", error);
    }
  }

  await ensureStore();
  const content = await fs.readFile(localDataFilePath, "utf8");
  const parsed = JSON.parse(content) as Partial<InventoryData>;

  return normalizeInventoryData(parsed);
}

async function writeStore(data: InventoryData): Promise<void> {
  const nextData = { ...data, lastUpdatedAt: now() };

  if (hasPostgresConfig) {
    try {
      await ensurePostgresStore();
      await runSql`
        INSERT INTO inventory_state (id, data, updated_at)
        VALUES (${inventoryStateId}, ${JSON.stringify(nextData)}::jsonb, NOW())
        ON CONFLICT (id)
        DO UPDATE SET
          data = EXCLUDED.data,
          updated_at = EXCLUDED.updated_at
      `;
      return;
    } catch (error) {
      if (isVercelRuntime) {
        throw new Error(buildPostgresErrorMessage("書き込み", error));
      }
      console.error("PostgreSQL書き込みに失敗したためローカルストアへフォールバックします", error);
    }
  }

  await ensureStore();
  await fs.writeFile(
    localDataFilePath,
    JSON.stringify(nextData, null, 2),
    "utf8",
  );
}

function toSnapshot(data: InventoryData): InventorySnapshot {
  const quantitySum = data.materials.reduce((sum, material) => sum + material.quantity, 0);
  const lowStockCount = data.materials.filter(
    (material) => material.threshold !== null && material.quantity <= material.threshold,
  ).length;

  return {
    ...data,
    totals: {
      materialCount: data.materials.length,
      quantitySum,
      lowStockCount,
    },
  };
}

function appendLog(data: InventoryData, log: InventoryLog): InventoryData {
  if (log.kind === "addition") {
    return { ...data, additionLogs: [log, ...data.additionLogs] };
  }

  return { ...data, usageLogs: [log, ...data.usageLogs] };
}

export async function getInventorySnapshot(): Promise<InventorySnapshot> {
  try {
    const data = await readStore();
    return toSnapshot(data);
  } catch (error) {
    if (isVercelRuntime) {
      throw error;
    }
    console.error("在庫データの読み込みに失敗したため初期データを返します", error);
    return toSnapshot(defaultData());
  }
}

export async function createMaterial(input: CreateMaterialInput): Promise<InventorySnapshot> {
  const data = await readStore();
  const name = input.name.trim();

  if (!name) {
    throw new Error("資材名を入力してください。");
  }

  if (data.materials.some((material) => material.name === name)) {
    throw new Error("同じ名前の資材がすでに存在します。");
  }

  const createdMaterial = createMaterialRecord({
    ...input,
    name,
    quantity: input.quantity,
    threshold: normalizeThreshold(input.threshold),
  });

  const nextData: InventoryData = {
    ...data,
    materials: [...data.materials, createdMaterial].sort((left, right) =>
      left.name.localeCompare(right.name, "ja"),
    ),
    lastUpdatedAt: now(),
  };

  await writeStore(nextData);
  return toSnapshot(nextData);
}

export async function deleteMaterial(id: string): Promise<InventorySnapshot> {
  const data = await readStore();
  const material = data.materials.find((entry) => entry.id === id);

  if (!material) {
    throw new Error("対象の資材が見つかりません。");
  }

  const nextData: InventoryData = {
    ...data,
    materials: data.materials.filter((entry) => entry.id !== id),
    lastUpdatedAt: now(),
  };

  await writeStore(nextData);
  return toSnapshot(nextData);
}

export async function adjustMaterial(
  input: AdjustMaterialInput,
): Promise<{ snapshot: InventorySnapshot; material: Material }> {
  const data = await readStore();
  const material = data.materials.find((entry) => entry.id === input.id);

  if (!material) {
    throw new Error("対象の資材が見つかりません。");
  }

  const delta = Math.trunc(input.delta);

  if (delta === 0) {
    throw new Error("増減数は1以上で指定してください。");
  }

  const nextQuantity = material.quantity + delta;

  if (nextQuantity < 0) {
    throw new Error("使用数が現在庫を超えています。");
  }

  const updatedMaterial: Material = {
    ...material,
    quantity: nextQuantity,
    updatedAt: now(),
    lastAlertAt:
      material.threshold !== null && nextQuantity > material.threshold ? null : material.lastAlertAt,
    lastAlertQuantity:
      material.threshold !== null && nextQuantity > material.threshold
        ? null
        : material.lastAlertQuantity,
  };

  const nextMaterials = data.materials.map((entry) =>
    entry.id === updatedMaterial.id ? updatedMaterial : entry,
  );

  const log: InventoryLog = {
    id: crypto.randomUUID(),
    materialId: updatedMaterial.id,
    materialName: updatedMaterial.name,
    kind: delta > 0 ? "addition" : "usage",
    quantity: Math.abs(delta),
    actor: input.actor.trim() || "未入力",
    note: input.note.trim(),
    createdAt: now(),
    resultingQuantity: nextQuantity,
  };

  const nextData = appendLog(
    {
      ...data,
      materials: nextMaterials,
      lastUpdatedAt: now(),
    },
    log,
  );

  await writeStore(nextData);

  return {
    snapshot: toSnapshot(nextData),
    material: updatedMaterial,
  };
}

export async function updateAlertSettings(
  input: UpdateAlertInput,
): Promise<{ snapshot: InventorySnapshot; material: Material }> {
  const data = await readStore();
  const material = data.materials.find((entry) => entry.id === input.id);

  if (!material) {
    throw new Error("対象の資材が見つかりません。");
  }

  const threshold = normalizeThreshold(input.threshold);
  const updatedMaterial: Material = {
    ...material,
    threshold,
    updatedAt: now(),
  };

  const nextData: InventoryData = {
    ...data,
    materials: data.materials.map((entry) =>
      entry.id === updatedMaterial.id ? updatedMaterial : entry,
    ),
    lastUpdatedAt: now(),
  };

  await writeStore(nextData);

  return {
    snapshot: toSnapshot(nextData),
    material: updatedMaterial,
  };
}

export async function updateGlobalNotificationSettings(
  input: UpdateGlobalNotificationInput,
): Promise<InventorySnapshot> {
  const data = await readStore();

  const nextData: InventoryData = {
    ...data,
    notificationSettings: sanitizeNotificationSettings(input),
    lastUpdatedAt: now(),
  };

  await writeStore(nextData);
  return toSnapshot(nextData);
}

export function resolveNotificationEmails(
  settings: GlobalNotificationSettings,
): string[] {
  return sanitizeEmails(settings.commonEmails);
}

export function resolveForwardNotificationEmails(
  settings: GlobalNotificationSettings,
): string[] {
  return sanitizeEmails(settings.forwardEmails);
}

export function hasNotificationChannel(settings: GlobalNotificationSettings): boolean {
  const hasEmailChannel =
    settings.emailEnabled &&
    (resolveNotificationEmails(settings).length > 0 ||
      resolveForwardNotificationEmails(settings).length > 0);
  const hasLineWorksChannel =
    settings.lineWorksEnabled &&
    (settings.lineWorksWebhookUrl.trim().length > 0 || Boolean(process.env.LINE_WORKS_WEBHOOK_URL));

  return hasEmailChannel || hasLineWorksChannel;
}

export async function markAlertSent(id: string, quantity: number): Promise<void> {
  const data = await readStore();

  const nextData: InventoryData = {
    ...data,
    materials: data.materials.map((material) =>
      material.id === id
        ? {
            ...material,
            lastAlertAt: now(),
            lastAlertQuantity: quantity,
            updatedAt: now(),
          }
        : material,
    ),
    lastUpdatedAt: now(),
  };

  await writeStore(nextData);
}

export function needsLowStockAlert(material: Material): boolean {
  return material.threshold !== null;
}

export function shouldSendLowStockAlert(
  material: Material,
  settings: GlobalNotificationSettings,
): boolean {
  if (!needsLowStockAlert(material)) {
    return false;
  }

  const threshold = material.threshold;

  if (threshold === null) {
    return false;
  }

  if (material.quantity > threshold) {
    return false;
  }

  if (!hasNotificationChannel(settings)) {
    return false;
  }

  return material.lastAlertQuantity === null || material.quantity < material.lastAlertQuantity;
}
