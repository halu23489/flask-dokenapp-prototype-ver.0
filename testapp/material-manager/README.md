## 資材管理アプリ

このアプリでできること:

- ホーム画面で資材一覧を表示
- 在庫の入庫 / 使用をその場で更新
- 新規資材を追加
- 追加ログと使用ログを別管理
- ログをExcelで出力
- 現在庫を画像 / Excelで出力または共有
- 共通の通知先を一括設定
- 現在庫の一斉送信
- 可能ならLINE WORKS Webhookでも送信

## ローカル起動

```bash
npm install
npm run dev
```

ブラウザで http://localhost:3000 を開くと使えます。

## データ保存

環境変数 `POSTGRES_URL` などの Vercel Postgres 設定がある場合は、在庫データをPostgresに保存します。
設定がない場合は data/inventory.json に保存され、ローカル用途として動作します。

つまり、ローカルではJSON保存、Vercel本番ではPostgres保存の二段構成です。

Vercelで運用する場合は、Vercel Postgres を追加して環境変数を本番環境へ設定してください。

初回デプロイ時に Postgres が空で、かつ data/inventory.json がデプロイ物に含まれていれば、その内容を初期データとして自動投入します。

明示的にローカル在庫をPostgresへ移したい場合は、Postgres の環境変数を設定した状態で次を実行します。

```bash
npm run migrate:postgres
```

このコマンドは data/inventory.json の内容で Postgres の在庫データを上書きします。

## メール通知

通知を有効にしたい場合は .env.example を参考に環境変数を設定してください。

必要な環境変数:

- POSTGRES_URL または POSTGRES_URL_NON_POOLING
- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASS
- MAIL_FROM
- LINE_WORKS_WEBHOOK_URL

未設定でもアプリは動作し、通知送信だけがスキップされます。

## 通知の考え方

- 低在庫通知は、各資材の下限値を基準に共通通知先へ送信します
- 一斉送信は共通送信先メールとLINE WORKS設定を使います
- LINE WORKSはこの実装ではWebhook URL前提の簡易対応です
