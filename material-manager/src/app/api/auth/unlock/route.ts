import { NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "material_manager_auth";

function isValidPinFormat(value: string) {
  return /^\d{4}$/.test(value);
}

function normalizePin(value: unknown) {
  const halfWidth = String(value ?? "").replace(/[０-９]/g, (char) =>
    String.fromCharCode(char.charCodeAt(0) - 0xfee0)
  );
  const digitsOnly = halfWidth.replace(/\D/g, "");
  if (digitsOnly.length < 3 || digitsOnly.length > 4) {
    return "";
  }
  return digitsOnly.padStart(4, "0");
}

export async function POST(request: Request) {
  const rawPin = (process.env.APP_UNLOCK_PIN ?? "").trim();
  const configuredPin = normalizePin(rawPin);

  // PIN未設定の場合は自動的に認証OK（テスト用）
  if (!rawPin || !isValidPinFormat(configuredPin)) {
    const isSecureContext = request.url.startsWith("https://") || process.env.NODE_ENV === "production";
    const response = NextResponse.json({ ok: true, message: "PIN未設定のためスキップしました" });
    response.cookies.set({
      name: AUTH_COOKIE_NAME,
      value: "ok",
      httpOnly: true,
      secure: isSecureContext,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  }

  const body = (await request.json().catch(() => ({}))) as { pin?: unknown };
  const inputPin = normalizePin(body.pin);

  if (!isValidPinFormat(inputPin) || inputPin !== configuredPin) {
    return NextResponse.json({ error: "PINコードが正しくありません。" }, { status: 401 });
  }

  const isSecureContext = request.url.startsWith("https://") || process.env.NODE_ENV === "production";

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "ok",
    httpOnly: true,
    secure: isSecureContext,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });

  return response;
}
