import os
import pytest
from flask import url_for
from app import app, db, OCRResult

# File: test_app.py

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in-memory SQLite for testing
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_home_page(client):
    """Test the home page."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"index.html" in response.data  # Ensure the template is rendered

def test_upload_file(client, tmp_path):
    """Test the file upload functionality."""
    # Create a temporary PDF file
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("Dummy PDF content")

    with open(pdf_path, 'rb') as pdf_file:
        response = client.post('/upload', data={'file': (pdf_file, 'test.pdf')})
    
    assert response.status_code == 302  # Redirect to results
    # Database save is disabled in the app, so no data should be saved
    assert OCRResult.query.count() == 0

def test_results_page(client):
    """Test the results page."""
    # Add a mock OCR result to the database
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/results')
    assert response.status_code == 200
    assert b"Sample OCR text" in response.data  # Ensure the result is displayed

def test_download_csv(client):
    """Test the CSV download functionality."""
    # Add a mock OCR result to the database
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/download_csv')
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == 'attachment;filename=ocr_results.csv'
    assert b"Sample OCR text" in response.data  # Ensure the CSV contains the correct dataimport os
import pytest
from flask import url_for
from app import app, db, OCRResult

# ファイル: test_app.py

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # テスト用にインメモリSQLiteを使用
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_home_page(client):
    """ホームページのテスト"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"index.html" in response.data  # テンプレートが正しくレンダリングされていることを確認

def test_upload_file(client, tmp_path):
    """ファイルアップロードのテスト"""
    # ダミーのPDFファイルを作成
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("Dummy PDF content")

    with open(pdf_path, 'rb') as pdf_file:
        response = client.post('/upload', data={'file': (pdf_file, 'test.pdf')})
    
    assert response.status_code == 302  # リダイレクトが発生することを確認
    # データベース保存が無効化されているため、データベースに保存されないことを確認
    assert OCRResult.query.count() == 0

def test_results_page(client):
    """結果表示ページのテスト"""
    # モックデータをデータベースに追加
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/results')
    assert response.status_code == 200
    assert b"Sample OCR text" in response.data  # 結果が正しく表示されていることを確認

def test_download_csv(client):
    """CSVダウンロードのテスト"""
    # モックデータをデータベースに追加
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/download_csv')
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == 'attachment;filename=ocr_results.csv'
    assert b"Sample OCR text" in response.data  # CSVデータに正しい内容が含まれていることを確認import os
import pytest
from flask import url_for
from app import app, db, OCRResult

# File: test_app.py

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in-memory SQLite for testing
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()

def test_home_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"index.html" in response.data  # Ensure the template is rendered

def test_upload_file(client, tmp_path):
    # Create a temporary PDF file
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("Dummy PDF content")

    with open(pdf_path, 'rb') as pdf_file:
        response = client.post('/upload', data={'file': (pdf_file, 'test.pdf')})
    
    assert response.status_code == 302  # Redirect to results
    assert OCRResult.query.count() == 0  # Database save is disabled in the app

def test_results_page(client):
    # Add a mock OCR result to the database
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/results')
    assert response.status_code == 200
    assert b"Sample OCR text" in response.data

def test_download_csv(client):
    # Add a mock OCR result to the database
    with app.app_context():
        result = OCRResult(filename="test.pdf", text="Sample OCR text")
        db.session.add(result)
        db.session.commit()

    response = client.get('/download_csv')
    assert response.status_code == 200
    assert response.headers['Content-Disposition'] == 'attachment;filename=ocr_results.csv'
    assert b"Sample OCR text" in response.data