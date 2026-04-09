import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import ezdxf
import openpyxl

# DWGファイルに線分を追加し、Excelファイルに表を作成する関数
def add_lines_to_dwg_and_create_excel(spacing, count, cover, width, height, file_path, horizontal_spacing, horizontal_cover, horizontal_count):
    length = height - cover * 2
    horizontal_length = width - horizontal_cover * 2
    
    doc = ezdxf.new(dxfversion='R2010')
    msp = doc.modelspace()
    
    # 躯体の長方形を作成
    msp.add_lwpolyline([(0, 0), (width, 0), (width, height), (0, height), (0, 0)])
    
    # 縦線を追加（主筋画層）
    main_layer = doc.layers.new(name='主筋', dxfattribs={'color': 1})  # 赤色
    for i in range(count):
        start_point = (cover + i * spacing, cover)
        end_point = (cover + i * spacing, cover + length)
        msp.add_line(start_point, end_point, dxfattribs={'layer': '主筋'})
    
    # 横線を追加（配力筋画層）
    secondary_layer = doc.layers.new(name='配力筋', dxfattribs={'color': 3})  # 緑色
    for i in range(horizontal_count):
        start_point = (horizontal_cover, horizontal_cover + i * horizontal_spacing)
        end_point = (horizontal_cover + horizontal_length, horizontal_cover + i * horizontal_spacing)
        msp.add_line(start_point, end_point, dxfattribs={'layer': '配力筋'})
    
    # 躯体の幅と長さの平行寸法を追加
    dim_layer = doc.layers.new(name='寸法', dxfattribs={'color': 5})  # 青色
    msp.add_aligned_dim(p1=(0, 0), p2=(width, 0), distance=-30, override={'dimtxt': 30, 'layer': '寸法'}).render()
    msp.add_aligned_dim(p1=(0, 0), p2=(0, height), distance=-30, override={'dimtxt': 30, 'layer': '寸法'}).render()

    doc.saveas(file_path)
    
    # Excelファイルに表を作成
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "線分情報"
    
    # 表のヘッダーを作成
    ws.append(["画層名", "線分の本数", "1本あたりの長さ寸法"])
    
    # 主筋の情報を追加
    ws.append(["主筋", count, length])
    
    # 配力筋の情報を追加
    ws.append(["配力筋", horizontal_count, horizontal_length])
    
    # Excelファイルを保存
    excel_file_path = file_path.replace(".dwg", ".xlsx")
    wb.save(excel_file_path)

# 配力筋の設定画面を表示する関数
def show_horizontal_lines_screen():
    def on_submit_horizontal():
        horizontal_spacing = float(horizontal_spacing_entry.get())
        horizontal_cover = float(horizontal_cover_entry.get())
        horizontal_count = int((height - horizontal_cover * 2) / horizontal_spacing + 1)
        
        file_path = filedialog.asksaveasfilename(defaultextension=".dwg", filetypes=[("DWG files", "*.dwg")])
        if file_path:
            add_lines_to_dwg_and_create_excel(spacing, count, cover, width, height, file_path,
                                              horizontal_spacing, horizontal_cover, horizontal_count)
            result_label.config(text="DWGファイルとExcelファイルを作成しました")
    
    # 配力筋の設定画面を作成
    horizontal_window = tk.Toplevel(root)
    horizontal_window.title("配力筋の設定")
    horizontal_window.geometry("400x300")
    
    ttk.Label(horizontal_window, text="配力筋の間隔（ピッチ）:").grid(column=0, row=0, padx=10, pady=5)
    horizontal_spacing_entry = ttk.Entry(horizontal_window)
    horizontal_spacing_entry.grid(column=1, row=0, padx=10, pady=5)
    
    ttk.Label(horizontal_window, text="配力筋のかぶり:").grid(column=0, row=1, padx=10, pady=5)
    horizontal_cover_entry = ttk.Entry(horizontal_window)
    horizontal_cover_entry.grid(column=1, row=1, padx=10, pady=5)
    
    submit_button = ttk.Button(horizontal_window, text="実行", command=on_submit_horizontal)
    submit_button.grid(column=0, row=2, columnspan=2, pady=10)

# ボタンが押されたときの処理
def on_submit():
    global spacing, cover, width, height, count
    spacing = float(spacing_entry.get())
    cover = float(cover_entry.get())
    width = float(width_entry.get())
    height = float(height_entry.get())
    
    # 本数を計算
    count = int((width - cover * 2) / spacing + 1)
    
    # 配力筋の設定画面を表示
    show_horizontal_lines_screen()

# メインウィンドウを作成
root = tk.Tk()
root.title("DWG 鉄筋配置アプリ（試用）")
root.geometry("400x500")

# 入力フィールドを作成
ttk.Label(root, text="躯体の幅:").grid(column=0, row=0, padx=10, pady=5)
width_entry = ttk.Entry(root)
width_entry.grid(column=1, row=0, padx=10, pady=5)

ttk.Label(root, text="躯体の長さ:").grid(column=0, row=1, padx=10, pady=5)
height_entry = ttk.Entry(root)
height_entry.grid(column=1, row=1, padx=10, pady=5)

ttk.Label(root, text="主筋間隔（ピッチ）:").grid(column=0, row=2, padx=10, pady=5)
spacing_entry = ttk.Entry(root)
spacing_entry.grid(column=1, row=2, padx=10, pady=5)

ttk.Label(root, text="かぶり:").grid(column=0, row=3, padx=10, pady=5)
cover_entry = ttk.Entry(root)
cover_entry.grid(column=1, row=3, padx=10, pady=5)

# 実行ボタンを作成
submit_button = ttk.Button(root, text="実行", command=on_submit)
submit_button.grid(column=0, row=4, columnspan=2, pady=10)

# 結果を表示するラベルを作成
result_label = ttk.Label(root, text="")
result_label.grid(column=0, row=5, columnspan=2, pady=10)

# 画像を表示するための関数
def display_image(image_path):
    image = Image.open(image_path)
    image.thumbnail((300, 300))  # サイズ調整
    photo_image = ImageTk.PhotoImage(image)

    image_label.config(image=photo_image)
    image_label.image = photo_image

# 画像ラベルを作成して配置
image_label = tk.Label(root)
image_label.grid(column=0, row=6, columnspan=2, pady=(20, 0))

# アプリケーションを実行して画像を表示
display_image("C:/Users/02030641/Desktop/Code/testapp/image1.png")

# 列の重みを設定して左右の空白を均等にする
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

root.mainloop()