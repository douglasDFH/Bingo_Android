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
        getSupportActionBar().setTitle("Bingo Imperial");

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

        android.widget.Button btnUsuarios = findViewById(R.id.btnUsuarios);
        if (esAdmin) {
            btnUsuarios.setVisibility(android.view.View.VISIBLE);
            btnUsuarios.setOnClickListener(v ->
                    startActivity(new Intent(this, UsuariosActivity.class)));
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
}
