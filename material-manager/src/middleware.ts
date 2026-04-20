import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE_NAME = "material_manager_auth";

function isPinConfigured() {
  const pin = (process.env.APP_UNLOCK_PIN ?? "").trim();
  return /^\d{3,4}$/.test(pin);
}

function isPublicPath(pathname: string) {
  return (
    pathname === "/unlock" ||
    pathname.startsWith("/api/auth/unlock") ||
    pathname.startsWith("/_next") ||
    pathname === "/favicon.ico"
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // PIN未設定の場合は認証をスキップ（テスト用）
  if (!isPinConfigured()) {
    return NextResponse.next();
  }

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const hasAuth = request.cookies.get(AUTH_COOKIE_NAME)?.value === "ok";

  if (hasAuth) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "認証が必要です。" }, { status: 401 });
  }

  const loginUrl = new URL("/unlock", request.url);
  loginUrl.searchParams.set("next", `${pathname}${search}`);

  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|.*\\.(?:png|jpg|jpeg|gif|svg|webp|ico)$).*)"],
};
