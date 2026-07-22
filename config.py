import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'btmob-secret-key-change-me'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///btmob.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER_APPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'apps')
    UPLOAD_FOLDER_ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'icons')
    UPLOAD_FOLDER_BUILT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'built')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024
    PANEL_DOMAIN = os.environ.get('PANEL_DOMAIN') or 'http://localhost:5000'