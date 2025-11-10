import logging
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from PIL import Image
import io
import os

# ログを抑制
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- アプリ設定 ---
APP_NAME = 'ショクチョー！'
APP_NAVIGATION = {
    'index': {'name': '🏠 ホーム', 'url': 'index'},
    'utilities': {
        'name': '🛠️ 便利アプリ',
        'children': [
            {'id': 'converter', 'name': '📸 HEIC to JPG 変換', 'url': 'converter_page'},
            {'id': 'unit_converter', 'name': '📏 単位換算', 'url': 'unit_converter_page'},
            {'id': 'calculator', 'name': '📐 計算ツール', 'url': 'calculator'},
            {'id': 'dxf_tool', 'name': '🗺️ DXF座標出力ツール', 'url': 'dxf_tool_page'},
            {'id': 'comparison_tool', 'name': '📊 比較見積もりツール', 'url': 'comparison_tool_page'},
        ]
    },
    'forum': {'name': '💬 知恵袋・掲示板', 'url': 'forum'},
}

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# 共通コンテキストを返すヘルパー
def base_context(current_app='', page_title=''):
    return {
        'nav': APP_NAVIGATION,
        'current_app': current_app,
        'page_title': page_title,
        'app_name': APP_NAME,
    }

# ルート定義（テンプレートは layout.html を継承している前提）
@app.route('/')
def index():
    ctx = base_context(current_app='index', page_title='ホーム')
    return render_template('index.html', **ctx)

@app.route('/forum')
def forum():
    ctx = base_context(current_app='forum', page_title='知恵袋・掲示板')
    return render_template('forum.html', **ctx)

@app.route('/calculator')
def calculator():
    ctx = base_context(current_app='calculator', page_title='計算ツール')
    return render_template('calc.html', **ctx)

@app.route('/converter')
def converter_page():
    ctx = base_context(current_app='converter', page_title='HEIC to JPG 変換')
    return render_template('converter.html', **ctx)

@app.route('/convert', methods=['POST'])
def convert_file():
    # 最小限の処理 — ファイルがなければリダイレクト、あれば一時保存して戻す（実処理は未実装）
    heic = request.files.get('heic_file')
    if not heic:
        flash('ファイルを選択してください。', 'warning')
        return redirect(url_for('converter_page'))
    # TODO: HEIC -> JPG 変換を実装（現在は受け取り確認のみ）
    flash('ファイル受け取りました（変換処理は未実装）。', 'success')
    return redirect(url_for('converter_page'))

@app.route('/unit_converter', methods=['GET', 'POST'])
def unit_converter_page():
    ctx = base_context(current_app='unit_converter', page_title='単位換算')
    # POST時に計算結果を ctx に入れてテンプレートへ渡す想定
    if request.method == 'POST':
        # 例: form のデータ処理（必要に応じて実装）
        pass
    return render_template('unit_converter.html', **ctx)

@app.route('/dxf_tool')
def dxf_tool_page():
    ctx = base_context(current_app='dxf_tool', page_title='DXF座標出力ツール')
    return render_template('dxf_tool.html', **ctx)

@app.route('/generate_dxf', methods=['POST'])
def generate_dxf():
    # TODO: DXF 生成処理を実装
    flash('DXF生成処理は未実装です。', 'info')
    return redirect(url_for('dxf_tool_page'))

@app.route('/comparison_tool')
def comparison_tool_page():
    ctx = base_context(current_app='comparison_tool', page_title='比較見積もりツール')
    return render_template('comparison_tool.html', **ctx)

# 実行ブロック
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)