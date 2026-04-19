"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

function isValidPinFormat(value: string) {
  return /^\d{4}$/.test(value);
}

function normalizePinText(value: string) {
  const halfWidth = value.replace(/[０-９]/g, (char) =>
    String.fromCharCode(char.charCodeAt(0) - 0xfee0)
  );
  return halfWidth.replace(/\D/g, "").slice(0, 4);
}

function UnlockPageContent() {
  const router = useRouter();

  const [pin, setPin] = useState("");
  const [message, setMessage] = useState("4桁のPINコードを入力してください。");
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit(event: { preventDefault: () => void }) {
    event.preventDefault();

    const normalized = normalizePinText(pin);

    if (!isValidPinFormat(normalized)) {
      setMessage("PINコードは4桁の数字で入力してください。");
      return;
    }

    setIsPending(true);

    try {
      const response = await fetch("/api/auth/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: normalized }),
      });

      const result = (await response.json().catch(() => ({}))) as { error?: string };

      if (!response.ok) {
        setPin("");
        setMessage(result.error ?? "PINコードを確認してもう一度入力してください。");
        return;
      }

      const nextPath = (() => {
        if (typeof window === "undefined") {
          return "/";
        }
        const raw = new URLSearchParams(window.location.search).get("next") ?? "/";
        return raw.startsWith("/") ? raw : "/";
      })();

      router.replace(nextPath);
      router.refresh();
    } finally {
      setIsPending(false);
    }
  }

  return (
    <main className="inventory-shell">
      <div className="container" style={{ maxWidth: 480 }}>
        <section className="inventory-card card border-0 rounded-4 mt-5">
          <div className="card-body p-4 p-md-5">
            <h1 className="h4 mb-2">アクセス保護</h1>
            <p className="inventory-subtle mb-4">このアプリを開くには4桁PINコードが必要です。</p>

            <form className="d-grid gap-3" onSubmit={handleSubmit}>
              <input
                type="password"
                inputMode="numeric"
                pattern="[0-9]*"
                maxLength={4}
                autoComplete="one-time-code"
                placeholder="4桁PIN"
                className="form-control form-control-lg text-center"
                value={pin}
                onChange={(event) => setPin(normalizePinText((event.target as HTMLInputElement).value))}
              />

              <button type="submit" className="btn btn-primary btn-lg" disabled={isPending}>
                {isPending ? "確認中..." : "開く"}
              </button>
            </form>

            <p className="small mt-3 mb-0 inventory-subtle">{message}</p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function UnlockPageClient() {
  return <UnlockPageContent />;
}
