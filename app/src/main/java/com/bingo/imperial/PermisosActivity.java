package com.bingo.imperial;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SwitchCompat;
import androidx.appcompat.widget.Toolbar;

import org.json.JSONObject;

public class PermisosActivity extends AppCompatActivity {

    private SwitchCompat switchSubirPdf, switchVender, switchReservar, switchLiberar;
    private TextView tvEstado;
    private boolean cargando = false;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_permisos);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Roles y Permisos");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        switchSubirPdf = findViewById(R.id.switchSubirPdf);
        switchVender   = findViewById(R.id.switchVender);
        switchReservar = findViewById(R.id.switchReservar);
        switchLiberar  = findViewById(R.id.switchLiberar);
        tvEstado       = findViewById(R.id.tvEstado);

        cargarPermisos();
    }

    private void cargarPermisos() {
        ApiClient.get("/permisos", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONObject json = new JSONObject(body);
                        JSONObject permisos = json.getJSONObject("permisos");

                        // Cargar sin disparar los listeners
                        cargando = true;
                        switchSubirPdf.setChecked(permisos.optBoolean("subir_pdf", false));
                        switchVender.setChecked(permisos.optBoolean("vender", true));
                        switchReservar.setChecked(permisos.optBoolean("reservar", true));
                        switchLiberar.setChecked(permisos.optBoolean("liberar", true));
                        cargando = false;

                        configurarListeners();
                    } catch (Exception ignored) {}
                });
            }
            @Override
            public void onError(String error) {}
        });
    }

    private void configurarListeners() {
        switchSubirPdf.setOnCheckedChangeListener((btn, checked) -> guardar("subir_pdf", checked));
        switchVender.setOnCheckedChangeListener((btn, checked) -> guardar("vender", checked));
        switchReservar.setOnCheckedChangeListener((btn, checked) -> guardar("reservar", checked));
        switchLiberar.setOnCheckedChangeListener((btn, checked) -> guardar("liberar", checked));
    }

    private void guardar(String permiso, boolean habilitado) {
        if (cargando) return;
        try {
            JSONObject body = new JSONObject();
            body.put("habilitado", habilitado);
            ApiClient.put("/permisos/" + permiso, body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String response) {
                    handler.post(() -> mostrarEstado(habilitado
                            ? "✅ Permiso activado"
                            : "🚫 Permiso desactivado"));
                }
                @Override
                public void onError(String error) {
                    handler.post(() -> mostrarEstado("❌ Error al guardar"));
                }
            });
        } catch (Exception ignored) {}
    }

    private void mostrarEstado(String msg) {
        tvEstado.setText(msg);
        tvEstado.setVisibility(View.VISIBLE);
        handler.postDelayed(() -> tvEstado.setVisibility(View.GONE), 2000);
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
