import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import ezdxf
from PIL import Image
from pillow_heif import register_heif_opener
import piexif
import os

# HEIFサポートを登録
register_heif_opener()

# 単位体積重量（t/m³）
unit_weights = {
    "鉄筋": 7.85,
    "無筋コンクリート": 2.35,
    "鉄筋コンクリート": 2.5,
    "セメントモルタル": 2.15,
    "砂質土": 1.6,
    "砕石": 1.8
}

def calculate_volume_weight():
    material = material_var.get()
    unit_weight = unit_weights[material]
    weight = weight_var.get()
    volume = volume_var.get()
    if weight:
        volume = float(weight) / unit_weight
        volume_var.set(f"{volume:.2f}")
    elif volume:
        weight = float(volume) * unit_weight
        weight_var.set(f"{weight:.2f}")

def copy_to_clipboard():
    result = f"重量: {weight_var.get()} t\n体積: {volume_var.get()} m³"
    root.clipboard_clear()
    root.clipboard_append(result)
    root.update()

def calculate_cutting_load():
    try:
        diameter_mm = int(diameter_combobox.get())
        
        # 分と厘の表記
        diameter_to_bu_rin = {
            6: "2分",
            8: "2分5厘",
            9: "3分",
            10: "3分5厘",
            12: "4分",
            14: "4分5厘",
            16: "5分",
            18: "6分",
            20: "6分5厘",
            22: "7分",
            24: "8分",
            26: "8分5厘",
            28: "9分",
            30: "10分",
            32: "10分5厘",
            36: "12分",
            40: "13分"
        }
        
        bu_rin = diameter_to_bu_rin.get(diameter_mm, "不明")
        
        # 切断荷重の計算 (直径^2 / 2) [kN]
        cutting_load_kn = (diameter_mm**2) / 2
        cutting_load_t = cutting_load_kn / 9.80665

        # 安全荷重の計算 (切断荷重を6で割る)
        safe_cutting_load_kn = cutting_load_kn / 6
        safe_cutting_load_t = cutting_load_t / 6

        # 使用禁止メッセージ
        if diameter_mm <= 9:
            warning_label_style.configure("Warning.TLabel", foreground="red")
            warning_label.config(text="当社では使用禁止！")
        else:
            warning_label_style.configure("Warning.TLabel", foreground="black")
            warning_label.config(text="")

        result_text = (f"直径: {diameter_mm} mm ({bu_rin})\n"
                       f"切断荷重: {cutting_load_kn:.2f} kN / {cutting_load_t:.4f} t\n"
                       f"安全荷重: {safe_cutting_load_kn:.2f} kN / {safe_cutting_load_t:.4f} t\n")

        result_label.config(text=result_text)
    except ValueError:
        messagebox.showerror("入力エラー", "数値を正しく入力してください。")

