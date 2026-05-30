package com.bingo.imperial;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

public class SubirPDFActivity extends AppCompatActivity {

    private Uri pdfUri;
    private View cardArchivo, progressCard, resultCard, btnSubirWrap;
    private TextView tvNombreArchivo, tvTamano, tvProgreso;
    private TextView tvResultNombre, tvResultTotal, tvResultNuevos, tvResultErrores;
    private Button btnSubir;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int pdfId = -1;
    private Runnable pollingRunnable;

    private final ActivityResultLauncher<String[]> picker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) { pdfUri = uri; mostrarArchivo(uri); }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_subir_pdf);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Subir PDF");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        cardArchivo      = findViewById(R.id.cardArchivo);
        progressCard     = findViewById(R.id.progressCard);
        resultCard       = findViewById(R.id.resultCard);
        btnSubirWrap     = findViewById(R.id.btnSubirWrap);
        tvNombreArchivo  = findViewById(R.id.tvNombreArchivo);
        tvTamano         = findViewById(R.id.tvTamano);
        tvProgreso       = findViewById(R.id.tvProgreso);
        tvResultNombre   = findViewById(R.id.tvResultNombre);
        tvResultTotal    = findViewById(R.id.tvResultTotal);
        tvResultNuevos   = findViewById(R.id.tvResultNuevos);
        tvResultErrores  = findViewById(R.id.tvResultErrores);
        btnSubir         = findViewById(R.id.btnSubir);

        cardArchivo.setOnClickListener(v -> picker.launch(new String[]{"application/pdf"}));
        btnSubir.setOnClickListener(v -> subirPDF());
        findViewById(R.id.btnVerCartones).setOnClickListener(v ->
                startActivity(new Intent(this, CartonesActivity.class)));
    }

    private void mostrarArchivo(Uri uri) {
        try {
            android.database.Cursor cursor = getContentResolver().query(uri, null, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int nameIdx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                int sizeIdx = cursor.getColumnIndex(android.provider.OpenableColumns.SIZE);
                tvNombreArchivo.setText(cursor.getString(nameIdx));
                long size = cursor.getLong(sizeIdx);
                tvTamano.setText(String.format("%.2f MB", size / 1024.0 / 1024.0));
                cursor.close();
            }
            btnSubirWrap.setVisibility(View.VISIBLE);
            resultCard.setVisibility(View.GONE);
        } catch (Exception e) {
            Toast.makeText(this, "Error al leer el archivo", Toast.LENGTH_SHORT).show();
        }
    }

    private void subirPDF() {
        if (pdfUri == null) return;
        btnSubir.setEnabled(false);
        progressCard.setVisibility(View.VISIBLE);
        tvProgreso.setText("Subiendo archivo...");
        resultCard.setVisibility(View.GONE);

        new Thread(() -> {
            try {
                InputStream is = getContentResolver().openInputStream(pdfUri);
                File temp = File.createTempFile("upload", ".pdf", getCacheDir());
                FileOutputStream fos = new FileOutputStream(temp);
                byte[] buf = new byte[8192];
                int len;
                while ((len = is.read(buf)) != -1) fos.write(buf, 0, len);
                fos.close();
                is.close();

                ApiClient.uploadPdf(temp, new ApiClient.Callback() {
                    @Override
                    public void onSuccess(String body) {
                        handler.post(() -> {
                            try {
                                JSONObject j = new JSONObject(body);
                                pdfId = j.getInt("pdf_id");
                                tvProgreso.setText("Procesando páginas... esto puede tardar unos minutos.");
                                iniciarPolling();
                            } catch (Exception e) {
                                mostrarError("Error al iniciar procesamiento");
                            }
                        });
                    }
                    @Override
                    public void onError(String error) {
                        handler.post(() -> mostrarError("Error al subir: " + error));
                    }
                });
            } catch (Exception e) {
                handler.post(() -> mostrarError("Error: " + e.getMessage()));
            }
        }).start();
    }

    private void iniciarPolling() {
        pollingRunnable = new Runnable() {
            @Override
            public void run() {
                if (pdfId < 0) return;
                ApiClient.get("/pdfs/" + pdfId + "/estado", new ApiClient.Callback() {
                    @Override
                    public void onSuccess(String body) {
                        handler.post(() -> {
                            try {
                                JSONObject j = new JSONObject(body);
                                String estado = j.optString("estado", "");
                                switch (estado) {
                                    case "procesando":
                                        tvProgreso.setText("Procesando páginas... esto puede tardar unos minutos.");
                                        handler.postDelayed(pollingRunnable, 3000);
                                        break;
                                    case "completado":
                                    case "completado_con_errores":
                                        mostrarResultado(j);
                                        break;
                                    case "error":
                                        mostrarError("Error al procesar: " + j.optString("mensaje_error", ""));
                                        break;
                                    default:
                                        handler.postDelayed(pollingRunnable, 3000);
                                }
                            } catch (Exception e) {
                                handler.postDelayed(pollingRunnable, 3000);
                            }
                        });
                    }
                    @Override
                    public void onError(String error) {
                        handler.postDelayed(pollingRunnable, 5000);
                    }
                });
            }
        };
        handler.postDelayed(pollingRunnable, 3000);
    }

    private void mostrarResultado(JSONObject j) {
        try {
            progressCard.setVisibility(View.GONE);
            resultCard.setVisibility(View.VISIBLE);
            btnSubirWrap.setVisibility(View.GONE);
            btnSubir.setEnabled(true);
            tvResultNombre.setText(j.optString("nombre_archivo", ""));
            tvResultTotal.setText(String.valueOf(j.optInt("total_paginas")));
            tvResultNuevos.setText(String.valueOf(j.optInt("cartones_creados")));
            tvResultErrores.setText(String.valueOf(j.optInt("errores")));
        } catch (Exception ignored) {}
    }

    private void mostrarError(String msg) {
        progressCard.setVisibility(View.GONE);
        btnSubir.setEnabled(true);
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (pollingRunnable != null) handler.removeCallbacks(pollingRunnable);
    }

    @Override public boolean onSupportNavigateUp() { finish(); return true; }
}
