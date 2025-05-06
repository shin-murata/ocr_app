from flask import Flask, request, render_template, redirect, url_for, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import pytesseract
import os
from dotenv import load_dotenv  # 追加
from PIL import Image
import csv
from paddleocr import PaddleOCR
import layoutparser as lp

# 環境変数を強制的に上書きして読み込む
load_dotenv(override=True)

# デバッグ用に環境変数を出力
print(f"TESSERACT_CMD: {os.getenv('TESSERACT_CMD')}")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")

# Tesseractのパスを設定
tesseract_cmd = os.getenv('TESSERACT_CMD')
if not tesseract_cmd:
    raise RuntimeError("TESSERACT_CMD が設定されていません。環境変数を確認してください。")
pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# データベース設定を環境変数から読み込む
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# モデル定義
class OCRResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)

# アプリケーションコンテキスト内でデータベースを初期化
with app.app_context():
    db.create_all()

# ホームページ
@app.route('/')
def home():
    return render_template('index.html')

# PDFアップロード処理
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "ファイルが選択されていません", 400

    file = request.files['file']
    if file.filename == '':
        return "ファイル名が空です", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # アップロードされたファイルを保存
    try:
        file.save(filepath)
        print(f"ファイルが保存されました: {filepath}")
    except Exception as e:
        return f"ファイルの保存中にエラーが発生しました: {str(e)}", 500

    extracted_text = ""

    # PDF または画像ファイルを処理
    if filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
        try:
            extracted_text = process_with_paddleocr(filepath)
            print("PaddleOCR による OCR 処理が完了しました。")
        except Exception as e:
            return f"PaddleOCR の処理中にエラーが発生しました: {str(e)}", 500

    # レイアウト検出を実行
    try:
        layout = process_with_layoutparser(filepath)
        print("Detectron2 によるレイアウト検出が完了しました。")
    except Exception as e:
        return f"レイアウト検出中にエラーが発生しました: {str(e)}", 500

    # 検出結果をターミナルに出力
    print(f"Layout Detection Result for {filename}:\n{layout}")

    # OCR結果をターミナルに出力
    print(f"OCR Result for {filename}:\n{extracted_text}")

    # データベースの内容をクリア
    try:
        OCRResult.query.delete()  # データベース内の全データを削除
        db.session.commit()  # コミットを忘れずに行う
        print("データベースの内容をクリアしました。")
    except Exception as e:
        return f"データベースのクリア中にエラーが発生しました: {str(e)}", 500

    # 新しいデータを保存
    try:
        result = OCRResult(filename=filename, text=extracted_text)
        db.session.add(result)
        db.session.commit()
        print("OCR結果がデータベースに保存されました。")
    except Exception as e:
        return f"データベース保存中にエラーが発生しました: {str(e)}", 500

    # CSVファイルに結果を保存
    try:
        with open('ocr_results.csv', 'w', encoding='utf-8') as f:
            f.write('ID,Filename,Text\n')
            results = OCRResult.query.all()
            for result in results:
                f.write(f"{result.id},{result.filename},\"{result.text}\"\n")
        print("OCR結果をCSVファイルに保存しました: ocr_results.csv")
    except Exception as e:
        return f"CSVファイルの保存中にエラーが発生しました: {str(e)}", 500

    return redirect(url_for('results'))

# 結果表示ページ
@app.route('/results')
def results():
    result = OCRResult.query.order_by(OCRResult.id.desc()).first()  # 最新のデータを取得
    return render_template('results.html', result=result)

# CSV出力エンドポイント
@app.route('/download_csv')
def download_csv():
    # 最新のデータを取得
    result = OCRResult.query.order_by(OCRResult.id.desc()).first()
    if not result:
        return "データがありません。", 404

    # CSVファイルを生成
    csv_file_path = 'ocr_results.csv'
    try:
        with open(csv_file_path, 'w', encoding='utf-8') as f:
            f.write('ID,Filename,Text\n')
            f.write(f"{result.id},{result.filename},\"{result.text}\"\n")
        print("CSVファイルを生成しました: ocr_results.csv")
    except Exception as e:
        return f"CSVファイルの生成中にエラーが発生しました: {str(e)}", 500

    # 生成したCSVファイルをダウンロード
    if os.path.exists(csv_file_path):
        return send_file(csv_file_path, as_attachment=True, download_name='ocr_results.csv', mimetype='text/csv')
    else:
        return "CSVファイルが見つかりません。", 404

# PaddleOCR の初期化
ocr = PaddleOCR(use_angle_cls=True, lang='japan', det_db_box_thresh=0.5)

def process_with_paddleocr(filepath):
    """
    PaddleOCR を使用して画像または PDF を処理し、表形式に整形
    """
    # OCR 処理
    result = ocr.ocr(filepath, cls=True)
    extracted_text = ""

    # テーブル形式に整形
    table_data = []  # テーブルデータを格納するリスト
    for line in result[0]:
        text = line[1][0]  # 認識されたテキスト
        confidence = line[1][1]  # 信頼度
        bbox = line[0]  # バウンディングボックス（位置情報）

        # bbox の構造を確認
        print(f"Bounding Box: {bbox}")

        # テーブルデータに追加
        table_data.append({
            "text": text,
            "confidence": confidence,
            "bbox": bbox
        })

    # 列の位置を基にデータを整形
    table_data.sort(key=lambda x: (min(point[1] for point in x["bbox"]), x["bbox"][0][0]))  # Y座標、X座標でソート
    rows = []
    current_row = []
    last_y = None

    for item in table_data:
        # bbox の Y 座標の最小値を取得
        y = min(point[1] for point in item["bbox"])  # 各点の Y 座標の最小値を取得
        if last_y is None or abs(y - last_y) > 10:  # 新しい行を判定（Y座標の差で判断）
            if current_row:
                rows.append(current_row)
            current_row = [item["text"]]
            last_y = y
        else:
            current_row.append(item["text"])

    if current_row:
        rows.append(current_row)

    # 表形式の文字列を生成
    extracted_text = "\n".join(["\t".join(row) for row in rows])

    return extracted_text

def process_with_layoutparser(image_path):
    # Detectron2 モデルを使用したレイアウト検出
    model = lp.Detectron2LayoutModel(
        config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
        label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
        extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.8]
    )
    image = lp.io.read(image_path)
    layout = model.detect(image)
    return layout

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # アップロードフォルダを作成
    app.run(debug=True)

# OCR結果（例として直接文字列を記述）
ocr_result_text = """
ここにOCRで読み取ったテキストを貼り付けてください。
"""