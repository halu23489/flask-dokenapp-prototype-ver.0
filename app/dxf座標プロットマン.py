import tkinter as tk
from tkinter import filedialog, messagebox
import os
import csv

# ezdxfが必要です。未インストールの場合は pip install ezdxf を実行してください。
try:
    import ezdxf
except ImportError:
    ezdxf = None


class DxfPlotterApp:
    def __init__(self, root):
        self.root = root
        root.title("CSV座標をDXFへプロット")

        # ファイルパス
        self.dxf_in_path = tk.StringVar()
        self.csv_path = tk.StringVar()
        self.dxf_out_path = tk.StringVar()

        # 設定値
        self.layer_name = tk.StringVar(value="取り込み座標")
        self.circle_radius = tk.DoubleVar(value=1.0)
        self.add_labels = tk.BooleanVar(value=True)
        self.text_height = tk.DoubleVar(value=2.5)
        self.text_offset = tk.DoubleVar(value=1.5)  # 円半径に対する倍率ではなく絶対オフセット（モデル単位）

        # UI 構築
        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 8, 'pady': 6}

        # 入力DXF
        tk.Label(self.root, text="入力DXF:").grid(row=0, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.dxf_in_path, width=60).grid(row=0, column=1, **pad)
        tk.Button(self.root, text="参照", command=self.select_dxf_in).grid(row=0, column=2, **pad)

        # CSV
        tk.Label(self.root, text="CSV(測点,A/B/C=測点/x/y):").grid(row=1, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.csv_path, width=60).grid(row=1, column=1, **pad)
        tk.Button(self.root, text="参照", command=self.select_csv).grid(row=1, column=2, **pad)

        # 出力DXF
        tk.Label(self.root, text="出力DXF:").grid(row=2, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.dxf_out_path, width=60).grid(row=2, column=1, **pad)
        tk.Button(self.root, text="参照", command=self.select_dxf_out).grid(row=2, column=2, **pad)

        # レイヤ・円・テキスト設定
        tk.Label(self.root, text="画層名:").grid(row=3, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.layer_name, width=20).grid(row=3, column=1, sticky="w", **pad)

        tk.Label(self.root, text="円の半径:").grid(row=4, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.circle_radius, width=10).grid(row=4, column=1, sticky="w", **pad)

        tk.Checkbutton(self.root, text="測点名を表示する", variable=self.add_labels).grid(row=5, column=1, sticky="w", **pad)

        tk.Label(self.root, text="文字高さ:").grid(row=6, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.text_height, width=10).grid(row=6, column=1, sticky="w", **pad)

        tk.Label(self.root, text="文字オフセット(X方向):").grid(row=7, column=0, sticky="e", **pad)
        tk.Entry(self.root, textvariable=self.text_offset, width=10).grid(row=7, column=1, sticky="w", **pad)

        # 実行ボタン
        tk.Button(self.root, text="プロット実行", command=self.run).grid(row=8, column=1, **pad)

    def select_dxf_in(self):
        path = filedialog.askopenfilename(
            title="入力DXFを選択",
            filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")]
        )
        if path:
            self.dxf_in_path.set(path)
            # 初期の保存先提案
            base = os.path.splitext(os.path.basename(path))[0]
            folder = os.path.dirname(path)
            proposed = os.path.join(folder, f"{base}_with_points.dxf")
            if not self.dxf_out_path.get():
                self.dxf_out_path.set(proposed)

    def select_csv(self):
        path = filedialog.askopenfilename(
            title="CSVを選択 (A=測点, B=x, C=y)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.csv_path.set(path)

    def select_dxf_out(self):
        path = filedialog.asksaveasfilename(
            title="出力DXFの保存先",
            defaultextension=".dxf",
            filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")]
        )
        if path:
            self.dxf_out_path.set(path)

    def run(self):
        # 前提チェック
        if ezdxf is None:
            messagebox.showerror("エラー", "ezdxf が見つかりません。事前に `pip install ezdxf` を実施してください。")
            return

        dxf_in = self.dxf_in_path.get().strip()
        csv_p = self.csv_path.get().strip()
        dxf_out = self.dxf_out_path.get().strip()

        if not dxf_in or not os.path.isfile(dxf_in):
            messagebox.showerror("エラー", "入力DXFが正しく選択されていません。")
            return
        if not csv_p or not os.path.isfile(csv_p):
            messagebox.showerror("エラー", "CSVが正しく選択されていません。")
            return
        if not dxf_out:
            messagebox.showerror("エラー", "出力DXFの保存先を指定してください。")
            return

        layer = self.layer_name.get().strip() or "取り込み座標"
        radius = float(self.circle_radius.get())
        add_labels = bool(self.add_labels.get())
        text_h = float(self.text_height.get())
        text_off = float(self.text_offset.get())

        try:
            # DXFを読み込み
            doc = ezdxf.readfile(dxf_in)
            msp = doc.modelspace()

            # レイヤ準備（色: 赤=1）
            if layer not in doc.layers:
                doc.layers.add(name=layer, color=1)

            # CSVを読み取り（UTF-8 → CP932の順でトライ）
            points = []
            encodings = ["utf-8-sig", "cp932"]
            read_ok = False
            for enc in encodings:
                try:
                    with open(csv_p, "r", encoding=enc, newline="") as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if not row:
                                continue
                            # 行は少なくとも3列（測点, x, y）
                            if len(row) < 3:
                                continue
                            name = str(row[0]).strip()
                            x_str = str(row[1]).strip().replace(",", "")
                            y_str = str(row[2]).strip().replace(",", "")
                            try:
                                x = float(x_str)
                                y = float(y_str)
                                points.append((name, x, y))
                            except ValueError:
                                # ヘッダ行や非数値はスキップ
                                continue
                    read_ok = True
                    break
                except UnicodeDecodeError:
                    continue

            if not read_ok:
                messagebox.showerror("エラー", "CSVの読み込みに失敗しました。文字コード（UTF-8/Shift_JIS）をご確認ください。")
                return

            if not points:
                messagebox.showerror("エラー", "CSVから有効な座標が読み取れませんでした。（B=Cが数値の行のみプロットします）")
                return

            # プロット（円 + 任意の測点名）
            for name, x, y in points:
                msp.add_circle(center=(x, y, 0.0), radius=radius, dxfattribs={"layer": layer})
                if add_labels and name:
                    # 単純にX方向へオフセットした位置にテキストを配置
                    msp.add_text(
                        name,
                        dxfattribs={"height": text_h, "layer": layer}
                    ).set_pos((x + text_off, y), align="LEFT")

            # 保存
            doc.saveas(dxf_out)
            messagebox.showinfo("完了", f"プロットして保存しました:\n{dxf_out}")

        except FileNotFoundError:
            messagebox.showerror("エラー", "入力DXFが見つかりません。パスを再確認してください。")
        except ezdxf.DXFStructureError as e:
            messagebox.showerror("エラー", f"DXFの構造エラー: {e}")
        except Exception as e:
            messagebox.showerror("エラー", f"処理中に予期せぬエラーが発生しました:\n{e}")


def main():
    root = tk.Tk()
    app = DxfPlotterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()