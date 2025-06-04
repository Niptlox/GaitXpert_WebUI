from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, doctor, patient
    is_active = db.Column(db.Boolean, default=True)
    invites = db.relationship('Invite', backref='creator', lazy=True, foreign_keys='Invite.created_by')
    videos = db.relationship('Video', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # doctor, patient
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    used_at = db.Column(db.DateTime)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    processing_id = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    result = db.Column(db.String(256))
    progress = db.Column(db.Float, default=0.0)
    is_finish = db.Column(db.Boolean, default=False)
    comments = db.relationship('Comment', backref='video', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('User', foreign_keys=[doctor_id])
