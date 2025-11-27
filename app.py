import os
import io
# zipfileのインポートを追加
import zipfile
import logging
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, g
from PIL import Image
import ezdxf
from io import StringIO, BytesIO # BytesIOも明示的にインポート
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import re
from werkzeug.routing import BuildError

# --- 定数定義（追加） ---
MAX_TAGS = 5
FORBIDDEN_WORDS = ['spam', 'test']
MAX_ARTICLE_LENGTH = 5000
MAX_COMMENT_LENGTH = 1000

def check_spam_content(body, max_len):
    """プレースホルダーのスパムチェック関数"""
    if len(body) > max_len:
        return True, f"本文が長すぎます (最大 {max_len} 文字)"
    # ここに正規表現やキーワードチェックを追加可能
    return False, ""
# --- 定数定義（追加ここまで） ---

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

# DB 初期化を試行
try:
    init_db()
except Exception:
    import logging
    logging.getLogger(__name__).warning('DB 初期化に失敗しました（起動後に再試行してください）。')

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def safe_url_for(endpoint, **values):
    """
    url_for を安全に呼び出す。存在しない endpoint の場合は '#' を返す。
    テンプレートから呼べるよう jinja globals に登録する。
    """
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return '#'

# テンプレートで safe_url_for を使えるよう登録
app.jinja_env.globals['safe_url_for'] = safe_url_for

# base_context はエンドポイント名をそのまま渡す（url_for はテンプレート側で評価）
def base_context(current_app='', page_title=''):
    return {
        'nav': APP_NAVIGATION,
        'current_app': current_app,
        'page_title': page_title,
        'app_name': APP_NAME,
    }

# レートリミッター設定
storage_uri = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri=storage_uri,
    app=app
)

# --- ルーティングの追加・修正 ---

# 1. ホームページ (ルート / ) の追加
@app.route('/')
def index():
    """ホーム (ダッシュボード)"""
    ctx = base_context(current_app='index', page_title=APP_NAME)
    # ここにダッシュボード情報を追加する
    return render_template('index.html', **ctx)

# 2. HEIC to JPG 変換ページ (GET) の追加 (ナビゲーションで 'converter_page' を参照しているため)
@app.route('/converter')
def converter_page():
    """HEIC to JPG 変換ページ (GET)"""
    ctx = base_context(current_app='converter', page_title='HEIC to JPG 変換')
    ctx['HEIF_AVAILABLE'] = HEIF_AVAILABLE # ライブラリが利用可能かテンプレートに渡す
    return render_template('converter.html', **ctx)

# 記事投稿
@app.route('/post_article', methods=['POST'])
@limiter.limit("5 per minute") # 投稿系なので制限を強化
def post_article_submit():
    title = (request.form.get('title') or '').strip()
    body = (request.form.get('body') or '').strip()
    tags_raw = (request.form.get('tags') or '').strip()

    # タグ数チェック・正規化
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    if len(tags) > MAX_TAGS:
        flash(f'タグは最大 {MAX_TAGS} 個までです。', 'warning')
        return redirect(url_for('forum'))
    # タグに禁止語が含まれないか
    for t in tags:
        for w in FORBIDDEN_WORDS:
            if w.lower() in t.lower():
                flash('タグに不適切な語句が含まれています。', 'warning')
                return redirect(url_for('forum'))
    tags_joined = ','.join(tags)

    if not body:
        flash('本文は必須です。', 'warning')
        return redirect(url_for('forum'))

    # スパムチェック（記事は長めを許容）
    is_spam, reason = check_spam_content(body, MAX_ARTICLE_LENGTH)
    if is_spam:
        flash(f'投稿を受け付けられません: {reason}', 'warning')
        return redirect(url_for('forum'))

    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO articles (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
                (title, body, tags_joined, datetime.utcnow().isoformat()))
    db.commit()
    flash('記事を投稿しました（匿名）。', 'success')
    return redirect(url_for('forum'))

