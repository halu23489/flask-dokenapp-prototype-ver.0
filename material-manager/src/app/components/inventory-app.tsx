"use client";

import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";

import { buildInventoryFileName } from "../../lib/inventory-file-name";
import type { GlobalNotificationSettings, InventorySnapshot, Material } from "../../lib/types";

type Props = {
  initialSnapshot: InventorySnapshot;
};

type PendingAmounts = Record<string, string>;

const numberFormatter = new Intl.NumberFormat("ja-JP");
const dateFormatter = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function normalizeNumericText(value: string) {
  return value
    .replace(/[０-９]/g, (char) => String.fromCharCode(char.charCodeAt(0) - 0xfee0))
    .replace(/[‐‑‒–—―ー]/g, "-")
    .replace(/[，、]/g, ",")
    .replace(/\s+/g, "")
    .replace(/,/g, "");
}

function parsePositiveInteger(value: string) {
  const normalized = normalizeNumericText(value);

  if (!normalized) {
    return NaN;
  }

  return Math.trunc(Number(normalized));
}

function parseEmails(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function waitForNextFrame() {
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
}

function blobFromCanvas(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("画像出力に失敗しました。"));
        return;
      }

      resolve(blob);
    }, "image/png");
  });
}

function createInventoryImageBlob(snapshot: InventorySnapshot) {
  const paddingX = 48;
  const topPadding = 40;
  const bottomPadding = 40;
  const titleHeight = 42;
  const subtitleHeight = 34;
  const headerHeight = 44;
  const rowHeight = 38;
  const tableTop = topPadding + titleHeight + subtitleHeight + 24;
  const tableWidth = 1104;
  const canvasWidth = 1200;
  const nameColumnWidth = 760;
  const qtyColumnWidth = tableWidth - nameColumnWidth;
  const rowCount = Math.max(snapshot.materials.length, 1);
  const canvasHeight = tableTop + headerHeight + rowHeight * rowCount + bottomPadding;

  const canvas = document.createElement("canvas");
  canvas.width = canvasWidth;
  canvas.height = canvasHeight;

  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("画像描画の初期化に失敗しました。");
  }

  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);

  context.fillStyle = "#111827";
  context.textBaseline = "middle";

  context.font = '700 34px "Noto Sans JP", sans-serif';
  context.fillText("松戸ヤード資材数量表", paddingX, topPadding + titleHeight / 2);

  context.fillStyle = "#4b5563";
  context.font = '400 20px "Noto Sans JP", sans-serif';
  context.fillText(
    `出力日時 ${dateFormatter.format(new Date(snapshot.lastUpdatedAt))}`,
    paddingX,
    topPadding + titleHeight + subtitleHeight / 2,
  );

  context.strokeStyle = "#cbd5e1";
  context.lineWidth = 2;
  context.strokeRect(paddingX, tableTop, tableWidth, headerHeight + rowHeight * rowCount);

  context.fillStyle = "#eef2f7";
  context.fillRect(paddingX, tableTop, tableWidth, headerHeight);

  context.strokeStyle = "#cbd5e1";
  context.beginPath();
  context.moveTo(paddingX + nameColumnWidth, tableTop);
  context.lineTo(paddingX + nameColumnWidth, tableTop + headerHeight + rowHeight * rowCount);
  context.stroke();

  context.fillStyle = "#111827";
  context.font = '700 20px "Noto Sans JP", sans-serif';
  context.fillText("資材名", paddingX + 16, tableTop + headerHeight / 2);
  context.fillText("在庫数量", paddingX + nameColumnWidth + 16, tableTop + headerHeight / 2);

  context.font = '400 20px "Noto Sans JP", sans-serif';

  const materials =
    snapshot.materials.length > 0
      ? snapshot.materials
      : [{ id: "empty", name: "資材データなし", quantity: 0, unit: "", notes: "" }];

  materials.forEach((material, index) => {
    const y = tableTop + headerHeight + rowHeight * index;

    if (index % 2 === 0) {
      context.fillStyle = "#ffffff";
    } else {
      context.fillStyle = "#f8fafc";
    }

    context.fillRect(paddingX, y, tableWidth, rowHeight);

    context.strokeStyle = "#e5e7eb";
    context.beginPath();
    context.moveTo(paddingX, y + rowHeight);
    context.lineTo(paddingX + tableWidth, y + rowHeight);
    context.stroke();

    context.fillStyle = "#111827";
    context.fillText(String(material.name), paddingX + 16, y + rowHeight / 2);
    context.fillText(
      `${numberFormatter.format(Number(material.quantity ?? 0))}${String(material.unit ?? "")}`,
      paddingX + nameColumnWidth + 16,
      y + rowHeight / 2,
    );
  });

  return blobFromCanvas(canvas);
}

