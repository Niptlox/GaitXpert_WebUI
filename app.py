from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, abort
"""
Flask web application for managing users, video uploads, and processing with role-based access control.
Routes:
    /login (GET, POST): User login page.
    /register (GET, POST): User registration page with invite code validation.
    /logout: Logs out the current user.
    /: Redirects user to their role-specific panel (admin, doctor, patient).
    /admin (GET, POST): Admin panel for managing users and invites.
    /doctor (GET, POST): Doctor panel for searching patients and commenting on videos.
    /doctor/comments/<int:video_id>: View comments for a specific video (doctor only).
    /patient (GET, POST): Patient panel for uploading videos, viewing processing status, and filtering by date.
    /patient/progress/<int:video_id>: Returns JSON with processing progress and result for a video.
    /patient/delete/<int:video_id> (POST): Deletes a patient's video.
    /instance/<path:filename>: Serves uploaded video files with access control.
    /admin/delete_user/<int:user_id> (POST): Admin deletes a user.
    /admin/delete_invite/<int:invite_id> (POST): Admin deletes an invite code.
    /admin/change_role/<int:user_id> (POST): Admin changes a user's role.
Features:
    - User authentication and registration with invite codes.
    - Role-based access: admin, doctor, patient.
    - Video upload by patients, sent to external FastAPI service for processing.
    - Doctors can view patients and comment on their videos.
    - Admins can manage users and invite codes.
    - Video processing progress and results are fetched from an external service.
    - Uploaded files are served securely based on user roles.
    - Automatic creation of database tables and test users on first request.
Dependencies:
    - Flask, Flask-Login, Flask-SQLAlchemy
    - requests, werkzeug, uuid, secrets, os, datetime
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Invite, Video, Comment
import os
from forms import LoginForm, RegisterForm
import secrets
from sqlalchemy import or_
from werkzeug.utils import secure_filename
import requests
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'AbrKadabreaasdASSDEFggs2')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверный email или пароль', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        invite = Invite.query.filter_by(code=form.invite_code.data, used_by=None).first()
        if not invite:
            flash('Неверный или использованный код приглашения', 'error')
            return render_template('register.html', form=form)
        if User.query.filter_by(email=form.email.data).first():
            flash('Пользователь с таким email уже существует', 'error')
            return render_template('register.html', form=form)
        user = User(email=form.email.data, role=invite.role)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        invite.used_by = user.id
        invite.used_at = db.func.now()
        db.session.commit()
        flash('Регистрация успешна! Войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    if current_user.role == 'admin':
        return redirect(url_for('admin_panel'))
    elif current_user.role == 'doctor':
        return redirect(url_for('doctor_panel'))
    elif current_user.role == 'patient':
        return redirect(url_for('patient_panel'))
    else:
        flash('Неизвестная роль пользователя', 'error')
        return redirect(url_for('logout'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        role = request.form.get('role')
        if role in ['doctor', 'patient']:
            code = secrets.token_urlsafe(8)
            invite = Invite(code=code, role=role, created_by=current_user.id)
            db.session.add(invite)
            db.session.commit()
            flash(f'Приглашение для {role} создано: {code}', 'success')
        else:
            flash('Некорректная роль', 'error')
    users = User.query.all()
    invites = Invite.query.order_by(Invite.id.desc()).all()
    return render_template('admin.html', users=users, invites=invites)

@app.route('/doctor', methods=['GET', 'POST'])
@login_required
def doctor_panel():
    if current_user.role != 'doctor':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    search = request.args.get('search', '').strip()
    if request.method == 'POST':
        video_id = request.form.get('video_id')
        comment_text = request.form.get('comment')
        video = Video.query.get(video_id)
        if video and comment_text:
            comment = Comment(video_id=video.id, doctor_id=current_user.id, text=comment_text)
            db.session.add(comment)
            db.session.commit()
            # flash('Комментарий добавлен', 'success')
        else:
            flash('Ошибка при добавлении комментария', 'error')
    if search:
        patients = User.query.filter(User.role=='patient', User.email.ilike(f'%{search}%')).all()
    else:
        patients = User.query.filter_by(role='patient').all()
    return render_template('doctor.html', patients=patients, search=search)

@app.route('/doctor/comments/<int:video_id>')
@login_required
def video_comments(video_id):
    if current_user.role != 'doctor':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    video = Video.query.get_or_404(video_id)
    comments = Comment.query.filter_by(video_id=video.id).order_by(Comment.created_at.desc()).all()
    return render_template('video_comments.html', video=video, comments=comments)

@app.route('/patient', methods=['GET', 'POST'])
@login_required
def patient_panel():
    if current_user.role != 'patient':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        file = request.files.get('video')
        if file:
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            filename = f"{uuid.uuid4()}.{ext}" if ext else str(uuid.uuid4())
            filepath = os.path.join('instance', filename)
            file.save(filepath)
            # Отправка видео на FastAPI сервис
            with open(filepath, 'rb') as f:
                try:
                    resp = requests.post('http://localhost:8081/api/processing/start', files={'file': f})
                    resp.raise_for_status()
                    processing_id = resp.json().get('processing_id')
                except Exception as e:
                    flash('Ошибка отправки видео на обработку', 'error')
                    return redirect(url_for('patient_panel'))
            from models import Video
            video = Video(user_id=current_user.id, filename=filename, processing_id=processing_id)
            db.session.add(video)
            db.session.commit()
            flash('Видео успешно загружено и отправлено на обработку', 'success')
            return redirect(url_for('patient_panel'))
    # Обновление прогресса и результата для всех видео пользователя
    from models import Video
    # Фильтрация по дате
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    query = Video.query.filter_by(user_id=current_user.id)
    if date_from:
        from datetime import datetime
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Video.uploaded_at >= dt_from)
        except Exception:
            pass
    if date_to:
        from datetime import datetime, timedelta
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Video.uploaded_at < dt_to)
        except Exception:
            pass
    videos = query.order_by(Video.uploaded_at.desc()).all()
    for video in videos:
        if not video.is_finish and video.processing_id:
            try:
                resp = requests.get(f'http://localhost:8081/api/processing/get?processing_id={video.processing_id}')
                if resp.status_code == 200:
                    data = resp.json()
                    video.progress = data.get('progress', 0)
                    video.is_finish = data.get('is_finish', False)
                    video.result = data.get('result', '')
                    db.session.commit()
            except Exception:
                pass
    return render_template('patient.html', videos=videos, date_from=date_from, date_to=date_to)

@app.route('/patient/progress/<int:video_id>')
@login_required
def patient_video_progress(video_id):
    from models import Video
    video = Video.query.get_or_404(video_id)
    if video.user_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    import requests
    if not video.is_finish and video.processing_id:
        try:
            resp = requests.get(f'http://localhost:8081/api/processing/get?processing_id={video.processing_id}')
            if resp.status_code == 200:
                data = resp.json()
                video.progress = data.get('progress', 0)
                video.is_finish = data.get('is_finish', False)
                video.result = data.get('result', '')
                db.session.commit()
        except Exception:
            pass
    return jsonify({
        'progress': video.progress,
        'is_finish': video.is_finish,
        'result': video.result or ''
    })

@app.route('/patient/delete/<int:video_id>', methods=['POST'])
@login_required
def delete_video(video_id):
    from models import Video
    video = Video.query.get_or_404(video_id)
    if video.user_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('patient_panel'))
    db.session.delete(video)
    db.session.commit()
    flash('Видео удалено', 'success')
    return redirect(url_for('patient_panel'))

@app.route('/instance/<path:filename>')
@login_required
def uploaded_file(filename):
    from models import Video, User
    video = Video.query.filter_by(filename=filename).first()
    if not video:
        abort(404)
    # Доступ разрешён владельцу, админу и врачу (если врач есть в системе)
    if current_user.role == 'admin' or video.user_id == current_user.id:
        return send_from_directory('instance', filename)
    # Врач может видеть видео любого пациента
    if current_user.role == 'doctor':
        return send_from_directory('instance', filename)
    abort(403)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('admin_panel'))
    from models import User
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя', 'error')
        return redirect(url_for('admin_panel'))
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_invite/<int:invite_id>', methods=['POST'])
@login_required
def admin_delete_invite(invite_id):
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('admin_panel'))
    from models import Invite
    invite = Invite.query.get_or_404(invite_id)
    db.session.delete(invite)
    db.session.commit()
    flash('Приглашение удалено', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
@login_required
def admin_change_role(user_id):
    if current_user.role != 'admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('admin_panel'))
    from models import User
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Нельзя менять свою роль', 'error')
        return redirect(url_for('admin_panel'))
    new_role = request.form.get('role')
    if new_role in ['admin', 'doctor', 'patient']:
        user.role = new_role
        db.session.commit()
        flash('Роль пользователя изменена', 'success')
    else:
        flash('Некорректная роль', 'error')
    return redirect(url_for('admin_panel'))


_tables_created = False
@app.before_request
def create_tables_once():
    global _tables_created
    if not _tables_created:
        db.create_all()
        # Добавление тестового администратора, если его нет
        if not User.query.filter_by(email='admin@example.com').first():
            admin = User(email='admin@example.com', role='admin', is_active=True)
            admin.set_password('pass')
            db.session.add(admin)

            doctor = User(email='doctor@example.com', role='doctor', is_active=True)
            doctor.set_password('pass')
            db.session.add(doctor) 

            patient = User(email='patient@example.com', role='patient', is_active=True)
            patient.set_password('pass')
            db.session.add(patient) 

            db.session.commit()
        _tables_created = True


if __name__ == '__main__':
    app.run(debug=True)
