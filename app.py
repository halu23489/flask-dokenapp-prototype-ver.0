import os
import io
from flask import Flask, render_template, request, redirect, url_for, send_file
import pillow_heif  # HEIC/HEIFファイルの読み込みに使用
from PIL import Image # 画像処理に使用
import ezdxf # DXFファイル生成に使用
from io import StringIO # DXFをメモリで扱うために使用

# ログを無効化（デバッグ時に邪魔にならないように）
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


# === 1. グローバル定数と比重データの定義 ===

APP_NAME = 'ショクチョー！'

# 比重データの定義 (比重/密度: t/m³ または kg/L)
DENSITY_DATA = {
    "コンクリート（無筋）": 2.3,    # 2.3 t/m³
    "コンクリート（有筋）": 2.45,   # 2.45 t/m³
    "砕石": 1.7,                    # 1.7 t/m³ (山積み)
    "土（真砂土など）": 1.6,      # 1.6 t/m³ (真砂土山積み目安)
    "泥（粘土質）": 1.8,            # 1.8 t/m³ (粘土山積み目安)
    "水": 1.0,                      # 1.0 t/m³
    "鉄骨・鋼材": 7.85,             # 7.85 t/m³
    "アスファルト": 2.35,          # 2.35 t/m³
}

# アプリケーションのナビゲーションマップ (サイドバーとリンク生成に使用)
APP_NAVIGATION = {
    'index': {'name': '🏠 ホーム', 'url': 'index'},
    'utilities': {
        'name': '🛠️ 便利アプリ',
        'children': [
            # 'url' は @app.route の関数名と一致させる
            {'id': 'converter', 'name': '📸 HEIC to JPG 変換', 'url': 'converter_page'},
            {'id': 'unit_converter', 'name': '📏 単位換算', 'url': 'unit_converter_page'},
            {'id': 'calculator', 'name': '📐 計算ツール', 'url': 'calculator'},
            {'id': 'dxf_tool', 'name': '🗺️ DXF座標出力ツール', 'url': 'dxf_tool_page'},
            {'id': 'comparison_tool', 'name': '📊 比較見積もりツール', 'url': 'comparison_tool_page'},
        ]
    },
    'forum': {'name': '💬 知恵袋・掲示板', 'url': 'forum'},
}


# 2. Flaskアプリケーションインスタンスの定義
app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# --- 3. ルーティング定義 ---

@app.route('/')
def index():
    """ホーム画面 (ダッシュボード)"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': 'ホーム',
        'nav': APP_NAVIGATION,
        'current_app': 'index'
    }
    return render_template('index.html', **data)

@app.route('/forum')
def forum():
    """知恵袋・掲示板ページ"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': '知恵袋・掲示板',
        'nav': APP_NAVIGATION,
        'current_app': 'forum'
    }
    # テンプレート名をforum_page.htmlに変更 (index.htmlとの衝突を避けるため)
    return render_template('forum_page.html', **data)

@app.route('/calculator')
def calculator():
    """計算ツールページ"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': '計算ツール',
        'nav': APP_NAVIGATION,
        'current_app': 'calculator'
    }
    return render_template('calc.html', **data)

# HEIC変換アプリのメインページ
@app.route('/converter')
def converter_page():
    """HEIC to JPG 変換ページ"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': 'HEIC to JPG 変換',
        'nav': APP_NAVIGATION,
        'current_app': 'converter'
    }
    return render_template('converter.html', **data)

# ファイルアップロードと変換処理 (変更なし)
@app.route('/convert', methods=['POST'])
def convert_file():
    if 'heic_file' not in request.files:
        return redirect(url_for('converter_page'))
    
    file = request.files['heic_file']
    
    if file.filename == '' or not file.filename.lower().endswith(('.heic', '.heif')):
        return redirect(url_for('converter_page'))

    try:
        heif_image = pillow_heif.read_heif(file.stream)
        image = heif_image.to_pillow()
        exif_bytes = heif_image.info.get("exif")
        base_name = os.path.splitext(file.filename)[0]
        jpg_filename = base_name + '.jpg'
        output = io.BytesIO()
        
        if exif_bytes:
            image.save(output, format="jpeg", exif=exif_bytes)
        else:
            image.save(output, format="jpeg")

        output.seek(0)
        
        return send_file(output,
                         mimetype='image/jpeg',
                         as_attachment=True,
                         download_name=jpg_filename)
                         
    except Exception as e:
        return f"ファイル処理中にエラーが発生しました。ファイル形式と内容を確認してください: {e}", 500


