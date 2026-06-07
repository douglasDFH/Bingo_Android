package com.bingo.imperial;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class SubirPDFActivity extends AppCompatActivity {

    private static final int CHUNK_SIZE = 1 * 1024 * 1024; // 1 MB por chunk (evita límites del proxy)
    private static final int MAX_REINTENTOS = 3;

    private final OkHttpClient chunkClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(2, TimeUnit.MINUTES)
            .readTimeout(2, TimeUnit.MINUTES)
            .build();

    private Uri pdfUri;
    private View cardArchivo, progressCard, resultCard, btnSubirWrap, cardAsignar;
    private TextView tvNombreArchivo, tvTamano, tvProgreso;
    private TextView tvResultNombre, tvResultTotal, tvResultNuevos, tvResultErrores;
    private Button btnSubir;
    private Spinner spUsuario;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int pdfId = -1;
    private int targetUserId = 0; // Capturado desde el spinner antes del upload
    private Runnable pollingRunnable;
    private boolean cancelado = false;

    private final ArrayList<String> usuarioNombres = new ArrayList<>();
    private final ArrayList<Integer> usuarioIds = new ArrayList<>();

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
        cardAsignar      = findViewById(R.id.cardAsignar);
        tvNombreArchivo  = findViewById(R.id.tvNombreArchivo);
        tvTamano         = findViewById(R.id.tvTamano);
        tvProgreso       = findViewById(R.id.tvProgreso);
        tvResultNombre   = findViewById(R.id.tvResultNombre);
        tvResultTotal    = findViewById(R.id.tvResultTotal);
        tvResultNuevos   = findViewById(R.id.tvResultNuevos);
        tvResultErrores  = findViewById(R.id.tvResultErrores);
        btnSubir         = findViewById(R.id.btnSubir);
        spUsuario        = findViewById(R.id.spUsuario);

        cardArchivo.setOnClickListener(v -> picker.launch(new String[]{"application/pdf"}));
        btnSubir.setOnClickListener(v -> iniciarSubida());
        findViewById(R.id.btnVerCartones).setOnClickListener(v ->
                startActivity(new Intent(this, CartonesActivity.class)));

        SessionManager session = new SessionManager(this);
        if (session.isAdmin()) {
            cardAsignar.setVisibility(View.VISIBLE);
            cargarUsuariosParaAsignar();
        }
    }

    private void cargarUsuariosParaAsignar() {
        ApiClient.get("/usuarios", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        usuarioNombres.clear();
                        usuarioIds.clear();
                        usuarioNombres.add("Sin asignar (Admin)");
                        usuarioIds.add(0);
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject u = arr.getJSONObject(i);
                            usuarioNombres.add(u.getString("username") + " (" + u.getString("rol") + ")");
                            usuarioIds.add(u.getInt("id"));
                        }
                        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                                SubirPDFActivity.this,
                                android.R.layout.simple_spinner_item,
                                usuarioNombres);
                        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                        spUsuario.setAdapter(adapter);
                    } catch (Exception ignored) {}
                });
            }
            @Override public void onError(String error) {}
        });
    }

    private void mostrarArchivo(Uri uri) {
        try {
            android.database.Cursor cursor = getContentResolver().query(uri, null, null, null, null);
            if (cursor != null && cursor.moveToFirst()) {
                int nameIdx = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                int sizeIdx = cursor.getColumnIndex(android.provider.OpenableColumns.SIZE);
                tvNombreArchivo.setText(cursor.getString(nameIdx));
                long size = cursor.getLong(sizeIdx);
                tvTamano.setText(String.format("%.1f MB", size / 1024.0 / 1024.0));
                cursor.close();
            }
            btnSubirWrap.setVisibility(View.VISIBLE);
            resultCard.setVisibility(View.GONE);
        } catch (Exception e) {
            Toast.makeText(this, "Error al leer el archivo", Toast.LENGTH_SHORT).show();
        }
    }

    private void iniciarSubida() {
        if (pdfUri == null) return;
        cancelado = false;
        btnSubir.setEnabled(false);
        progressCard.setVisibility(View.VISIBLE);
        resultCard.setVisibility(View.GONE);
        actualizarProgreso("Preparando archivo...", 0, 0);

        // Capturar usuario seleccionado antes de entrar al hilo de fondo
        int pos = spUsuario.getSelectedItemPosition();
        targetUserId = (pos > 0 && pos < usuarioIds.size()) ? usuarioIds.get(pos) : 0;

        new Thread(this::subirEnChunks).start();
    }

    private void subirEnChunks() {
        File tempFile = null;
        try {
            // 1. Copiar a archivo temporal
            actualizarProgreso("Preparando archivo...", 0, 0);
            tempFile = copiarATemp();
            if (tempFile == null || cancelado) return;

            long totalBytes = tempFile.length();
            int totalChunks = (int) Math.ceil((double) totalBytes / CHUNK_SIZE);
            String uploadId = UUID.randomUUID().toString();
            String nombre = tvNombreArchivo.getText().toString();

            // 2. Subir cada chunk
            byte[] buffer = new byte[CHUNK_SIZE];
            java.io.FileInputStream fis = new java.io.FileInputStream(tempFile);

            for (int i = 0; i < totalChunks; i++) {
                if (cancelado) { fis.close(); return; }

                int leidos = fis.read(buffer);
                byte[] chunkData = new byte[leidos];
                System.arraycopy(buffer, 0, chunkData, 0, leidos);

                final int chunkActual = i + 1;
                actualizarProgreso(
                    String.format("Subiendo parte %d de %d...", chunkActual, totalChunks),
                    chunkActual, totalChunks
                );

                boolean ok = subirChunkConReintento(uploadId, i, totalChunks, nombre, chunkData);
                if (!ok) {
                    fis.close();
                    mostrarError("Error al subir parte " + chunkActual + ". Revisa tu conexión.");
                    return;
                }
            }
            fis.close();

            // 3. Finalizar
            actualizarProgreso("Ensamblando y procesando PDF...", totalChunks, totalChunks);
            finalizarUpload(uploadId);

        } catch (Exception e) {
            mostrarError("Error: " + e.getMessage());
        } finally {
            if (tempFile != null) tempFile.delete();
        }
    }

    private File copiarATemp() {
        try {
            InputStream is = getContentResolver().openInputStream(pdfUri);
            File temp = File.createTempFile("upload", ".pdf", getCacheDir());
            FileOutputStream fos = new FileOutputStream(temp);
            byte[] buf = new byte[8192];
            int len;
            while ((len = is.read(buf)) != -1) fos.write(buf, 0, len);
            fos.close();
            is.close();
            return temp;
        } catch (IOException e) {
            mostrarError("Error al leer el archivo");
            return null;
        }
    }

    private boolean subirChunkConReintento(String uploadId, int index, int total, String nombre, byte[] data) {
        for (int intento = 1; intento <= MAX_REINTENTOS; intento++) {
            try {
                RequestBody chunkBody = RequestBody.create(data, MediaType.get("application/octet-stream"));
                MultipartBody body = new MultipartBody.Builder()
                        .setType(MultipartBody.FORM)
                        .addFormDataPart("chunk", "chunk", chunkBody)
                        .addFormDataPart("upload_id", uploadId)
                        .addFormDataPart("chunk_index", String.valueOf(index))
                        .addFormDataPart("total_chunks", String.valueOf(total))
                        .addFormDataPart("nombre", nombre)
                        .build();

                Request request = new Request.Builder()
                        .url(Config.BASE_URL + "/upload-chunk")
                        .header("Authorization", "Bearer " + ApiClient.getToken())
                        .post(body)
                        .build();

                try (Response response = chunkClient.newCall(request).execute()) {
                    if (response.isSuccessful()) return true;
                }
            } catch (IOException e) {
                if (intento == MAX_REINTENTOS) return false;
                try { Thread.sleep(2000L * intento); } catch (InterruptedException ignored) {}
            }
        }
        return false;
    }

    private void finalizarUpload(String uploadId) {
        try {
            JSONObject body = new JSONObject();
            body.put("upload_id", uploadId);

            if (targetUserId > 0) body.put("usuario_id", targetUserId);

            ApiClient.post("/upload-finalize", body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String response) {
                    handler.post(() -> {
                        try {
                            JSONObject j = new JSONObject(response);
                            pdfId = j.getInt("pdf_id");
                            actualizarProgreso("Procesando páginas... puede tardar unos minutos.", pdfId, pdfId);
                            iniciarPolling();
                        } catch (Exception e) {
                            mostrarError("Parse error: " + e.getMessage() + "\nRespuesta: " + response.substring(0, Math.min(300, response.length())));
                        }
                    });
                }
                @Override
                public void onError(String error) {
                    mostrarError("Error al finalizar: " + error);
                }
            });
        } catch (Exception e) {
            mostrarError("Error al finalizar");
        }
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
                                        actualizarProgreso("Procesando páginas... puede tardar unos minutos.", 0, 0);
                                        handler.postDelayed(pollingRunnable, 3000);
                                        break;
                                    case "completado":
                                    case "completado_con_errores":
                                        mostrarResultado(j);
                                        break;
                                    case "error":
                                        mostrarError("Error al procesar el PDF");
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

    private void actualizarProgreso(String mensaje, int actual, int total) {
        handler.post(() -> {
            progressCard.setVisibility(View.VISIBLE);
            if (total > 0 && actual > 0)
                tvProgreso.setText(String.format("%s\n%d / %d partes", mensaje, actual, total));
            else
                tvProgreso.setText(mensaje);
        });
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
        handler.post(() -> {
            progressCard.setVisibility(View.GONE);
            btnSubir.setEnabled(true);
            Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        cancelado = true;
        if (pollingRunnable != null) handler.removeCallbacks(pollingRunnable);
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
