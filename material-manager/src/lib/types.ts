export type LogKind = "addition" | "usage";

export type GlobalNotificationSettings = {
  emailEnabled: boolean;
  commonEmails: string[];
  forwardEmails: string[];
  lineWorksEnabled: boolean;
  lineWorksWebhookUrl: string;
};

export type Material = {
  id: string;
  name: string;
  category: string;
  location: string;
  unit: string;
  quantity: number;
  threshold: number | null;
  notes: string;
  createdAt: string;
  updatedAt: string;
  lastAlertAt: string | null;
  lastAlertQuantity: number | null;
};

export type InventoryLog = {
  id: string;
  materialId: string;
  materialName: string;
  kind: LogKind;
  quantity: number;
  actor: string;
  note: string;
  createdAt: string;
  resultingQuantity: number;
};

export type InventoryData = {
  materials: Material[];
  additionLogs: InventoryLog[];
  usageLogs: InventoryLog[];
  notificationSettings: GlobalNotificationSettings;
  lastUpdatedAt: string;
};

export type InventorySnapshot = InventoryData & {
  totals: {
    materialCount: number;
    quantitySum: number;
    lowStockCount: number;
  };
};

export type CreateMaterialInput = {
  name: string;
  category: string;
  location: string;
  unit: string;
  quantity: number;
  threshold: number | null;
  notes: string;
};

export type AdjustMaterialInput = {
  id: string;
  delta: number;
  actor: string;
  note: string;
};

export type UpdateAlertInput = {
  id: string;
  threshold: number | null;
};

export type UpdateGlobalNotificationInput = {
  emailEnabled: boolean;
  commonEmails: string[];
  forwardEmails: string[];
  lineWorksEnabled: boolean;
  lineWorksWebhookUrl: string;
};