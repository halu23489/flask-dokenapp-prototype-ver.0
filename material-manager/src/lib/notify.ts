import nodemailer from "nodemailer";

import { buildInventoryFileName } from "./inventory-file-name";
import {
  buildInventoryWorkbookBuffer,
} from "./inventory-export";
import type { GlobalNotificationSettings, InventorySnapshot, Material } from "./types";

function getTransporter() {
  const host = process.env.SMTP_HOST;
  const port = Number(process.env.SMTP_PORT ?? "587");
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;

  if (!host || !user || !pass) {
    return null;
  }

  return nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: {
      user,
      pass,
    },
  });
}

function resolveLineWorksWebhookUrl(settings: GlobalNotificationSettings): string {
  return settings.lineWorksWebhookUrl.trim() || process.env.LINE_WORKS_WEBHOOK_URL || "";
}

async function sendEmailMessage(
  subject: string,
  text: string,
  recipients: string[],
  snapshot?: InventorySnapshot,
) {
  const transporter = getTransporter();

  if (!transporter) {
    return "メールはSMTP未設定のためスキップしました。";
  }

  if (recipients.length === 0) {
    return "メール送信先が未設定のためスキップしました。";
  }

  const from = process.env.MAIL_FROM ?? process.env.SMTP_USER;

  await transporter.sendMail({
    from,
    to: recipients.join(","),
    subject,
    text,
    attachments: snapshot
      ? [
          {
            filename: buildInventoryFileName("xlsx"),
            content: buildInventoryWorkbookBuffer(snapshot),
            contentType:
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          },
        ]
      : [],
  });

  return `メール送信: ${recipients.length}件`;
}

async function sendLineWorksMessage(text: string, settings: GlobalNotificationSettings) {
  const webhookUrl = resolveLineWorksWebhookUrl(settings);

  if (!webhookUrl || !settings.lineWorksEnabled) {
    return "LINE WORKSは未設定のためスキップしました。";
  }

  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      content: {
        type: "text",
        text,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`LINE WORKS送信に失敗しました: ${response.status}`);
  }

  return "LINE WORKS送信: 1件";
}

function buildLowStockMessage(material: Material): string {
  return [
    `在庫アラート: ${material.name}`,
    `現在庫: ${material.quantity}${material.unit}`,
    `下限値: ${material.threshold ?? "未設定"}${material.unit}`,
    `更新日時: ${new Date(material.updatedAt).toLocaleString("ja-JP")}`,
  ].join("\n");
}

function buildBroadcastMessage(snapshot: InventorySnapshot): string {
  const lines = snapshot.materials.slice(0, 30).map(
    (material) => `・${material.name}: ${material.quantity}${material.unit} / ${material.location}`,
  );

  return [
    "資材一斉通知",
    `資材数: ${snapshot.totals.materialCount}件`,
    `総在庫: ${snapshot.totals.quantitySum}`,
    `要補充: ${snapshot.totals.lowStockCount}件`,
    `更新日時: ${new Date(snapshot.lastUpdatedAt).toLocaleString("ja-JP")}`,
    "",
    ...lines,
  ].join("\n");
}

export async function sendLowStockAlert(
  material: Material,
  snapshot: InventorySnapshot,
  settings: GlobalNotificationSettings,
  recipients: string[],
): Promise<string> {
  const subject = `在庫アラート: ${material.name}`;
  const text = buildLowStockMessage(material);
  const results: string[] = [];

  if (settings.emailEnabled) {
    results.push(await sendEmailMessage(subject, text, recipients, snapshot));
  }

  if (settings.lineWorksEnabled) {
    results.push(await sendLineWorksMessage(text, settings));
  }

  return results.join(" / ") || "送信対象がありません。";
}

export async function sendBroadcastNotification(
  snapshot: InventorySnapshot,
  settings: GlobalNotificationSettings,
): Promise<string> {
  const text = buildBroadcastMessage(snapshot);
  const subject = "資材一斉通知";
  const results: string[] = [];

  if (settings.emailEnabled) {
    results.push(await sendEmailMessage(subject, text, settings.commonEmails, snapshot));
  }

  if (settings.lineWorksEnabled) {
    results.push(await sendLineWorksMessage(text, settings));
  }

  if (results.length === 0) {
    throw new Error("一斉送信先が未設定です。メールまたはLINE WORKSを設定してください。");
  }

  return results.join(" / ");
}