export default function InventoryApp({ initialSnapshot }: Props) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [actor, setActor] = useState("現場担当者");
  const [query, setQuery] = useState("");
  const [exportFormat, setExportFormat] = useState<"image" | "xlsx">("xlsx");
  const [statusMessage, setStatusMessage] = useState("ローカル保存で起動しています。");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [notificationDraft, setNotificationDraft] = useState<GlobalNotificationSettings>(
    initialSnapshot.notificationSettings,
  );
  const [pendingAmounts, setPendingAmounts] = useState<PendingAmounts>({});
  const [addForm, setAddForm] = useState({
    name: "",
    unit: "個",
    quantity: "0",
    threshold: "",
    notes: "",
  });
  const [settingsDrafts, setSettingsDrafts] = useState<Record<string, { threshold: string }>>(() =>
    Object.fromEntries(
      initialSnapshot.materials.map((material) => [
        material.id,
        {
          threshold: material.threshold?.toString() ?? "",
        },
      ]),
    ),
  );
  const [isPending, startTransition] = useTransition();
  const reportRef = useRef<HTMLDivElement>(null);
  const deferredQuery = useDeferredValue(query);

  const filteredMaterials = useMemo(() => {
    if (!deferredQuery.trim()) {
      return snapshot.materials;
    }

    const normalized = deferredQuery.trim().toLowerCase();
    return snapshot.materials.filter((material) => {
      return [material.name, material.notes].join(" ").toLowerCase().includes(normalized);
    });
  }, [deferredQuery, snapshot.materials]);

  const refreshSnapshot = useCallback(async (showMessage = true) => {
    const response = await fetch("/api/state", { cache: "no-store" });
    const nextSnapshot = (await response.json()) as InventorySnapshot;
    setSnapshot(nextSnapshot);

    if (showMessage) {
      setStatusMessage("最新の在庫情報に更新しました。");
    }
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshSnapshot(false);
    }, 15000);

    return () => window.clearInterval(interval);
  }, [refreshSnapshot]);

  async function mutateInventory(payload: { action: string; payload: Record<string, unknown> }) {
    const response = await fetch("/api/materials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const result = (await response.json()) as {
      snapshot?: InventorySnapshot;
      message?: string;
      error?: string;
    };

    if (!response.ok || result.error) {
      throw new Error(result.error ?? "更新に失敗しました。");
    }

    if (result.snapshot) {
      setSnapshot(result.snapshot);
      setNotificationDraft(result.snapshot.notificationSettings);
      setSettingsDrafts(
        Object.fromEntries(
          result.snapshot.materials.map((material) => [
            material.id,
            {
              threshold: material.threshold?.toString() ?? "",
            },
          ]),
        ),
      );
    }

    setStatusMessage(result.message ?? "更新しました。");
  }

  function handleAdjust(materialId: string, direction: 1 | -1) {
    const rawAmount = pendingAmounts[materialId] ?? "1";
    const amount = parsePositiveInteger(rawAmount);

    if (!Number.isFinite(amount) || amount < 1) {
      setStatusMessage("増減数は1以上で指定してください。");
      return;
    }

    startTransition(() => {
      void mutateInventory({
        action: "adjust",
        payload: {
          id: materialId,
          delta: amount * direction,
          actor,
          note: "",
        },
      }).catch((error: Error) => {
        setStatusMessage(error.message);
      });
    });
  }

  function updatePendingAmount(materialId: string, nextValue: string) {
    setPendingAmounts((current) => ({
      ...current,
      [materialId]: nextValue,
    }));
  }

  function handleCreateMaterial(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    startTransition(() => {
      void mutateInventory({
        action: "create",
        payload: {
          ...addForm,
          category: "",
          location: "",
          quantity: Number(addForm.quantity || 0),
          threshold: addForm.threshold === "" ? null : Number(addForm.threshold),
        },
      })
        .then(() => {
          setAddForm({
            name: "",
            unit: "個",
            quantity: "0",
            threshold: "",
            notes: "",
          });
          setIsAddModalOpen(false);
        })
        .catch((error: Error) => {
          setStatusMessage(error.message);
        });
    });
  }

  function handleAlertSave(material: Material) {
    const draft = settingsDrafts[material.id];

    startTransition(() => {
      void mutateInventory({
        action: "update-alert",
        payload: {
          id: material.id,
          threshold: draft.threshold === "" ? null : Number(draft.threshold),
        },
      }).catch((error: Error) => {
        setStatusMessage(error.message);
      });
    });
  }

  function handleDeleteMaterial(material: Material) {
    const confirmed = window.confirm(`「${material.name}」を削除します。`);

    if (!confirmed) {
      return;
    }

    startTransition(() => {
      void mutateInventory({
        action: "delete",
        payload: {
          id: material.id,
        },
      }).catch((error: Error) => {
        setStatusMessage(error.message);
      });
    });
  }

  function handleNotificationSave() {
    startTransition(() => {
      void mutateInventory({
        action: "update-global-alert",
        payload: {
          emailEnabled: notificationDraft.emailEnabled,
          commonEmails: notificationDraft.commonEmails,
          lineWorksEnabled: notificationDraft.lineWorksEnabled,
          lineWorksWebhookUrl: notificationDraft.lineWorksWebhookUrl,
        },
      }).catch((error: Error) => {
        setStatusMessage(error.message);
      });
    });
  }

  function handleBroadcast() {
    startTransition(() => {
      void mutateInventory({
        action: "broadcast-notification",
        payload: {},
      }).catch((error: Error) => {
        setStatusMessage(error.message);
      });
    });
  }

  async function fetchExportBlob(format: "xlsx") {
    const response = await fetch(`/api/exports/inventory?format=${format}`);
    if (!response.ok) {
      throw new Error("現在は画像とExcel出力のみ対応しています。");
    }
    return response.blob();
  }

  async function createImageExportBlob() {
    if ("fonts" in document) {
      await document.fonts.ready;
    }

    await waitForNextFrame();
    return createInventoryImageBlob(snapshot);
  }

  async function handleExport() {
    if (exportFormat === "image") {
      const blob = await createImageExportBlob();

      downloadBlob(blob, buildInventoryFileName("png"));
      setStatusMessage("画像を書き出しました。");
      return;
    }

    const blob = await fetchExportBlob(exportFormat);
    downloadBlob(blob, buildInventoryFileName(exportFormat));
    setStatusMessage(`${exportFormat.toUpperCase()}を出力しました。`);
  }

  async function handleShare() {
    if (!("share" in navigator)) {
      setStatusMessage("この端末は共有APIに対応していません。");
      return;
    }

    if (exportFormat === "image") {
      const blob = await createImageExportBlob();

      const file = new File([blob], buildInventoryFileName("png"), { type: "image/png" });
      await navigator.share({
        files: [file],
        title: "資材現況一覧",
        text: "最新の資材現況です。",
      });
      setStatusMessage("画像を共有しました。");
      return;
    }

    const blob = await fetchExportBlob(exportFormat);
    const file = new File([blob], buildInventoryFileName(exportFormat), {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await navigator.share({
      files: [file],
      title: "資材現況一覧",
      text: "最新の資材現況です。",
    });

    setStatusMessage(`${exportFormat.toUpperCase()}を共有しました。`);
  }

  return (
    <main className="inventory-shell">
      <div className="container-xl">
        <div className="inventory-hero rounded-4 p-4 p-lg-5 mb-4">
          <div className="row g-4 align-items-end">
            <div className="col-lg-8">
              <span className="badge text-bg-primary mb-3">全員編集可</span>
              <h1 className="display-6 fw-bold mb-2">松戸置き場用資材管理表</h1>
              <p className="inventory-subtle mb-2">
                資材の現在庫、入庫・使用、ログ出力、共有、全員向け通知をシンプルにまとめています。
              </p>
              <p className="inventory-subtle mb-0 small">
                最終更新 {dateFormatter.format(new Date(snapshot.lastUpdatedAt))}
              </p>
            </div>
            <div className="col-lg-4">
              <div className="row g-2">
                <div className="col-4">
                  <SummaryCard label="資材数" value={`${numberFormatter.format(snapshot.totals.materialCount)}件`} />
                </div>
                <div className="col-4">
                  <SummaryCard label="総在庫" value={numberFormatter.format(snapshot.totals.quantitySum)} />
                </div>
                <div className="col-4">
                  <SummaryCard
                    label="要補充"
                    value={`${numberFormatter.format(snapshot.totals.lowStockCount)}件`}
                    accent={snapshot.totals.lowStockCount > 0}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="row g-4 align-items-start">
          <div className="col-12">
            <section className="inventory-card card border-0 rounded-4 mb-4">
              <div className="card-body p-4 p-xl-5">
                <div className="d-flex flex-column flex-md-row justify-content-between gap-3 mb-4">
                  <div>
                    <div className="inventory-kicker mb-2">メイン操作</div>
                    <h2 className="h3 mb-1">資材の出し入れ</h2>
                    <p className="inventory-subtle mb-0">数量入力、入庫、使用をこの一覧でそのまま処理できます。</p>
                  </div>
                  <div className="d-flex gap-2 inventory-search-row">
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="資材名やメモで検索"
                      className="form-control form-control-lg"
                    />
                    <button type="button" onClick={() => setIsAddModalOpen(true)} className="btn btn-outline-primary btn-lg text-nowrap">
                      新資材追加
                    </button>
                    <button type="button" onClick={() => void refreshSnapshot()} className="btn btn-primary btn-lg text-nowrap">
                      最新化
                    </button>
                  </div>
                </div>

                <div className="inventory-utility-bar mb-4">
                  <div className="inventory-utility-item">
                    <span className="inventory-subtle small">操作者</span>
                    <input value={actor} onChange={(event) => setActor(event.target.value)} className="form-control" />
                  </div>
                  <div className="inventory-utility-status alert alert-primary mb-0" role="alert">
                    <div>{statusMessage}</div>
                    <div className="small mt-1">この画面は閲覧者全員がそのまま編集できます。{isPending ? " 更新中..." : ""}</div>
                  </div>
                </div>

                <div className="inventory-report table-responsive rounded-3 border">
                  <table className="inventory-table inventory-table-large inventory-table-mobile-fit table table-hover align-middle mb-0">
                    <thead className="table-light">
                      <tr>
                        <th>資材名</th>
                        <th>在庫</th>
                        <th>閾値</th>
                        <th className="inventory-main-actions-col">出し入れ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMaterials.map((material) => {
                        const isLow = material.threshold !== null && material.quantity <= material.threshold;
                        const draft = settingsDrafts[material.id];

                        return (
                          <tr key={material.id}>
                            <td>
                              <div className="fw-semibold fs-5">{material.name}</div>
                              <div className="small inventory-subtle mt-1">{material.notes || "メモなし"}</div>
                            </td>
                            <td>
                              <span className="fw-semibold fs-4">{numberFormatter.format(material.quantity)}</span>
                              <span className="inventory-subtle ms-1">{material.unit}</span>
                            </td>
                            <td>
                              <span className={`badge ${isLow ? "text-bg-warning" : "text-bg-light"}`}>
                                {material.threshold === null ? "未設定" : `${material.threshold}${material.unit}`}
                              </span>
                            </td>
                            <td>
                              <div className="d-grid gap-2">
                                <div className="inventory-action-row d-grid gap-2 gap-xl-3">
                                  <input
                                    type="tel"
                                    inputMode="numeric"
                                    pattern="[0-9０-９]*"
                                    enterKeyHint="done"
                                    value={pendingAmounts[material.id] ?? "1"}
                                    onInput={(event) => updatePendingAmount(material.id, event.currentTarget.value)}
                                    onChange={(event) => updatePendingAmount(material.id, event.target.value)}
                                    onBlur={(event) => {
                                      const normalized = normalizeNumericText(event.target.value);
                                      updatePendingAmount(material.id, normalized || "1");
                                    }}
                                    className="form-control form-control-lg inventory-amount-input"
                                  />
                                  <button type="button" onClick={() => handleAdjust(material.id, 1)} className="btn btn-primary btn-lg inventory-action-button">
                                    入庫
                                  </button>
                                  <button type="button" onClick={() => handleAdjust(material.id, -1)} className="btn btn-danger btn-lg inventory-action-button">
                                    使用
                                  </button>
                                  <button type="button" onClick={() => handleDeleteMaterial(material)} className="btn btn-outline-secondary inventory-delete-button">
                                    削除
                                  </button>
                                </div>

                                <div className="row g-2">
                                  <div className="col-md-4 col-xl-3">
                                    <input
                                      value={draft?.threshold ?? ""}
                                      onChange={(event) =>
                                        setSettingsDrafts((current) => ({
                                          ...current,
                                          [material.id]: {
                                            ...(current[material.id] ?? { threshold: "" }),
                                            threshold: event.target.value,
                                          },
                                        }))
                                      }
                                      placeholder="下限値"
                                      className="form-control"
                                    />
                                  </div>
                                  <div className="col-md-8 col-xl-9 d-flex align-items-center justify-content-end gap-2">
                                    <button type="button" onClick={() => handleAlertSave(material)} className="btn btn-outline-secondary">
                                      下限値を保存
                                    </button>
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        );
                      })}

                      {filteredMaterials.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="text-center text-muted py-4">
                            条件に一致する資材はありません。
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className="row g-4 mt-1">
          <div className="col-xl-4">
            <section className="inventory-card card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <h2 className="h5 mb-3">共通通知設定</h2>
                <div className="d-grid gap-3">
                  <div className="form-check">
                    <input
                      id="notify-email-enabled"
                      type="checkbox"
                      className="form-check-input"
                      checked={notificationDraft.emailEnabled}
                      onChange={(event) =>
                        setNotificationDraft((current) => ({
                          ...current,
                          emailEnabled: event.target.checked,
                        }))
                      }
                    />
                    <label htmlFor="notify-email-enabled" className="form-check-label">
                      メール通知を使う
                    </label>
                  </div>
                  <div>
                    <label className="form-label">全員向け送信先メール</label>
                    <input
                      value={notificationDraft.commonEmails.join(", ")}
                      onChange={(event) =>
                        setNotificationDraft((current) => ({
                          ...current,
                          commonEmails: parseEmails(event.target.value),
                        }))
                      }
                      placeholder="aaa@example.com, bbb@example.com"
                      className="form-control"
                    />
                  </div>
                  <div className="form-check">
                    <input
                      id="notify-lineworks-enabled"
                      type="checkbox"
                      className="form-check-input"
                      checked={notificationDraft.lineWorksEnabled}
                      onChange={(event) =>
                        setNotificationDraft((current) => ({
                          ...current,
                          lineWorksEnabled: event.target.checked,
                        }))
                      }
                    />
                    <label htmlFor="notify-lineworks-enabled" className="form-check-label">
                      LINE WORKS送信を使う
                    </label>
                  </div>
                  <div>
                    <label className="form-label">LINE WORKS Webhook URL</label>
                    <input
                      value={notificationDraft.lineWorksWebhookUrl}
                      onChange={(event) =>
                        setNotificationDraft((current) => ({
                          ...current,
                          lineWorksWebhookUrl: event.target.value,
                        }))
                      }
                      placeholder="https://..."
                      className="form-control"
                    />
                  </div>
                  <div className="d-grid gap-2 d-sm-flex">
                    <button type="button" onClick={handleNotificationSave} className="btn btn-primary flex-fill">
                      共通通知設定を保存
                    </button>
                    <button type="button" onClick={handleBroadcast} className="btn btn-outline-secondary flex-fill">
                      一斉送信
                    </button>
                  </div>
                  <div className="small inventory-subtle">
                    下限値に達した資材は、この共通通知先へ自動送信されます。
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div className="col-xl-4">
            <section className="inventory-card card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <h2 className="h5 mb-3">出力と共有</h2>
                <div className="d-grid gap-3">
                  <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "image" | "xlsx")} className="form-select">
                    <option value="image">画像で出力 / 共有</option>
                    <option value="xlsx">Excelで出力 / 共有</option>
                  </select>
                  <div className="d-grid gap-2 d-sm-flex">
                    <button type="button" onClick={() => void handleExport()} className="btn btn-outline-primary flex-fill">出力</button>
                    <button type="button" onClick={() => void handleShare()} className="btn btn-outline-secondary flex-fill">共有</button>
                  </div>
                  <div className="small inventory-subtle">現在庫を画像またはExcelで出力できます。</div>
                </div>
              </div>
            </section>
          </div>

          <div className="col-xl-4">
            <section className="inventory-card card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <h2 className="h5 mb-3">ログ出力</h2>
                <div className="d-grid gap-2">
                  <button type="button" onClick={() => window.open("/api/exports/logs?type=addition", "_blank")} className="btn btn-outline-secondary">追加ログをExcel出力</button>
                  <button type="button" onClick={() => window.open("/api/exports/logs?type=usage", "_blank")} className="btn btn-outline-secondary">使用ログをExcel出力</button>
                  <button type="button" onClick={() => window.open("/api/exports/logs?type=all", "_blank")} className="btn btn-outline-secondary">全ログをExcel出力</button>
                </div>
              </div>
            </section>
          </div>
        </div>

        <div className="row g-4 mt-1">
          <div className="col-lg-6">
            <LogPanel title="追加ログ" logs={snapshot.additionLogs} tone="success" />
          </div>
          <div className="col-lg-6">
            <LogPanel title="使用ログ" logs={snapshot.usageLogs} tone="warning" />
          </div>
        </div>

        {isAddModalOpen ? (
          <div className="inventory-modal-backdrop" role="presentation" onClick={() => setIsAddModalOpen(false)}>
            <div className="inventory-modal card border-0 rounded-4" role="dialog" aria-modal="true" aria-label="新資材追加" onClick={(event) => event.stopPropagation()}>
              <div className="card-body p-4 p-xl-5">
                <div className="d-flex align-items-center justify-content-between gap-3 mb-4">
                  <div>
                    <div className="inventory-kicker mb-2">新規登録</div>
                    <h2 className="h4 mb-0">新資材追加</h2>
                  </div>
                  <button type="button" onClick={() => setIsAddModalOpen(false)} className="btn btn-outline-secondary">
                    閉じる
                  </button>
                </div>
                <form onSubmit={handleCreateMaterial} className="d-grid gap-3">
                  <input value={addForm.name} onChange={(event) => setAddForm((current) => ({ ...current, name: event.target.value }))} placeholder="資材名" className="form-control form-control-lg" />
                  <div className="row g-2">
                    <div className="col-md-4">
                      <input value={addForm.unit} onChange={(event) => setAddForm((current) => ({ ...current, unit: event.target.value }))} placeholder="単位" className="form-control" />
                    </div>
                    <div className="col-md-4">
                      <input value={addForm.quantity} onChange={(event) => setAddForm((current) => ({ ...current, quantity: event.target.value }))} placeholder="初期在庫" className="form-control" />
                    </div>
                    <div className="col-md-4">
                      <input value={addForm.threshold} onChange={(event) => setAddForm((current) => ({ ...current, threshold: event.target.value }))} placeholder="下限値" className="form-control" />
                    </div>
                  </div>
                  <textarea value={addForm.notes} onChange={(event) => setAddForm((current) => ({ ...current, notes: event.target.value }))} rows={4} placeholder="メモ" className="form-control" />
                  <div className="d-flex justify-content-end gap-2">
                    <button type="button" onClick={() => setIsAddModalOpen(false)} className="btn btn-outline-secondary">
                      キャンセル
                    </button>
                    <button className="btn btn-primary btn-lg" type="submit">資材を追加</button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        ) : null}

        <div className="inventory-export-sheet" ref={reportRef} aria-hidden="true">
          <div className="inventory-export-sheet-inner">
            <h2 className="inventory-export-title">松戸ヤード資材数量表</h2>
            <div className="inventory-export-date">出力日時 {dateFormatter.format(new Date(snapshot.lastUpdatedAt))}</div>
            <table className="table table-bordered align-middle mb-0">
              <thead>
                <tr>
                  <th>資材名</th>
                  <th>在庫数量</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.materials.map((material) => (
                  <tr key={`export-${material.id}`}>
                    <td>{material.name}</td>
                    <td>{material.quantity}{material.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>
  );
}

function SummaryCard({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-4 p-3 h-100 ${accent ? "inventory-low" : "inventory-summary"}`}>
      <div className="small inventory-subtle mb-1">{label}</div>
      <div className="fw-bold fs-5">{value}</div>
    </div>
  );
}

function LogPanel({
  title,
  logs,
  tone,
}: {
  title: string;
  logs: InventorySnapshot["additionLogs"];
  tone: "success" | "warning";
}) {
  return (
    <section className="inventory-card card border-0 rounded-4 h-100">
      <div className="card-body p-4">
        <div className="d-flex align-items-center justify-content-between mb-3">
          <h2 className="h5 mb-0">{title}</h2>
          <span className={`badge ${tone === "success" ? "text-bg-success" : "text-bg-warning"}`}>
          最新10件
          </span>
        </div>
        <div className="d-grid gap-2">
          {logs.slice(0, 10).map((log) => (
            <div key={log.id} className="border rounded-3 p-3 bg-white">
              <div className="d-flex justify-content-between gap-3">
                <div>
                  <div className="fw-semibold">{log.materialName}</div>
                  <div className="small inventory-subtle">
                  {dateFormatter.format(new Date(log.createdAt))} / {log.actor}
                  </div>
                </div>
                <div className="text-end">
                  <div className="fw-semibold">{log.quantity}</div>
                  <div className="small inventory-subtle">実行後 {log.resultingQuantity}</div>
                </div>
              </div>
              <div className="small inventory-subtle mt-2">{log.note || "メモなし"}</div>
            </div>
          ))}
          {logs.length === 0 ? <div className="text-center text-muted py-4">まだ記録はありません。</div> : null}
        </div>
      </div>
    </section>
  );
}