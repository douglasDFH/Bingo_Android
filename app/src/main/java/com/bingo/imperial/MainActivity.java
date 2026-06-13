package com.bingo.imperial;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import org.json.JSONObject;

public class MainActivity extends AppCompatActivity {

    private SwipeRefreshLayout swipeRefresh;
    private View errorCard, statsContainer;
    private TextView tvTotalCartones, tvDisponibles, tvVendidos, tvReservados, tvPdfs, tvIngresos;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        SessionManager session = new SessionManager(this);
        if (!session.isLoggedIn()) {
            startActivity(new Intent(this, LoginActivity.class));
            finish();
            return;
        }
        ApiClient.setToken(session.getToken());
        boolean esAdmin = session.isAdmin();

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        String username   = session.getUsername();
        String rolDisplay = esAdmin ? "Administrador" : "Vendedor";
        getSupportActionBar().setTitle("Bienvenido, " + username);
        getSupportActionBar().setSubtitle(rolDisplay);

        swipeRefresh    = findViewById(R.id.swipeRefresh);
        errorCard       = findViewById(R.id.errorCard);
        statsContainer  = findViewById(R.id.statsContainer);
        tvTotalCartones = findViewById(R.id.tvTotalCartones);
        tvDisponibles   = findViewById(R.id.tvDisponibles);
        tvVendidos      = findViewById(R.id.tvVendidos);
        tvReservados    = findViewById(R.id.tvReservados);
        tvPdfs          = findViewById(R.id.tvPdfs);
        tvIngresos      = findViewById(R.id.tvIngresos);

        swipeRefresh.setColorSchemeColors(0xFF6C63FF);
        swipeRefresh.setOnRefreshListener(this::cargarDatos);

        findViewById(R.id.btnSubirPDF).setOnClickListener(v ->
                startActivity(new Intent(this, SubirPDFActivity.class)));
        findViewById(R.id.btnVerCartones).setOnClickListener(v ->
                startActivity(new Intent(this, CartonesActivity.class)));
        findViewById(R.id.btnVerPDFs).setOnClickListener(v ->
                startActivity(new Intent(this, PDFsActivity.class)));
        findViewById(R.id.btnBuscar).setOnClickListener(v ->
                startActivity(new Intent(this, CartonesActivity.class)));
        findViewById(R.id.btnDisponibles).setOnClickListener(v -> {
            Intent i = new Intent(this, CartonesActivity.class);
            i.putExtra("estado", "disponible");
            startActivity(i);
        });
        findViewById(R.id.btnVendidos).setOnClickListener(v -> {
            Intent i = new Intent(this, CartonesActivity.class);
            i.putExtra("estado", "vendido");
            startActivity(i);
        });

        android.widget.Button btnUsuarios          = findViewById(R.id.btnUsuarios);
        android.widget.Button btnGrupos            = findViewById(R.id.btnGrupos);
        android.widget.Button btnBanners           = findViewById(R.id.btnBanners);
        android.widget.Button btnMigrarNumeros      = findViewById(R.id.btnMigrarNumeros);
        android.widget.Button btnRegenerarImagenes  = findViewById(R.id.btnRegenerarImagenes);
        if (esAdmin) {
            btnUsuarios.setVisibility(android.view.View.VISIBLE);
            btnUsuarios.setOnClickListener(v ->
                    startActivity(new Intent(this, UsuariosActivity.class)));

            btnGrupos.setVisibility(android.view.View.VISIBLE);
            btnGrupos.setOnClickListener(v ->
                    startActivity(new Intent(this, GruposActivity.class)));

            btnBanners.setVisibility(android.view.View.VISIBLE);
            btnBanners.setOnClickListener(v ->
                    startActivity(new Intent(this, BannersActivity.class)));

            btnMigrarNumeros.setVisibility(android.view.View.VISIBLE);
            btnMigrarNumeros.setOnClickListener(v -> confirmarMigracion());

            btnRegenerarImagenes.setVisibility(android.view.View.VISIBLE);
            btnRegenerarImagenes.setOnClickListener(v -> confirmarRegenerarImagenes());
        }