class LevelSurveyNotebook:
    def __init__(self, parent):
        self.parent = parent
        self.columns = ("タイプ", "測点", "後視 (BS)", "機械高さ (IH)", "前視 (FS)", "標高")
        self.tree = ttk.Treeview(parent, columns=self.columns, show="headings", height=8)

        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor=tk.CENTER, width=100)

        self.data = [
            ("BM", "1", "", "", "", "100.0"),
            ("", "2", "", "", "", ""),
            ("", "3", "", "", "", ""),
            ("", "4", "", "", "", ""),
        ]

        for item in self.data:
            self.tree.insert("", tk.END, values=item)

        self.tree.pack(pady=20)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.entry_frame = ttk.Frame(parent)
        self.entry_frame.pack(pady=10)

        self.type_entry = ttk.Entry(self.entry_frame, width=10)
        self.type_entry.grid(row=0, column=0, padx=5)
        self.type_label = ttk.Label(self.entry_frame, text="タイプ")
        self.type_label.grid(row=1, column=0)

        self.point_entry = ttk.Entry(self.entry_frame, width=10)
        self.point_entry.grid(row=0, column=1, padx=5)
        self.point_label = ttk.Label(self.entry_frame, text="測点")
        self.point_label.grid(row=1, column=1)

        self.bs_entry = ttk.Entry(self.entry_frame, width=10)
        self.bs_entry.grid(row=0, column=2, padx=5)
        self.bs_label = ttk.Label(self.entry_frame, text="後視 (BS)")
        self.bs_label.grid(row=1, column=2)

        self.ih_entry = ttk.Entry(self.entry_frame, width=10)
        self.ih_entry.grid(row=0, column=3, padx=5)
        self.ih_label = ttk.Label(self.entry_frame, text="機械高さ (IH)")
        self.ih_label.grid(row=1, column=3)

        self.fs_entry = ttk.Entry(self.entry_frame, width=10)
        self.fs_entry.grid(row=0, column=4, padx=5)
        self.fs_label = ttk.Label(self.entry_frame, text="前視 (FS)")
        self.fs_label.grid(row=1, column=4)

        self.elevation_entry = ttk.Entry(self.entry_frame, width=10)
        self.elevation_entry.grid(row=0, column=5, padx=5)
        self.elevation_label = ttk.Label(self.entry_frame, text="標高")
        self.elevation_label.grid(row=1, column=5)

        self.calculate_button = ttk.Button(parent, text="計算", style="Custom.TButton", command=self.calculate_elevation)
        self.calculate_button.pack(pady=5)

        self.add_button = ttk.Button(parent, text="測点を追加", style="Custom.TButton", command=self.add_point)
        self.add_button.pack(pady=5)

        self.set_bm_button = ttk.Button(parent, text="BMに設定", style="Custom.TButton", command=self.set_benchmark)
        self.set_bm_button.pack(pady=5)

        self.unset_bm_button = ttk.Button(parent, text="BMを解除", style="Custom.TButton", command=self.unset_benchmark)
        self.unset_bm_button.pack(pady=5)

        self.save_dwg_button = ttk.Button(parent, text="DXFに保存", style="Custom.TButton", command=self.save_to_dwg)
        self.save_dwg_button.pack(pady=5)

    def on_tree_select(self, event):
        selected_item = self.tree.selection()
        if selected_item:
            values = self.tree.item(selected_item[0], "values")

            self.type_entry.delete(0, tk.END)
            self.type_entry.insert(0, values[0])

            self.point_entry.delete(0, tk.END)
            self.point_entry.insert(0, values[1])

            self.bs_entry.delete(0, tk.END)
            self.bs_entry.insert(0, values[2])

            self.ih_entry.delete(0, tk.END)
            self.ih_entry.insert(0, values[3])

            self.fs_entry.delete(0, tk.END)
            self.fs_entry.insert(0, values[4])

            self.elevation_entry.delete(0, tk.END)
            self.elevation_entry.insert(0, values[5])

            if values[0] in ("BM", "KBM"):
                self.elevation_entry.config(state='normal')
            else:
                self.elevation_entry.config(state='readonly')

    def calculate_elevation(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("警告", "計算する行を選択してください")
            return

        values = list(self.tree.item(selected_item[0], "values"))

        try:
            entry_type = self.type_entry.get()
            point = self.point_entry.get()
            bs_value = float(self.bs_entry.get()) if self.bs_entry.get() else 0.0
            ih_value = float(self.ih_entry.get()) if self.ih_entry.get() else 0.0
            fs_value = float(self.fs_entry.get()) if self.fs_entry.get() else 0.0

            if entry_type in ("BM", "KBM"):
                elevation = float(self.elevation_entry.get())
                ih_value = elevation + bs_value
            else:
                prev_item = self.tree.prev(selected_item[0])
                prev_values = list(self.tree.item(prev_item, "values")) if prev_item else None

                if not bs_value:
                    bs_value = float(prev_values[2]) if prev_values and prev_values[2] else 0.0

                if not ih_value:
                    ih_value = float(prev_values[3]) if prev_values and prev_values[3] else 0.0

                elevation = ih_value - fs_value

            values[0] = entry_type
            values[1] = point
            values[2] = bs_value
            values[3] = ih_value
            values[4] = fs_value
            values[5] = elevation

        except ValueError:
            values[5] = "エラー"

        self.tree.item(selected_item[0], values=values)

    def add_point(self):
        new_point_index = len(self.tree.get_children()) + 1
        self.tree.insert("", tk.END, values=("", str(new_point_index), "", "", "", ""))

    def set_benchmark(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("警告", "BMに設定する行を選択してください")
            return

        values = list(self.tree.item(selected_item[0], "values"))
        values[0] = "BM"
        self.tree.item(selected_item[0], values=values)
        self.on_tree_select(None)

    def unset_benchmark(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("警告", "BMを解除する行を選択してください")
            return

        values = list(self.tree.item(selected_item[0], "values"))
        values[0] = ""
        self.tree.item(selected_item[0], values=values)
        self.on_tree_select(None)

    def save_to_dwg(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".dxf",
            filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")],
            initialfile="レベル計測結果.dxf"
        )
        if not file_path:
            return

        doc = ezdxf.new()
        msp = doc.modelspace()

        x_offset = 0
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            try:
                elevation = float(values[5])
                y_position = elevation
                x_start = x_offset
                x_end = x_offset + 100

                # 線分を引く
                msp.add_line((x_start, y_position), (x_end, y_position))

                # テキストを追加
                text_position = (x_start + 5, y_position + 5)
                msp.add_text(f"{values[1]}: {elevation:.2f}", dxfattribs={'height': 5, 'insert': text_position})

                x_offset += 100  # 次の測点のX位置をオフセット
            except ValueError:
                continue

        doc.saveas(file_path)
        messagebox.showinfo("保存完了", f"データをDXFに保存しました: {file_path}")

def heif_to_jpg_with_metadata(heif_file_path, jpg_file_path):
    # HEIFファイルを開く
    image = Image.open(heif_file_path)
    
    # EXIFデータを取得
    exif_dict = piexif.load(image.info['exif'])
    
    # JPGとして保存
    image.save(jpg_file_path, "JPEG", exif=piexif.dump(exif_dict))

def select_heif_files():
    file_paths = filedialog.askopenfilenames(filetypes=[("HEIFファイル", "*.heic;*.heif")])
    if file_paths:
        output_dir = filedialog.askdirectory()
        if output_dir:
            for file_path in file_paths:
                file_name = os.path.basename(file_path)
                output_path = os.path.join(output_dir, os.path.splitext(file_name)[0] + ".jpg")
                try:
                    heif_to_jpg_with_metadata(file_path, output_path)
                except Exception as e:
                    messagebox.showerror("エラー", f"ファイルの変換に失敗しました: {e}")
            messagebox.showinfo("成功", "すべてのファイルが正常に変換されました！")

# GUIのセットアップ
root = tk.Tk()
root.title("建設業ツール")
root.geometry("900x600")

# スタイルの設定
style = ttk.Style()
style.configure("Custom.TButton", font=("Helvetica", 10, "bold"), padding=6, background="#ADD8E6", foreground="white")
style.map("Custom.TButton",
          background=[("active", "#87CEEB")],  # 少し濃い青
          foreground=[("active", "white")])

style.configure("TLabel", font=("Helvetica", 10))
style.configure("TEntry", font=("Helvetica", 10))

# 特定のラベルスタイルを設定
warning_label_style = ttk.Style()
warning_label_style.configure("Warning.TLabel", font=("Helvetica", 12, "bold"))

# タブの作成
tab_control = ttk.Notebook(root)

# 単位体積重量タブ
tab1 = ttk.Frame(tab_control)
tab_control.add(tab1, text='単位体積重量')

# 材料の選択
material_var = tk.StringVar(value="鉄筋")
ttk.Label(tab1, text="材料を選択:").grid(column=0, row=0, padx=10, pady=10, sticky="w")
material_menu = ttk.Combobox(tab1, textvariable=material_var, values=list(unit_weights.keys()), state="readonly")
material_menu.grid(column=1, row=0, padx=10, pady=10)

# 重量の入力
weight_var = tk.StringVar()
ttk.Label(tab1, text="重量 (t):").grid(column=0, row=1, padx=10, pady=10, sticky="w")
weight_entry = ttk.Entry(tab1, textvariable=weight_var)
weight_entry.grid(column=1, row=1, padx=10, pady=10)

# 体積の入力
volume_var = tk.StringVar()
ttk.Label(tab1, text="体積 (m³):").grid(column=0, row=2, padx=10, pady=10, sticky="w")
volume_entry = ttk.Entry(tab1, textvariable=volume_var)
volume_entry.grid(column=1, row=2, padx=10, pady=10)

# 計算ボタン
calculate_button = ttk.Button(tab1, text="計算", style="Custom.TButton", command=calculate_volume_weight)
calculate_button.grid(column=0, row=3, columnspan=2, padx=10, pady=10)

# コピーするボタン
copy_button = ttk.Button(tab1, text="コピー", style="Custom.TButton", command=copy_to_clipboard)
copy_button.grid(column=0, row=4, columnspan=2, padx=10, pady=10)

# 荷重計算タブ
tab2 = ttk.Frame(tab_control)
tab_control.add(tab2, text='切断荷重計算')

# ワイヤーロープの直径選択
ttk.Label(tab2, text="ワイヤーロープの直径 (mm):").grid(row=0, column=0, padx=10, pady=10, sticky="w")
diameter_combobox = ttk.Combobox(tab2, values=[6, 8, 9, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40], state="readonly")
diameter_combobox.set(6)
diameter_combobox.grid(row=0, column=1, padx=10, pady=10)

# 計算ボタン
calc_button = ttk.Button(tab2, text="計算", style="Custom.TButton", command=calculate_cutting_load)
calc_button.grid(row=1, column=0, columnspan=2, pady=20)

# 結果表示
result_label = ttk.Label(tab2, text="結果: ", background='lightgrey', anchor='center', font=('Helvetica', 10, 'bold'))
result_label.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

# 使用禁止メッセージ表示
warning_label = ttk.Label(tab2, text="", style="Warning.TLabel", anchor='center')
warning_label.grid(row=3, column=0, columnspan=2, pady=10)

# レベル測量野帳タブ
tab3 = ttk.Frame(tab_control)
tab_control.add(tab3, text='レベル測量野帳')

# レベル測量野帳のインスタンスを作成
level_survey_app = LevelSurveyNotebook(tab3)

# HEIF変換タブ
tab4 = ttk.Frame(tab_control)
tab_control.add(tab4, text='HEIF変換')

# HEIF変換のボタン
convert_button = ttk.Button(tab4, text="HEIFファイルを選択", style="Custom.TButton", command=select_heif_files)
convert_button.pack(pady=20)

tab_control.pack(expand=1, fill='both')

root.mainloop()