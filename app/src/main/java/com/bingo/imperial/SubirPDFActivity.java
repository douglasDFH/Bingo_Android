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
    private TextView tvNombreArchivo, tvTamano, tvResultNombre, tvResultTotal, tvResultNuevos, tvResultErrores;
    private Button btnSubir;
    private final Handler handler = new Handler(Looper.getMainLooper());

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
        resultCard.setVisibility(View.GONE);

        new Thread(() -> {
            try {
                InputStream is = getContentResolver().openInputStream(pdfUri);
                File temp = File.createTempFile("upload", ".pdf", getCacheDir());
                FileOutputStream fos = new FileOutputStream(temp);
                byte[] buf = new byte[4096];
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
                                progressCard.setVisibility(View.GONE);
                                resultCard.setVisibility(View.VISIBLE);
                                btnSubirWrap.setVisibility(View.GONE);
                                btnSubir.setEnabled(true);
                                tvResultNombre.setText(j.optString("nombre", ""));
                                tvResultTotal.setText(String.valueOf(j.optInt("total")));
                                tvResultNuevos.setText(String.valueOf(j.optInt("cartones_creados")));
                                tvResultErrores.setText(String.valueOf(j.optInt("errores")));
                            } catch (Exception ignored) {}
                        });
                    }
                    @Override
                    public void onError(String error) {
                        handler.post(() -> {
                            progressCard.setVisibility(View.GONE);
                            btnSubir.setEnabled(true);
                            Toast.makeText(SubirPDFActivity.this, "Error: " + error, Toast.LENGTH_LONG).show();
                        });
                    }
                });
            } catch (Exception e) {
                handler.post(() -> {
                    progressCard.setVisibility(View.GONE);
                    btnSubir.setEnabled(true);
                    Toast.makeText(SubirPDFActivity.this, "Error: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    @Override public boolean onSupportNavigateUp() { finish(); return true; }
}