        cargarDatos();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "Cerrar sesión").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            new AlertDialog.Builder(this)
                    .setTitle("Cerrar sesión")
                    .setMessage("¿Deseas cerrar sesión?")
                    .setPositiveButton("Sí", (d, w) -> {
                        new SessionManager(this).cerrarSesion();
                        ApiClient.setToken(null);
                        startActivity(new Intent(this, LoginActivity.class));
                        finish();
                    })
                    .setNegativeButton("Cancelar", null)
                    .show();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    protected void onResume() {
        super.onResume();
        cargarDatos();
    }

    private void cargarDatos() {
        swipeRefresh.setRefreshing(true);
        errorCard.setVisibility(View.GONE);

        ApiClient.get("/dashboard", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONObject j = new JSONObject(body);
                        tvTotalCartones.setText(String.valueOf(j.getInt("total_cartones")));
                        tvDisponibles.setText(String.valueOf(j.getInt("disponibles")));
                        tvVendidos.setText(String.valueOf(j.getInt("vendidos")));
                        tvReservados.setText(String.valueOf(j.getInt("reservados")));
                        tvPdfs.setText(String.valueOf(j.getInt("total_pdfs")));
                        tvIngresos.setText(String.format("$%.2f", j.getDouble("ingresos")));
                        statsContainer.setVisibility(View.VISIBLE);
                    } catch (Exception e) {
                        mostrarError();
                    }
                    swipeRefresh.setRefreshing(false);
                });
            }

            @Override
            public void onError(String error) {
                handler.post(() -> {
                    mostrarError();
                    swipeRefresh.setRefreshing(false);
                });
            }
        });
    }

    private void mostrarError() {
        errorCard.setVisibility(View.VISIBLE);
        statsContainer.setVisibility(View.GONE);
    }

    private void confirmarRegenerarImagenes() {
        new AlertDialog.Builder(this)
                .setTitle("Regenerar imágenes")
                .setMessage("Esto reemplaza la imagen de TODOS los cartones existentes usando el nuevo template con el número en el círculo.\n\n¿Continuar?")
                .setPositiveButton("Sí, regenerar", (d, w) -> ejecutarRegenerarImagenes())
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void ejecutarRegenerarImagenes() {
        android.widget.Button btn = findViewById(R.id.btnRegenerarImagenes);
        btn.setEnabled(false);
        btn.setText("Iniciando...");

        ApiClient.post("/admin/regenerar-imagenes", "{}", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        org.json.JSONObject j = new org.json.JSONObject(body);
                        int total   = j.optInt("total", 0);
                        String msg  = j.optString("mensaje", "Regeneración iniciada.");
                        new AlertDialog.Builder(MainActivity.this)
                                .setTitle("✅ Proceso iniciado")
                                .setMessage(msg + "\n\nEn unos minutos abre un cartón para ver el nuevo diseño con el template.")
                                .setPositiveButton("OK", null)
                                .show();
                    } catch (Exception e) {
                        Toast.makeText(MainActivity.this,
                                "Regeneración iniciada en segundo plano", Toast.LENGTH_LONG).show();
                    }
                    btn.setEnabled(true);
                    btn.setText("🖼 Regenerar imágenes con template");
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> {
                    new AlertDialog.Builder(MainActivity.this)
                            .setTitle("Error")
                            .setMessage("No se pudo iniciar: " + error)
                            .setPositiveButton("OK", null)
                            .show();
                    btn.setEnabled(true);
                    btn.setText("🖼 Regenerar imágenes con template");
                });
            }
        });
    }

    private void confirmarMigracion() {
        new AlertDialog.Builder(this)
                .setTitle("Migrar números a 5 dígitos")
                .setMessage("Esto convertirá todos los números de cartones existentes al formato de 5 dígitos.\n\nEjemplo: 100001 → 00001\n\n¿Continuar?")
                .setPositiveButton("Sí, migrar", (d, w) -> ejecutarMigracion())
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void ejecutarMigracion() {
        android.widget.Button btn = findViewById(R.id.btnMigrarNumeros);
        btn.setEnabled(false);
        btn.setText("Migrando...");

        ApiClient.post("/admin/migrar-numeros", "{}", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        org.json.JSONObject j = new org.json.JSONObject(body);
                        int actualizados = j.optInt("actualizados", 0);
                        int sinCambio    = j.optInt("sin_cambio", 0);
                        int colisiones   = j.optInt("colisiones", 0);
                        int total        = j.optInt("total", 0);

                        new AlertDialog.Builder(MainActivity.this)
                                .setTitle("Migración completada ✅")
                                .setMessage(
                                        "Total cartones: " + total + "\n" +
                                        "Actualizados:   " + actualizados + "\n" +
                                        "Ya estaban OK:  " + sinCambio + "\n" +
                                        (colisiones > 0 ? "Con conflicto: " + colisiones : "")
                                )
                                .setPositiveButton("OK", null)
                                .show();
                    } catch (Exception e) {
                        Toast.makeText(MainActivity.this, "Migración completada", Toast.LENGTH_SHORT).show();
                    }
                    btn.setEnabled(true);
                    btn.setText("🔢 Migrar cartones a 5 dígitos");
                });
            }

            @Override
            public void onError(String error) {
                handler.post(() -> {
                    new AlertDialog.Builder(MainActivity.this)
                            .setTitle("Error")
                            .setMessage("No se pudo migrar: " + error)
                            .setPositiveButton("OK", null)
                            .show();
                    btn.setEnabled(true);
                    btn.setText("🔢 Migrar cartones a 5 dígitos");
                });
            }
        });
    }
}
