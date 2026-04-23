import { NextResponse } from "next/server";

import { sendBroadcastNotification, sendLowStockAlert } from "../../../lib/notify";
import {
  adjustMaterial,
  createMaterial,
  deleteMaterial,
  getInventorySnapshot,
  hasNotificationChannel,
  markAlertSent,
  resolveForwardNotificationEmails,
  resolveNotificationEmails,
  shouldSendLowStockAlert,
  updateAlertSettings,
  updateGlobalNotificationSettings,
} from "../../../lib/store";

export const runtime = "nodejs";

function normalizeNumericValue(value: unknown) {
  if (typeof value === "number") {
    return value;
  }

  if (typeof value !== "string") {
    return Number(value ?? 0);
  }

  const normalized = value
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/[‐‑‒–—―ー]/g, "-")
    .replace(/[，、]/g, ",")
    .replace(/\s+/g, "")
    .replace(/,/g, "");

  return Number(normalized || 0);
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      action:
        | "create"
        | "adjust"
        | "delete"
        | "update-alert"
        | "update-global-alert"
        | "broadcast-notification";
      payload: Record<string, unknown>;
    };

    if (body.action === "create") {
      const snapshot = await createMaterial({
        name: String(body.payload.name ?? ""),
        category: String(body.payload.category ?? ""),
        location: String(body.payload.location ?? ""),
        unit: String(body.payload.unit ?? "個"),
        quantity: normalizeNumericValue(body.payload.quantity),
        threshold:
          body.payload.threshold === null || body.payload.threshold === ""
            ? null
            : normalizeNumericValue(body.payload.threshold),
        notes: String(body.payload.notes ?? ""),
      });

      return NextResponse.json({ snapshot, message: "資材を追加しました。" });
    }

    if (body.action === "adjust") {
      const result = await adjustMaterial({
        id: String(body.payload.id ?? ""),
        delta: normalizeNumericValue(body.payload.delta),
        actor: String(body.payload.actor ?? ""),
        note: String(body.payload.note ?? ""),
      });

      let message = "在庫を更新しました。";
      const settings = result.snapshot.notificationSettings;

      if (shouldSendLowStockAlert(result.material, settings)) {
        const recipients = resolveNotificationEmails(settings);
        const forwardRecipients = resolveForwardNotificationEmails(settings);
        message = await sendLowStockAlert(
          result.material,
          result.snapshot,
          settings,
          recipients,
          forwardRecipients,
        );
        await markAlertSent(result.material.id, result.material.quantity);

        const refreshedSnapshot = await getInventorySnapshot();
        return NextResponse.json({ snapshot: refreshedSnapshot, message });
      }

      return NextResponse.json({ snapshot: result.snapshot, message });
    }

    if (body.action === "delete") {
      const snapshot = await deleteMaterial(String(body.payload.id ?? ""));
      return NextResponse.json({ snapshot, message: "資材を削除しました。" });
    }

    if (body.action === "update-alert") {
      const result = await updateAlertSettings({
        id: String(body.payload.id ?? ""),
        threshold:
          body.payload.threshold === null || body.payload.threshold === ""
            ? null
            : normalizeNumericValue(body.payload.threshold),
      });

      return NextResponse.json({
        snapshot: result.snapshot,
        message: "通知設定を更新しました。",
      });
    }

    if (body.action === "update-global-alert") {
      const snapshot = await updateGlobalNotificationSettings({
        emailEnabled: Boolean(body.payload.emailEnabled),
        commonEmails: Array.isArray(body.payload.commonEmails)
          ? body.payload.commonEmails.map(String)
          : [],
        forwardEmails: Array.isArray(body.payload.forwardEmails)
          ? body.payload.forwardEmails.map(String)
          : [],
        lineWorksEnabled: Boolean(body.payload.lineWorksEnabled),
        lineWorksWebhookUrl: String(body.payload.lineWorksWebhookUrl ?? ""),
      });

      return NextResponse.json({
        snapshot,
        message: "共通通知設定を更新しました。",
      });
    }

    if (body.action === "broadcast-notification") {
      const snapshot = await getInventorySnapshot();

      if (!hasNotificationChannel(snapshot.notificationSettings)) {
        return NextResponse.json(
          { error: "共通通知先が未設定です。" },
          { status: 400 },
        );
      }

      const message = await sendBroadcastNotification(snapshot, snapshot.notificationSettings);
      return NextResponse.json({ snapshot, message });
    }

    return NextResponse.json({ error: "不正な操作です。" }, { status: 400 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "処理に失敗しました。";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}