import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
from pillow_heif import register_heif_opener
import piexif
import os

# HEIFサポートを登録
register_heif_opener()

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

# メインウィンドウを作成
root = tk.Tk()
root.title("HEIFからJPGへの変換ツール")

# ウィンドウサイズを設定
root.geometry("400x150")

# ボタンを作成して配置
convert_button = tk.Button(root, text="HEIFファイルを選択", command=select_heif_files)
convert_button.pack(pady=20)

# アプリケーションを実行
root.mainloop()