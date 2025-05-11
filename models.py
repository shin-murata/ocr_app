from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON

db = SQLAlchemy()

class OCRResult(db.Model):
    __tablename__ = 'ocr_result'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    table_json = db.Column(JSON, nullable=True)  # ✅ 2DテーブルをJSON形式で保存