# === 単位換算アプリのメインページ ===
@app.route('/unit_converter', methods=['GET', 'POST'])
def unit_converter_page():
    result = None
    density_options = list(DENSITY_DATA.keys())
    
    # --- POSTリクエストの場合のみ、換算ロジックを実行 ---
    if request.method == 'POST':
        try:
            value = float(request.form['value'])
            unit_from = request.form['unit_from']
            unit_to = request.form['unit_to']
            density_type = request.form.get('density_type')
            
            # --- 換算ロジック ---
            
            # 1. 長さ換算
            if unit_from in ['m', 'cm', 'mm'] and unit_to in ['m', 'cm', 'mm']:
                base_value = value
                if unit_from == 'cm': base_value /= 100
                elif unit_from == 'mm': base_value /= 1000
                
                if unit_to == 'cm': final_value = base_value * 100
                elif unit_to == 'mm': final_value = base_value * 1000
                else: final_value = base_value
                
                result = f"{value} {unit_from} は {final_value:.4f} {unit_to} です"
            
            # 2. 重さ換算
            elif unit_from in ['t', 'kg', 'g'] and unit_to in ['t', 'kg', 'g']:
                base_value = value
                if unit_from == 't': base_value *= 1000
                elif unit_from == 'g': base_value /= 1000
                
                if unit_to == 't': final_value = base_value / 1000
                elif unit_to == 'g': final_value = base_value * 1000
                else: final_value = base_value

                result = f"{value} {unit_from} は {final_value:.4f} {unit_to} です"

            # 3. 体積(m³)と重さ(t)の比重換算
            elif unit_from == 'm3' and unit_to == 't' and density_type:
                density = DENSITY_DATA.get(density_type, 1.0)
                final_value = value * density
                result = f"【{density_type}】の場合: {value} m³ は {final_value:.4f} t (トン) です"
            
            # 4. 重さ(t)と体積(m³)の比重逆換算
            elif unit_from == 't' and unit_to == 'm3' and density_type:
                density = DENSITY_DATA.get(density_type, 1.0)
                if density == 0:
                    result = "比重がゼロの物質は換算できません。"
                else:
                    final_value = value / density
                    result = f"【{density_type}】の場合: {value} t (トン) は {final_value:.4f} m³ です"
            
            # 5. 換算サポート外
            elif unit_from == unit_to:
                result = f"同じ単位です: {value} {unit_from}"
            else:
                result = "現在、その単位間の換算はサポートされていません。比重換算の場合は、単位の組み合わせと比重の種類を確認してください。"


        except ValueError:
            result = "数値として有効な値を入力してください。"
        except Exception as e:
            result = f"エラーが発生しました: {e}"

    # テンプレートに渡すデータの定義
    data = {
        'app_name': APP_NAME,
        'page_title': '単位換算',
        'result': result,
        'density_options': density_options,
        # ★ 修正: navとcurrent_appを渡す
        'nav': APP_NAVIGATION,
        'current_app': 'unit_converter'
    }
    
    return render_template('unit_converter.html', **data)


# =================================================================
# === DXF座標出力ツール ===
# =================================================================

@app.route('/dxf_tool')
def dxf_tool_page():
    """DXF座標出力ページ"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': 'DXF座標出力ツール',
        'nav': APP_NAVIGATION,
        'current_app': 'dxf_tool'
    }
    return render_template('dxf_tool.html', **data)

# DXF生成処理 (変更なし)
@app.route('/generate_dxf', methods=['POST'])
def generate_dxf():
    # フォームから座標テキストデータを取得 (Hidden Fieldから)
    coords_text = request.form.get('coords_data', '')
    radius_str = request.form.get('circle_radius', '1.0')
    
    if not coords_text:
        return "座標データがありません。", 400

    try:
        radius = float(radius_str)
        if radius <= 0:
             radius = 1.0 # 半径が不正な場合はデフォルト値
    except ValueError:
        radius = 1.0

    points = []
    # テキストデータを解析し、座標リストを作成 (X, Y, Z形式の行データ)
    for line in coords_text.strip().split('\n'):
        parts = line.split(',')
        if len(parts) >= 2:
            try:
                # X, Yは必須。Zは省略可能（フォーム側で '0.0' に設定済み）
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                z = float(parts[2].strip()) if len(parts) >= 3 else 0.0
                points.append((x, y, z))
            except ValueError:
                # 無効な行はスキップ
                continue
    
    if not points:
        return "有効な座標データが見つかりませんでした。", 400

    # DXFドキュメントの作成
    doc = ezdxf.new(dxfversion='R2010')
    msp = doc.modelspace()
    
    # 各点を中心とする円をDXFに追加
    for x, y, z in points:
        # DXFのCIRCLEエンティティを追加。Z座標も使用可能。
        msp.add_circle(center=(x, y, z), radius=radius, dxfattribs={'layer': 'POINTS', 'color': 1}) # 色は赤
    
    # DXFデータをメモリに出力
    stream = io.StringIO()
    doc.write(stream)
    stream.seek(0)
    
    # ストリームをバイトデータに変換して送る
    dxf_data = io.BytesIO(stream.getvalue().encode('utf-8'))
    
    return send_file(
        dxf_data,
        mimetype='application/dxf',
        as_attachment=True,
        download_name='coordinate_circles.dxf'
    )


# =================================================================
# === 比較見積もりツール ===
# =================================================================

@app.route('/comparison_tool')
def comparison_tool_page():
    """比較見積もりツールページ"""
    # ★ 修正: navとcurrent_appを渡す
    data = {
        'app_name': APP_NAME, 
        'page_title': '比較見積もりツール',
        'nav': APP_NAVIGATION,
        'current_app': 'comparison_tool'
    }
    return render_template('comparison_tool.html', **data)

# =================================================================