# コメント投稿
@app.route('/post_comment/<int:article_id>', methods=['POST'])
@limiter.limit("10 per hour") # コメント投稿も制限を強化
def post_comment_submit(article_id):
    body = (request.form.get('comment_body') or '').strip()
    if not body:
        flash('コメントを入力してください。', 'warning')
        return redirect(url_for('view_article', article_id=article_id))

    # スパムチェック等...
    is_spam, reason = check_spam_content(body, MAX_COMMENT_LENGTH)
    if is_spam:
        flash(f'コメントを受け付けられません: {reason}', 'warning')
        return redirect(url_for('view_article', article_id=article_id))

    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO comments (article_id, body, created_at) VALUES (?, ?, ?)",
                (article_id, body, datetime.utcnow().isoformat()))
    db.commit()
    flash('コメントを投稿しました（匿名）。', 'success')
    return redirect(url_for('view_article', article_id=article_id))

# === HEIC変換 (Zip対応に修正) ===
@app.route('/convert', methods=['POST'])
@limiter.limit("30 per hour")
def convert_file():
    
    # 複数ファイルを取得
    heic_files = request.files.getlist('heic_file') 

    if not heic_files or all(f.filename == '' for f in heic_files):
        flash('ファイルが選択されていません。', 'warning')
        return redirect(url_for('converter_page'))

    if not HEIF_AVAILABLE:
        flash('サーバーに HEIC を処理するライブラリ(pillow-heif)がインストールされていません。', 'danger')
        return redirect(url_for('converter_page'))

    # メモリ内でZipファイルを作成
    zip_buffer = io.BytesIO()
    
    # 変換成功したファイル数をカウント
    converted_count = 0
    
    # ZipFileオブジェクトを作成
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 取得したファイルを一つずつ処理
        for heic in heic_files:
            if heic.filename == '' or not heic.filename.lower().endswith(('.heic', '.heif')):
                continue

            try:
                # ファイル名を安全なものに（必要であれば）
                original_name = heic.filename
                base = os.path.splitext(original_name)[0]
                # Zip内のファイル名
                jpg_filename = f'{base}.jpg'

                # メモリ内で変換処理
                data = heic.read()
                img = Image.open(io.BytesIO(data))
                
                exif = img.info.get('exif', None)
                rgb = img.convert('RGB')
                
                # 個別のJPGをメモリに保存
                jpg_buffer = io.BytesIO()
                save_kwargs = {'format': 'JPEG', 'quality': 95}
                if exif:
                    save_kwargs['exif'] = exif
                
                rgb.save(jpg_buffer, **save_kwargs)
                jpg_buffer.seek(0)
                
                # ZipファイルにJPGデータを書き込む
                zf.writestr(jpg_filename, jpg_buffer.getvalue())
                converted_count += 1
                
            except Exception as e:
                # 1つのファイルが失敗しても続行する（ログには残す）
                logging.warning(f"ファイル '{heic.filename}' の変換に失敗: {e}")
                pass # エラーのファイルはスキップ

    if converted_count == 0:
        flash('有効なHEICファイルの変換にすべて失敗しました。', 'danger')
        return redirect(url_for('converter_page'))

    zip_buffer.seek(0)
    
    # Zipファイルとしてダウンロードさせる
    flash(f'{converted_count} 件のHEICファイルをJPGに変換しました。', 'success')
    return send_file(
        zip_buffer, 
        mimetype='application/zip', 
        as_attachment=True, 
        download_name='Converted_HEIC_Files.zip'
    )

# === 単位換算アプリのメインページ ===
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
                    base = value * table[frm]        # convert to base unit
                    return base / table[to]          # convert base to target

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

# DXF座標出力ツール
@app.route('/dxf_tool')
def dxf_tool_page():
    ctx = base_context(current_app='dxf_tool', page_title='DXF座標出力ツール')
    return render_template('dxf_tool.html', **ctx)

