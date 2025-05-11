# ── ここから必ずファイル先頭 ──
import os

# GPU CUDA を無効化
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import paddle
# デバイスを CPU に固定
paddle.set_device("cpu")

# ✅ PaddleOCR を使う前にインポート
from paddleocr import PaddleOCR

# ✅ PaddleOCR 読み込み後に disable_static() を呼ぶ
paddle.disable_static()  # ✅ これを追加！

# 以降、PaddleOCR インスタンス化
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='japan',
    det_db_box_thresh=0.5,
    use_gpu=False,
    layout=False,
    table=False
)

# ── ここまで GPU 無効化 ──

from flask import Flask, request, render_template, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pytesseract
from dotenv import load_dotenv
from PIL import Image
import csv
import layoutparser as lp
from layoutparser.visualization import draw_box
import cv2
import numpy as np



# ── セル分割ユーティリティ関数 ──
def segment_table_cells(pil_image, table_block):
    """
    指定された table_block 領域を切り出し、
    水平線＋垂直線の交点から各セルの矩形を推定して返します。
    """
    img = np.array(pil_image.convert("RGB"))
    # Rectangle から座標を取得
    x1 = int(table_block.block.x_1)
    y1 = int(table_block.block.y_1)
    x2 = int(table_block.block.x_2)
    y2 = int(table_block.block.y_2)
    tbl = img[y1:y2, x1:x2]

    # 二値化＋反転
    gray = cv2.cvtColor(tbl, cv2.COLOR_RGB2GRAY)
    _, bw = cv2.threshold(gray, 0, 255,
                         cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 水平線抽出
    hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (tbl.shape[1]//15, 1))
    horizontal = cv2.dilate(cv2.erode(bw, hor_kernel, iterations=1), hor_kernel, iterations=1)
    # 垂直線抽出
    ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, tbl.shape[0]//15))
    vertical = cv2.dilate(cv2.erode(bw, ver_kernel, iterations=1), ver_kernel, iterations=1)

    # 交点取得
    intersections = cv2.bitwise_and(horizontal, vertical)
    pts = cv2.findNonZero(intersections)
    if pts is None:
        return []
    pts = pts.reshape(-1, 2)
    xs = sorted(set(pts[:,0].tolist()))
    ys = sorted(set(pts[:,1].tolist()))

    # 近接値をまとめるクラスタリング
    def cluster(vals, thr=10):
        clusters = []
        for v in vals:
            if not clusters or abs(v - clusters[-1][-1]) > thr:
                clusters.append([v])
            else:
                clusters[-1].append(v)
        return [int(sum(c)/len(c)) for c in clusters]

    xs = cluster(xs)
    ys = cluster(ys)

    # 各セル領域リスト化
    cells = []
    for i in range(len(ys)-1):
        for j in range(len(xs)-1):
            xa, xb = xs[j], xs[j+1]
            ya, yb = ys[i], ys[i+1]
            cells.append((x1+xa, y1+ya, x1+xb, y1+yb))
    return cells

# ── Detectron2 互換パッチ ──
Image.LINEAR = Image.BILINEAR
from layoutparser.models.detectron2.layoutmodel import Detectron2LayoutModel

# 環境変数読み込み
load_dotenv(override=True)
TESS_CMD = os.getenv('TESSERACT_CMD')
if not TESS_CMD:
    raise RuntimeError("TESSERACT_CMD が設定されていません。")
pytesseract.pytesseract.tesseract_cmd = TESS_CMD

# Flask / DB 初期化
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# 画像配信用
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# レイアウト検出モデル
MODEL = Detectron2LayoutModel(
    config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
    model_path=os.path.expanduser("~/.cache/layoutparser/checkpoints/PubLayNet/model_final.pth"),
    extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
    label_map={0:"Text",1:"Title",2:"List",3:"Table",4:"Figure"}
)

# DB モデル
class OCRResult(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    text     = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

def process_with_paddleocr(path):
    res = ocr.ocr(path, cls=True)
    return "\n".join([line[1][0] for line in res[0]])

def process_with_layoutparser(path):
    img = Image.open(path).convert("RGB")
    return MODEL.detect(img)

# ホーム
@app.route('/')
def home():
    return render_template('index.html')

# アップロード & 処理
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "ファイルが選択されていません", 400
    file = request.files['file']
    if file.filename == '':
        return "ファイル名が空です", 400

    # フォルダ作成（必須）
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 1) OCR
    full_text = process_with_paddleocr(filepath)

    # 2) レイアウト検出
    layout = process_with_layoutparser(filepath)

    # 3) セル分割 & OCRで2D配列
    tbl_blocks = [b for b in layout if b.type=='Table']
    table_rows = []
    if tbl_blocks:
        tbl = tbl_blocks[0]
        cells = segment_table_cells(Image.open(filepath), tbl)
        # 列数を推測
        col_starts = sorted({c[0] for c in cells})
        n_cols = len(col_starts)
        # 切り出しOCR
        # （upload_file() 内のセルごとの OCR 部分）
        cell_texts = []
        for (x1, y1, x2, y2) in cells:
            # セル領域を切り出し
            crop = Image.open(filepath).convert("RGB").crop((x1, y1, x2, y2))
            # NumPy 形式にして PaddleOCR に渡す
            res = ocr.ocr(np.array(crop), cls=True)

            # res[0] が None のときは空リスト扱いに
            lines = res[0] if (res and res[0] is not None) else []

            # 各行データからテキストだけ取り出し
            text = "".join([ln[1][0] for ln in lines])
            cell_texts.append(text)
        # 行ごとに分割
        for i in range(0, len(cell_texts), n_cols):
            table_rows.append(cell_texts[i:i+n_cols])
    
    # 可視化画像
    layout_image = None
    if tbl_blocks:
        vis = draw_box(Image.open(filepath), [tbl], box_width=3, box_color='orange')
        vis_np = np.array(vis.convert("RGB"))
        for (x1,y1,x2,y2) in cells:
            cv2.rectangle(vis_np, (x1,y1), (x2,y2), (0,0,255), 1)
        vis_img = Image.fromarray(vis_np)
        layout_image = f"layout_{filename}"
        vis_img.save(os.path.join(app.config['UPLOAD_FOLDER'], layout_image))

    # 4) DB 保存
    OCRResult.query.delete()
    db.session.commit()
    rec = OCRResult(filename=filename, text=full_text)
    db.session.add(rec)
    db.session.commit()

    # 5) 結果表示
    return render_template('results.html',
                           result=rec,
                           layout_image=layout_image,
                           table_rows=table_rows)

# CSVダウンロード
@app.route('/download_csv')
def download_csv():
    rec = OCRResult.query.order_by(OCRResult.id.desc()).first()
    if not rec:
        return "データがありません。", 404
    # CSV は table_rows から
    # ここは簡易的に full_text を改行で
    rows = rec.text.split("\n")
    path = 'ocr_results.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for r in rows:
            writer.writerow([r])
    return send_file(path, as_attachment=True,
                     download_name='ocr_results.csv',
                     mimetype='text/csv')

# エントリポイント
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
