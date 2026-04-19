import { NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "material_manager_auth";

function isValidPinFormat(value: string) {
  return /^\d{4}$/.test(value);
}

function normalizePin(value: unknown) {
  const digitsOnly = String(value ?? "").replace(/\D/g, "");
  if (digitsOnly.length < 3 || digitsOnly.length > 4) {
    return "";
  }
  return digitsOnly.padStart(4, "0");
}

export async function POST(request: Request) {
  const configuredPin = normalizePin((process.env.APP_UNLOCK_PIN ?? "").trim());

  if (!isValidPinFormat(configuredPin)) {
    return NextResponse.json(
      {
        error:
          "サーバー側のPIN設定が未設定です。環境変数 APP_UNLOCK_PIN に4桁の数字を設定してください。",
      },
      { status: 500 },
    );
  }

  const body = (await request.json().catch(() => ({}))) as { pin?: unknown };
  const inputPin = normalizePin(body.pin);

  if (!isValidPinFormat(inputPin) || inputPin !== configuredPin) {
    return NextResponse.json({ error: "PINコードが正しくありません。" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "ok",
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });

  return response;
}