@app.route('/generate_dxf', methods=['POST'])
@limiter.limit("60 per hour")
def generate_dxf():
    coord_text = (request.form.get('coordinate_data') or '').strip()
    layer_name = (request.form.get('app_layer') or 'POINTS').strip()
    filename = (request.form.get('dxf_name') or 'coordinate_output').strip()
    if not coord_text:
        flash('座標データが入力されていません。', 'warning')
        return redirect(url_for('dxf_tool_page'))

    points = []
    for raw_line in coord_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) == 1:
            continue
        if len(parts) == 2:
            label = ''
            try:
                x = float(parts[0])
                y = float(parts[1])
            except Exception:
                continue
        else:
            try:
                x = float(parts[-2])
                y = float(parts[-1])
                label = ','.join(parts[:-2])
            except Exception:
                continue
        points.append({'label': label, 'x': x, 'y': y})

    if not points:
        flash('有効な座標が見つかりませんでした。フォーマットを確認してください。', 'warning')
        return redirect(url_for('dxf_tool_page'))

    try:
        doc = ezdxf.new(dxfversion='R2010')
        if layer_name not in doc.layers:
            doc.layers.new(name=layer_name)
        msp = doc.modelspace()

        for pt in points:
            x, y = pt['x'], pt['y']
            msp.add_point((x, y), dxfattribs={'layer': layer_name})
            if pt['label']:
                txt = msp.add_text(str(pt['label']), dxfattribs={'height': 0.25, 'layer': layer_name})
                txt.set_pos((x + 0.2, y + 0.2), align='LEFT')

        buf = BytesIO()
        doc.saveas(buf)
        buf.seek(0)
        download_name = f"{filename}.dxf"
        return send_file(buf, mimetype='application/dxf', as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f'DXF 生成に失敗しました: {e}', 'danger')
        return redirect(url_for('dxf_tool_page'))

# 計算ツール
@app.route('/calculator')
def calculator():
    ctx = base_context(current_app='calculator', page_title='計算ツール')
    return render_template('calc.html', **ctx)

# 比較見積もりツール
@app.route('/comparison_tool')
def comparison_tool_page():
    ctx = base_context(current_app='comparison_tool', page_title='比較見積もりツール')
    return render_template('comparison_tool.html', **ctx)

# --- フォーラム ---
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
    
    def get_tag_list(tags_str):
        return [t.strip() for t in (tags_str or '').split(',') if t.strip()]
    
    return render_template('forum.html', articles=articles, tag=tag, get_tag_list=get_tag_list, **ctx)

# 記事詳細
@app.route('/article/<int:article_id>', methods=['GET'])
def view_article(article_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    article = cur.fetchone()
    if not article:
        flash('記事が見つかりません。', 'warning')
        return redirect(url_for('forum'))

    cur.execute("SELECT * FROM comments WHERE article_id = ? ORDER BY created_at ASC", (article_id,))
    comments = cur.fetchall()

    similar = []
    if article['tags']:
        tags = [t.strip() for t in article['tags'].split(',') if t.strip()]
        if tags:
            q_like = ' OR '.join(['lower(tags) LIKE ?' for _ in tags])
            params = [f'%{t}%' for t in tags]
            cur.execute(f"SELECT * FROM articles WHERE ({q_like}) AND id != ? ORDER BY created_at DESC LIMIT 6", (*params, article_id))
            similar = cur.fetchall()

    def get_tag_list(tags_str):
        return [t.strip() for t in (tags_str or '').split(',') if t.strip()]

    ctx = base_context(current_app='forum', page_title=article['title'] or '記事')
    return render_template('article.html', article=article, comments=comments, similar=similar, get_tag_list=get_tag_list, **ctx)


@app.route('/_routes_debug')
def _routes_debug():
    out = []
    for rule in app.url_map.iter_rules():
        out.append(f"{rule.endpoint} -> {rule.rule} [{','.join(rule.methods)}]")
    return "<br>".join(sorted(out))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)