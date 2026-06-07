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

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

public class SubirPDFActivity extends AppCompatActivity {

    private static final int CHUNK_SIZE = 2 * 1024 * 1024; // 2 MB por chunk
    private static final int MAX_REINTENTOS = 3;

    private final OkHttpClient chunkClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(2, TimeUnit.MINUTES)
            .readTimeout(2, TimeUnit.MINUTES)
            .build();

    private Uri pdfUri;
    private View cardArchivo, progressCard, resultCard, btnSubirWrap, cardAsignar;
    private TextView tvNombreArchivo, tvTamano, tvProgreso;
    private TextView tvTiempoRestante, tvCartonesProcesando, tvDeTotales;
    private TextView tvResultNombre, tvResultTotal, tvResultNuevos, tvResultErrores;
    private Button btnSubir, btnVerCartonesEnVivo;
    private Spinner spUsuario;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int pdfId = -1;
    private int targetUserId = 0;
    private Runnable pollingRunnable;
    private boolean cancelado = false;

    // Tiempo real
    private long uploadStartTime = 0;
    private long processingStartTime = 0;
    private int totalChunksGlobal = 0;

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

        cardArchivo          = findViewById(R.id.cardArchivo);
        progressCard         = findViewById(R.id.progressCard);
        resultCard           = findViewById(R.id.resultCard);
        btnSubirWrap         = findViewById(R.id.btnSubirWrap);
        cardAsignar          = findViewById(R.id.cardAsignar);
        tvNombreArchivo      = findViewById(R.id.tvNombreArchivo);
        tvTamano             = findViewById(R.id.tvTamano);
        tvProgreso           = findViewById(R.id.tvProgreso);
        tvTiempoRestante     = findViewById(R.id.tvTiempoRestante);
        tvCartonesProcesando = findViewById(R.id.tvCartonesProcesando);
        tvDeTotales          = findViewById(R.id.tvDeTotales);
        tvResultNombre       = findViewById(R.id.tvResultNombre);
        tvResultTotal        = findViewById(R.id.tvResultTotal);
        tvResultNuevos       = findViewById(R.id.tvResultNuevos);
        tvResultErrores      = findViewById(R.id.tvResultErrores);
        btnSubir             = findViewById(R.id.btnSubir);
        btnVerCartonesEnVivo = findViewById(R.id.btnVerCartonesEnVivo);
        spUsuario            = findViewById(R.id.spUsuario);

