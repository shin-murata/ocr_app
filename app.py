from flask import Flask, request, render_template, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import pytesseract
import os
import csv
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
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
    file.save(filepath)

    # 画像をOCR処理
    image = Image.open(filepath)  # 画像ファイルを開く
    extracted_text = pytesseract.image_to_string(image, lang='jpn')

    # データベース保存
    result = OCRResult(filename=filename, text=extracted_text)
    db.session.add(result)
    db.session.commit()

    return redirect(url_for('results'))

# 結果表示ページ
@app.route('/results')
def results():
    results = OCRResult.query.all()
    return render_template('results.html', results=results)

# CSV出力エンドポイント
@app.route('/download_csv')
def download_csv():
    # データベースからすべての結果を取得
    results = OCRResult.query.all()

    # CSVデータを生成
    def generate():
        # ヘッダー行
        yield ','.join(['ID', 'Filename', 'Text']) + '\n'
        # 各行のデータ
        for result in results:
            yield ','.join([str(result.id), result.filename, result.text.replace('\n', ' ')]) + '\n'

    # レスポンスをCSV形式で返す
    return Response(
        generate(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=ocr_results.csv'}
    )

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)