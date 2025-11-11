import logging
import os
import io
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, g
from PIL import Image

# optional HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:
    HEIF_AVAILABLE = False

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
    'forum': {'name': '💬 詰所（掲示板・チャット）', 'url': 'forum'},
}

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        body TEXT NOT NULL,
        tags TEXT,
        created_at TEXT NOT NULL
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
    )
    ''')
    db.commit()
    db.close()

# ← ここで直接初期化を呼ぶ（before_first_request を使わない）
try:
    init_db()
except Exception:
    # 起動時に DB 作成できなくてもアプリを止めたくない場合はログ出力のみ
    import logging
    logging.getLogger(__name__).warning('DB 初期化に失敗しました（起動後に再試行してください）。')

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 共通コンテキストを返すヘルパー
def base_context(current_app='', page_title=''):
    return {
        'nav': APP_NAVIGATION,
        'current_app': current_app,
        'page_title': page_title,
        'app_name': APP_NAME,
    }

# ルート定義
@app.route('/')
def index():
    ctx = base_context(current_app='index', page_title='ホーム')
    return render_template('index.html', **ctx)

@app.route('/converter')
def converter_page():
    ctx = base_context(current_app='converter', page_title='HEIC to JPG 変換')
    return render_template('converter.html', **ctx)

@app.route('/convert', methods=['POST'])
def convert_file():
    heic = request.files.get('heic_file')
    if not heic:
        flash('ファイルを選択してください。', 'warning')
        return redirect(url_for('converter_page'))

    if not HEIF_AVAILABLE:
        flash('サーバーに HEIC を処理するライブラリ(pillow-heif)がインストールされていません。', 'danger')
        return redirect(url_for('converter_page'))

    data = heic.read()
    try:
        img = Image.open(io.BytesIO(data))
    except Exception as e:
        flash(f'HEIC ファイルの読み込みに失敗しました: {e}', 'danger')
        return redirect(url_for('converter_page'))

    exif = img.info.get('exif', None)
    rgb = img.convert('RGB')
    out = io.BytesIO()
    save_kwargs = {'format': 'JPEG', 'quality': 95}
    if exif:
        save_kwargs['exif'] = exif
    rgb.save(out, **save_kwargs)
    out.seek(0)

    original_name = getattr(heic, 'filename', 'image.heic') or 'image.heic'
    base = os.path.splitext(original_name)[0]
    download_name = f'{base}.jpg'
    return send_file(out, mimetype='image/jpeg', as_attachment=True, download_name=download_name)

@app.route('/unit_converter', methods=['GET', 'POST'])
def unit_converter_page():
    ctx = base_context(current_app='unit_converter', page_title='単位換算')

    # 材料の比重（密度: kg/m3）
    MATERIALS = {
        'soil_compacted': {'label': '土(締固め)', 'density': 1700},
        'crushed_stone': {'label': '砕石', 'density': 2000},
        'concrete_rebar': {'label': 'コンクリート（有筋）', 'density': 2400},
        'concrete_plain': {'label': 'コンクリート（無筋）', 'density': 2350},
        'asphalt': {'label': 'アスファルト', 'density': 2300},
        'steel': {'label': '鋼材', 'density': 7850},
    }

    result = None
    if request.method == 'POST':
        try:
            mode = request.form.get('mode', 'unit')  # 'unit' または 'material'
            # 単位テーブル（変換は内部で kg / m3 / m3 を基準に行う）
            weight_table = {'kg':1.0, 'g':0.001, 't':1000.0, 'lb':0.45359237}
            volume_table = {'m3':1.0, 'l':0.001, 'ml':0.000001}

            if mode == 'unit':
                category = request.form.get('category', 'length')
                value = float(request.form.get('value', '0') or 0)
                frm = request.form.get('from_unit')
                to = request.form.get('to_unit')

                def convert(value, frm, to, table):
                    base = value * table[frm]           # convert to base unit
                    return base / table[to]             # convert base to target

                if category == 'length':
                    table = {'m':1.0, 'cm':0.01, 'mm':0.001, 'km':1000.0, 'ft':0.3048, 'in':0.0254}
                elif category == 'weight':
                    table = weight_table
                elif category == 'volume':
                    table = volume_table
                else:
                    raise ValueError('未対応のカテゴリ')

                if frm not in table or to not in table:
                    raise ValueError('不正な単位')

                out_val = convert(value, frm, to, table)
                result = {
                    'mode': 'unit',
                    'value': value,
                    'from': frm,
                    'to': to,
                    'out': round(out_val, 6)
                }

            else:  # material mode: 体積 <-> 質量
                direction = request.form.get('direction', 'vol_to_mass')  # 'vol_to_mass' or 'mass_to_vol'
                value = float(request.form.get('value', '0') or 0)
                vol_unit = request.form.get('vol_unit', 'm3')
                mass_unit = request.form.get('mass_unit', 'kg')
                material_key = request.form.get('material')
                if material_key not in MATERIALS:
                    raise ValueError('不正な材料')

                density = MATERIALS[material_key]['density']  # kg / m3

                # 単位を基準に揃える
                if vol_unit not in volume_table or mass_unit not in weight_table:
                    raise ValueError('不正な単位')

                if direction == 'vol_to_mass':
                    # 入力の体積 -> m3
                    vol_m3 = value * volume_table[vol_unit]
                    mass_kg = vol_m3 * density
                    out_mass = mass_kg / weight_table[mass_unit]
                    result = {
                        'mode': 'material',
                        'direction': direction,
                        'material': MATERIALS[material_key]['label'],
                        'value': value,
                        'from_unit': vol_unit,
                        'to_unit': mass_unit,
                        'out': round(out_mass, 6),
                        'density': density
                    }
                else:
                    # 入力の質量 -> kg
                    mass_kg = value * weight_table[mass_unit]
                    vol_m3 = mass_kg / density
                    out_vol = vol_m3 / volume_table[vol_unit]
                    result = {
                        'mode': 'material',
                        'direction': direction,
                        'material': MATERIALS[material_key]['label'],
                        'value': value,
                        'from_unit': mass_unit,
                        'to_unit': vol_unit,
                        'out': round(out_vol, 6),
                        'density': density
                    }

        except Exception as e:
            flash(f'換算に失敗しました: {e}', 'danger')

    ctx['result'] = result
    ctx['materials'] = MATERIALS
    return render_template('unit_converter.html', **ctx)

@app.route('/dxf_tool')
def dxf_tool_page():
    ctx = base_context(current_app='dxf_tool', page_title='DXF座標出力ツール')
    return render_template('dxf_tool.html', **ctx)

@app.route('/generate_dxf', methods=['POST'])
def generate_dxf():
    flash('DXF生成処理は未実装です。', 'info')
    return redirect(url_for('dxf_tool_page'))

@app.route('/calculator')
def calculator():
    ctx = base_context(current_app='calculator', page_title='計算ツール')
    return render_template('calc.html', **ctx)

@app.route('/comparison_tool')
def comparison_tool_page():
    ctx = base_context(current_app='comparison_tool', page_title='比較見積もりツール')
    return render_template('comparison_tool.html', **ctx)

# --- フォーラム（記事一覧・投稿・詳細・コメント） ---
@app.route('/forum', methods=['GET'])
def forum():
    tag = request.args.get('tag', '').strip().lower()
    db = get_db()
    cur = db.cursor()
    if tag:
        like = f'%{tag}%'
        cur.execute("SELECT * FROM articles WHERE lower(tags) LIKE ? ORDER BY created_at DESC", (like,))
    else:
        cur.execute("SELECT * FROM articles ORDER BY created_at DESC")
    articles = cur.fetchall()
    ctx = base_context(current_app='forum', page_title='知恵袋・掲示板')
    return render_template('forum.html', articles=articles, tag=tag, **ctx)

@app.route('/post_article', methods=['POST'])
def post_article():
    title = (request.form.get('title') or '').strip()
    body = (request.form.get('body') or '').strip()
    tags_raw = (request.form.get('tags') or '').strip()
    if not body:
        flash('本文は必須です。', 'warning')
        return redirect(url_for('forum'))

    # 正規化: カンマ区切り -> 小文字・空白除去
    tags = ','.join([t.strip().lower() for t in tags_raw.split(',') if t.strip()])

    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO articles (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
                (title, body, tags, datetime.utcnow().isoformat()))
    db.commit()
    flash('記事を投稿しました（匿名）。', 'success')
    return redirect(url_for('forum'))

@app.route('/article/<int:article_id>', methods=['GET'])
def view_article(article_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    article = cur.fetchone()
    if not article:
        flash('記事が見つかりません。', 'warning')
        return redirect(url_for('forum'))

    # コメント取得
    cur.execute("SELECT * FROM comments WHERE article_id = ? ORDER BY created_at ASC", (article_id,))
    comments = cur.fetchall()

    # 類似記事（同じタグを1つでも持つもの、最大6件）
    similar = []
    if article['tags']:
        tags = [t.strip() for t in article['tags'].split(',') if t.strip()]
        q_like = ' OR '.join(['lower(tags) LIKE ?' for _ in tags])
        params = [f'%{t}%' for t in tags]
        cur.execute(f"SELECT * FROM articles WHERE ({q_like}) AND id != ? ORDER BY created_at DESC LIMIT 6", (*params, article_id))
        similar = cur.fetchall()

    ctx = base_context(current_app='forum', page_title=article['title'] or '記事')
    return render_template('article.html', article=article, comments=comments, similar=similar, **ctx)

@app.route('/post_comment/<int:article_id>', methods=['POST'])
def post_comment(article_id):
    body = (request.form.get('comment_body') or '').strip()
    if not body:
        flash('コメントを入力してください。', 'warning')
        return redirect(url_for('view_article', article_id=article_id))
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO comments (article_id, body, created_at) VALUES (?, ?, ?)",
                (article_id, body, datetime.utcnow().isoformat()))
    db.commit()
    flash('コメントを投稿しました（匿名）。', 'success')
    return redirect(url_for('view_article', article_id=article_id))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)