package com.bingo.imperial;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class CartonesActivity extends AppCompatActivity {

    private RecyclerView recyclerView;
    private CartonAdapter adapter;
    private SwipeRefreshLayout swipeRefresh;
    private EditText searchInput;
    private ChipGroup chipGroup;
    private TextView tvTotal;

    private String estado = "";
    private String busqueda = "";
    private int page = 1;
    private int totalPaginas = 1;
    private boolean cargando = false;
    private final List<JSONObject> cartones = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cartones);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Cartones");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        if (getIntent().hasExtra("estado")) estado = getIntent().getStringExtra("estado");

        recyclerView = findViewById(R.id.recyclerView);
        swipeRefresh = findViewById(R.id.swipeRefresh);
        searchInput  = findViewById(R.id.searchInput);
        chipGroup    = findViewById(R.id.chipGroup);
        tvTotal      = findViewById(R.id.tvTotal);

        swipeRefresh.setColorSchemeColors(0xFF6C63FF);
        swipeRefresh.setOnRefreshListener(() -> cargar(1, true));

        GridLayoutManager lm = new GridLayoutManager(this, 2);
        recyclerView.setLayoutManager(lm);
        adapter = new CartonAdapter(cartones, carton -> {
            try {
                Intent intent = new Intent(this, CartonDetalleActivity.class);
                intent.putExtra("id", carton.getInt("id"));
                intent.putExtra("numero", carton.getString("numero"));
                startActivity(intent);
            } catch (Exception ignored) {}
        });
        recyclerView.setAdapter(adapter);

        recyclerView.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override
            public void onScrolled(@androidx.annotation.NonNull RecyclerView rv, int dx, int dy) {
                if (!rv.canScrollVertically(1) && !cargando && page < totalPaginas)
                    cargar(page + 1, false);
            }
        });

        searchInput.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void afterTextChanged(Editable s) {}
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) {
                busqueda = s.toString();
                cargar(1, true);
            }
        });

        setupChips();
        cargar(1, true);
    }

    private void setupChips() {
        String[] labels = {"Todos", "Disponibles", "Vendidos", "Reservados"};
        String[] keys   = {"", "disponible", "vendido", "reservado"};
        for (int i = 0; i < labels.length; i++) {
            Chip chip = new Chip(this);
            chip.setText(labels[i]);
            chip.setCheckable(true);
            chip.setChecked(estado.equals(keys[i]));
            final String key = keys[i];
            chip.setOnCheckedChangeListener((btn, checked) -> {
                if (checked) { estado = key; cargar(1, true); }
            });
            chipGroup.addView(chip);
        }
    }

    private void cargar(int p, boolean reset) {
        if (cargando) return;
        cargando = true;
        if (reset) { cartones.clear(); adapter.notifyDataSetChanged(); }

        StringBuilder url = new StringBuilder("/cartones?page=" + p);
        if (!estado.isEmpty())   url.append("&estado=").append(estado);
        if (!busqueda.isEmpty()) url.append("&q=").append(busqueda);

        ApiClient.get(url.toString(), new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONObject json = new JSONObject(body);
                        JSONArray arr = json.getJSONArray("cartones");
                        totalPaginas = json.getInt("total_paginas");
                        page = p;
                        int total = json.getInt("total");
                        tvTotal.setText(total + " cartones");
                        for (int i = 0; i < arr.length(); i++) cartones.add(arr.getJSONObject(i));
                        adapter.notifyDataSetChanged();
                        if (total == 0 && !busqueda.isEmpty()) {
                            buscarNumeroGlobal(busqueda);
                        }
                    } catch (Exception ignored) {}
                    cargando = false;
                    swipeRefresh.setRefreshing(false);
                });
            }

            @Override
            public void onError(String error) {
                handler.post(() -> { cargando = false; swipeRefresh.setRefreshing(false); });
            }
        });
    }

    private void buscarNumeroGlobal(String numero) {
        ApiClient.get("/buscar-numero?q=" + numero, new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONObject j = new JSONObject(body);
                        if (!j.optBoolean("disponible", true)) {
                            String estado    = j.optString("estado", "");
                            String vendedor  = j.optString("vendedor", "Desconocido");
                            String grupo     = j.optString("grupo", "");
                            String comprador = j.optString("comprador", "");

                            String accion = estado.equals("vendido") ? "vendido" : "reservado";
                            StringBuilder msg = new StringBuilder(
                                    "El cartón " + numero + " fue " + accion + " por: " + vendedor);
                            if (!grupo.isEmpty())
                                msg.append("\nGrupo: ").append(grupo);
                            if (!comprador.isEmpty())
                                msg.append("\nComprador: ").append(comprador);

                            new AlertDialog.Builder(CartonesActivity.this)
                                    .setTitle("Cartón no disponible")
                                    .setMessage(msg.toString())
                                    .setPositiveButton("OK", null)
                                    .show();
                        }
                    } catch (Exception ignored) {}
                });
            }
            @Override
            public void onError(String error) {}
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