        cardArchivo.setOnClickListener(v -> picker.launch(new String[]{"application/pdf"}));
        btnSubir.setOnClickListener(v -> iniciarSubida());
        btnVerCartonesEnVivo.setOnClickListener(v ->
                startActivity(new Intent(this, CartonesActivity.class)));
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
            @Override public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        usuarioNombres.clear(); usuarioIds.clear();
                        usuarioNombres.add("Sin asignar (Admin)"); usuarioIds.add(0);
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject u = arr.getJSONObject(i);
                            usuarioNombres.add(u.getString("username") + " (" + u.getString("rol") + ")");
                            usuarioIds.add(u.getInt("id"));
                        }
                        ArrayAdapter<String> adapter = new ArrayAdapter<>(SubirPDFActivity.this,
                                android.R.layout.simple_spinner_item, usuarioNombres);
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
            mostrarError("Error", "Error al leer el archivo");
        }
    }

    private void iniciarSubida() {
        if (pdfUri == null) return;
        cancelado = false;
        uploadStartTime = 0;
        processingStartTime = 0;
        btnSubir.setEnabled(false);
        progressCard.setVisibility(View.VISIBLE);
        resultCard.setVisibility(View.GONE);
        tvCartonesProcesando.setVisibility(View.GONE);
        tvDeTotales.setVisibility(View.GONE);
        tvTiempoRestante.setVisibility(View.GONE);
        btnVerCartonesEnVivo.setVisibility(View.GONE);
        tvProgreso.setText("Preparando archivo...");

        int pos = spUsuario.getSelectedItemPosition();
        targetUserId = (pos > 0 && pos < usuarioIds.size()) ? usuarioIds.get(pos) : 0;

        new Thread(this::subirEnChunks).start();
    }

    private void subirEnChunks() {
        File tempFile = null;
        try {
            actualizarMensaje("Leyendo archivo...", null);
            tempFile = copiarATemp();
            if (tempFile == null || cancelado) return;

            long totalBytes = tempFile.length();
            int totalChunks = (int) Math.ceil((double) totalBytes / CHUNK_SIZE);
            totalChunksGlobal = totalChunks;
            String uploadId = UUID.randomUUID().toString();
            String nombre = tvNombreArchivo.getText().toString();

            uploadStartTime = System.currentTimeMillis();

            java.io.FileInputStream fis = new java.io.FileInputStream(tempFile);
            byte[] buffer = new byte[CHUNK_SIZE];

            for (int i = 0; i < totalChunks; i++) {
                if (cancelado) { fis.close(); return; }

                int leidos = fis.read(buffer);
                byte[] chunkData = new byte[leidos];
                System.arraycopy(buffer, 0, chunkData, 0, leidos);

                final int chunkActual = i + 1;
                // Calcular tiempo restante de subida
                long elapsed = System.currentTimeMillis() - uploadStartTime;
                String tiempoStr = null;
                if (chunkActual > 1) {
                    long timePerChunk = elapsed / chunkActual;
                    long remaining = (totalChunks - chunkActual) * timePerChunk;
                    tiempoStr = "~" + formatTiempo(remaining) + " restantes";
                }
                actualizarMensaje(
                    String.format("Subiendo parte %d de %d...", chunkActual, totalChunks),
                    tiempoStr
                );

                boolean ok = subirChunkConReintento(uploadId, i, totalChunks, nombre, chunkData);
                if (!ok) {
                    fis.close();
                    mostrarError("Error de red", "Error al subir parte " + chunkActual + ". Revisa tu conexión.");
                    return;
                }
            }
            fis.close();

            actualizarMensaje("Ensamblando PDF en servidor...", null);
            finalizarUpload(uploadId);

        } catch (Exception e) {
            mostrarError("Error", e.getMessage());
        } finally {
            if (tempFile != null) tempFile.delete();
        }
    }

    private File copiarATemp() {
        try {
            InputStream is = getContentResolver().openInputStream(pdfUri);
            File temp = File.createTempFile("upload", ".pdf", getCacheDir());
            FileOutputStream fos = new FileOutputStream(temp);
            byte[] buf = new byte[8192]; int len;
            while ((len = is.read(buf)) != -1) fos.write(buf, 0, len);
            fos.close(); is.close();
            return temp;
        } catch (IOException e) {
            mostrarError("Error", "Error al leer el archivo");
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
                        .url(Config.BASE_URL + "/pdf-parte")
                        .header("Authorization", "Bearer " + ApiClient.getToken())
                        .post(body).build();
                try (Response response = chunkClient.newCall(request).execute()) {
                    String respBody = response.body() != null ? response.body().string() : "";
                    if (response.isSuccessful() && !respBody.startsWith("<")) return true;
                }
            } catch (IOException e) {
                if (intento == MAX_REINTENTOS) return false;
                try { Thread.sleep(2000L * intento); } catch (InterruptedException ignored) {}
            }
        }
        return false;
    }

    private void finalizarUpload(String uploadId) {
        new Thread(() -> {
            try {
                JSONObject bodyJson = new JSONObject();
                bodyJson.put("upload_id", uploadId);
                if (targetUserId > 0) bodyJson.put("usuario_id", targetUserId);

                OkHttpClient finalizeClient = new OkHttpClient.Builder()
                        .connectTimeout(30, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(60, TimeUnit.SECONDS)
                        .build();

                okhttp3.RequestBody rb = okhttp3.RequestBody.create(
                        bodyJson.toString(),
                        okhttp3.MediaType.get("application/json; charset=utf-8"));
                Request req = new Request.Builder()
                        .url(Config.BASE_URL + "/pdf-completar")
                        .header("Authorization", "Bearer " + ApiClient.getToken())
                        .post(rb).build();

                try (Response response = finalizeClient.newCall(req).execute()) {
                    String respBody = response.body() != null ? response.body().string() : "(vacío)";
                    if (!response.isSuccessful()) {
                        mostrarError("Error HTTP " + response.code(), respBody);
                        return;
                    }
                    if (respBody.startsWith("<")) {
                        mostrarError("Error de proxy", "El servidor devolvió HTML en vez de JSON.\n" + respBody.substring(0, Math.min(300, respBody.length())));
                        return;
                    }
                    JSONObject j = new JSONObject(respBody);
                    pdfId = j.getInt("pdf_id");
                    processingStartTime = System.currentTimeMillis();
                    handler.post(() -> {
                        tvProgreso.setText("⚙ Procesando páginas...");
                        tvCartonesProcesando.setVisibility(View.VISIBLE);
                        tvDeTotales.setVisibility(View.VISIBLE);
                        tvTiempoRestante.setVisibility(View.VISIBLE);
                        btnVerCartonesEnVivo.setVisibility(View.VISIBLE);
                        tvCartonesProcesando.setText("0 cartones creados");
                        tvDeTotales.setText("calculando...");
                        tvTiempoRestante.setText("Calculando tiempo restante...");
                        iniciarPolling();
                    });
                }
            } catch (Exception e) {
                mostrarError("Error al finalizar", e.getClass().getSimpleName() + ": " + e.getMessage());
            }
        }).start();
    }

    private void iniciarPolling() {
        pollingRunnable = new Runnable() {
            @Override public void run() {
                if (pdfId < 0 || cancelado) return;
                ApiClient.get("/pdfs/" + pdfId + "/estado", new ApiClient.Callback() {
                    @Override public void onSuccess(String body) {
                        handler.post(() -> {
                            try {
                                JSONObject j = new JSONObject(body);
                                String estado = j.optString("estado", "");
                                int cartonesCreados = j.optInt("cartones_creados", 0);
                                int totalPaginas = j.optInt("total_paginas", 0);
                                int errores = j.optInt("errores", 0);

                                // Actualizar conteo en tiempo real
                                tvCartonesProcesando.setText(cartonesCreados + " cartones creados"
                                        + (errores > 0 ? " (" + errores + " errores)" : ""));
                                if (totalPaginas > 0) {
                                    tvDeTotales.setText("de " + totalPaginas + " páginas");
                                }

                                // Estimar tiempo restante
                                if (cartonesCreados > 0 && totalPaginas > 0 && processingStartTime > 0) {
                                    long elapsed = System.currentTimeMillis() - processingStartTime;
                                    long msPorCarton = elapsed / cartonesCreados;
                                    long restantes = totalPaginas - cartonesCreados;
                                    long msRestantes = restantes * msPorCarton;
                                    if (restantes > 0) {
                                        tvTiempoRestante.setText("~" + formatTiempo(msRestantes) + " restantes");
                                    } else {
                                        tvTiempoRestante.setText("Finalizando...");
                                    }
                                }

                                switch (estado) {
                                    case "procesando":
                                        tvProgreso.setText("⚙ Procesando páginas...");
                                        handler.postDelayed(pollingRunnable, 2000);
                                        break;
                                    case "completado":
                                    case "completado_con_errores":
                                        mostrarResultado(j);
                                        break;
                                    case "error":
                                        mostrarError("Error del servidor",
                                                j.optString("mensaje_error", "Error al procesar el PDF"));
                                        break;
                                    default:
                                        handler.postDelayed(pollingRunnable, 2000);
                                }
                            } catch (Exception e) {
                                handler.postDelayed(pollingRunnable, 3000);
                            }
                        });
                    }
                    @Override public void onError(String error) {
                        handler.postDelayed(pollingRunnable, 4000);
                    }
                });
            }
        };
        handler.postDelayed(pollingRunnable, 2000);
    }

    private String formatTiempo(long ms) {
        if (ms <= 0) return "0s";
        long secs = ms / 1000;
        if (secs < 60) return secs + "s";
        return (secs / 60) + "m " + (secs % 60) + "s";
    }

    private void actualizarMensaje(String mensaje, String tiempo) {
        handler.post(() -> {
            progressCard.setVisibility(View.VISIBLE);
            tvProgreso.setText(mensaje);
            if (tiempo != null) {
                tvTiempoRestante.setVisibility(View.VISIBLE);
                tvTiempoRestante.setText(tiempo);
            } else {
                tvTiempoRestante.setVisibility(View.GONE);
            }
        });
    }

    private void mostrarResultado(JSONObject j) {
        handler.post(() -> {
            try {
                if (pollingRunnable != null) handler.removeCallbacks(pollingRunnable);
                progressCard.setVisibility(View.GONE);
                resultCard.setVisibility(View.VISIBLE);
                btnSubirWrap.setVisibility(View.GONE);
                btnSubir.setEnabled(true);
                tvResultNombre.setText(j.optString("nombre_archivo", ""));
                tvResultTotal.setText(String.valueOf(j.optInt("total_paginas")));
                tvResultNuevos.setText(String.valueOf(j.optInt("cartones_creados")));
                tvResultErrores.setText(String.valueOf(j.optInt("errores")));
            } catch (Exception ignored) {}
        });
    }

    private void mostrarError(String titulo, String msg) {
        handler.post(() -> {
            if (pollingRunnable != null) handler.removeCallbacks(pollingRunnable);
            progressCard.setVisibility(View.GONE);
            btnSubir.setEnabled(true);
            new androidx.appcompat.app.AlertDialog.Builder(this)
                    .setTitle(titulo)
                    .setMessage(msg)
                    .setPositiveButton("OK", null)
                    .show();
        });
    }

    @Override protected void onDestroy() {
        super.onDestroy();
        cancelado = true;
        if (pollingRunnable != null) handler.removeCallbacks(pollingRunnable);
    }

    @Override public boolean onSupportNavigateUp() { finish(); return true; }
}
