package com.bingo.imperial;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.floatingactionbutton.FloatingActionButton;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class GruposActivity extends AppCompatActivity implements GrupoAdapter.Listener {

    private RecyclerView rvGrupos;
    private View emptyView;
    private final List<GrupoAdapter.GrupoItem> grupos = new ArrayList<>();
    private GrupoAdapter adapter;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_grupos);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Grupos");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        rvGrupos = findViewById(R.id.rvGrupos);
        emptyView = findViewById(R.id.emptyView);

        adapter = new GrupoAdapter(grupos, this);
        rvGrupos.setLayoutManager(new LinearLayoutManager(this));
        rvGrupos.setAdapter(adapter);

        FloatingActionButton fab = findViewById(R.id.fabAgregarGrupo);
        fab.setOnClickListener(v -> mostrarDialogCrear());

        cargarGrupos();
    }

    private void cargarGrupos() {
        ApiClient.get("/grupos", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        grupos.clear();
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject obj = arr.getJSONObject(i);
                            grupos.add(new GrupoAdapter.GrupoItem(
                                    obj.getInt("id"),
                                    obj.getString("nombre"),
                                    obj.optInt("total_usuarios", 0)
                            ));
                        }
                        adapter.notifyDataSetChanged();
                        emptyView.setVisibility(grupos.isEmpty() ? View.VISIBLE : View.GONE);
                        rvGrupos.setVisibility(grupos.isEmpty() ? View.GONE : View.VISIBLE);
                    } catch (Exception ignored) {}
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() ->
                        Toast.makeText(GruposActivity.this, "Error al cargar grupos", Toast.LENGTH_SHORT).show());
            }
        });
    }

    private void mostrarDialogCrear() {
        EditText et = new EditText(this);
        et.setHint("Nombre del grupo");

        new AlertDialog.Builder(this)
                .setTitle("Nuevo grupo")
                .setView(et)
                .setPositiveButton("Crear", (d, w) -> {
                    String nombre = et.getText().toString().trim();
                    if (nombre.isEmpty()) {
                        Toast.makeText(this, "Ingresa un nombre", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    crearGrupo(nombre);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void crearGrupo(String nombre) {
        try {
            JSONObject body = new JSONObject();
            body.put("nombre", nombre);
            ApiClient.post("/grupos", body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String resp) {
                    handler.post(() -> {
                        Toast.makeText(GruposActivity.this, "Grupo creado ✓", Toast.LENGTH_SHORT).show();
                        cargarGrupos();
                    });
                }
                @Override
                public void onError(String error) {
                    handler.post(() ->
                            Toast.makeText(GruposActivity.this, "Error: " + error, Toast.LENGTH_SHORT).show());
                }
            });
        } catch (Exception e) {
            Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onEditar(GrupoAdapter.GrupoItem grupo) {
        EditText et = new EditText(this);
        et.setText(grupo.nombre);
        et.setSelectAllOnFocus(true);

        new AlertDialog.Builder(this)
                .setTitle("Renombrar grupo")
                .setView(et)
                .setPositiveButton("Guardar", (d, w) -> {
                    String nombre = et.getText().toString().trim();
                    if (nombre.isEmpty()) {
                        Toast.makeText(this, "El nombre no puede estar vacío", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    renombrarGrupo(grupo.id, nombre);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void renombrarGrupo(int grupoId, String nombre) {
        try {
            JSONObject body = new JSONObject();
            body.put("nombre", nombre);
            ApiClient.put("/grupos/" + grupoId, body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String resp) {
                    handler.post(() -> {
                        Toast.makeText(GruposActivity.this, "Grupo renombrado ✓", Toast.LENGTH_SHORT).show();
                        cargarGrupos();
                    });
                }
                @Override
                public void onError(String error) {
                    handler.post(() ->
                            Toast.makeText(GruposActivity.this, "Error: " + error, Toast.LENGTH_SHORT).show());
                }
            });
        } catch (Exception e) {
            Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onEliminar(GrupoAdapter.GrupoItem grupo) {
        new AlertDialog.Builder(this)
                .setTitle("Eliminar grupo")
                .setMessage("¿Eliminar \"" + grupo.nombre + "\"?\n\nLos usuarios del grupo quedarán sin grupo asignado.")
                .setPositiveButton("Eliminar", (d, w) -> eliminarGrupo(grupo.id))
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void eliminarGrupo(int grupoId) {
        ApiClient.delete("/grupos/" + grupoId, new ApiClient.Callback() {
            @Override
            public void onSuccess(String resp) {
                handler.post(() -> {
                    Toast.makeText(GruposActivity.this, "Grupo eliminado", Toast.LENGTH_SHORT).show();
                    cargarGrupos();
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() ->
                        Toast.makeText(GruposActivity.this, "Error: " + error, Toast.LENGTH_SHORT).show());
            }
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
