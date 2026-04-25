import InventoryApp from "@/app/components/inventory-app";
import { getInventorySnapshot } from "../lib/store";

export const dynamic = "force-dynamic";

export default async function Home() {
  try {
    const snapshot = await getInventorySnapshot();

    return (
      <InventoryApp initialSnapshot={snapshot} />
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "在庫データの読み込みに失敗しました。";

    return (
      <main style={{ padding: "2rem", maxWidth: 760, margin: "0 auto", fontFamily: "sans-serif" }}>
        <h1 style={{ marginBottom: "0.75rem" }}>在庫データを読み込めません</h1>
        <p style={{ marginBottom: "0.5rem" }}>サーバーで在庫データの取得に失敗しました。</p>
        <p style={{ marginBottom: "1rem", color: "#a00" }}>{message}</p>
        <ol style={{ lineHeight: 1.7 }}>
          <li>Vercel の Environment Variables で POSTGRES_URL 系を確認</li>
          <li>Supabase の接続文字列が正しいか確認</li>
          <li>修正後に Redeploy して再読み込み</li>
        </ol>
      </main>
    );
  }
}
