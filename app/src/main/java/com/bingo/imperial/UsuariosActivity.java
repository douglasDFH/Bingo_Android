package com.bingo.imperial;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.widget.SwitchCompat;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.google.android.material.floatingactionbutton.FloatingActionButton;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class UsuariosActivity extends AppCompatActivity {

    private RecyclerView recyclerView;
    private SwipeRefreshLayout swipeRefresh;
    private UsuarioAdapter adapter;
    private final List<JSONObject> usuarios = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_usuarios);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Gestionar Usuarios");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        recyclerView = findViewById(R.id.recyclerView);
        swipeRefresh = findViewById(R.id.swipeRefresh);

        swipeRefresh.setColorSchemeColors(0xFF6C63FF);
        swipeRefresh.setOnRefreshListener(this::cargarUsuarios);

        adapter = new UsuarioAdapter(usuarios,
                this::mostrarDialogoEditar,
                this::confirmarEliminar);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        recyclerView.setAdapter(adapter);

        FloatingActionButton fab = findViewById(R.id.fab);
        fab.setOnClickListener(v -> mostrarDialogoCrear());

        cargarUsuarios();
    }

    private void cargarUsuarios() {
        swipeRefresh.setRefreshing(true);
        ApiClient.get("/auth/usuarios", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        usuarios.clear();
                        for (int i = 0; i < arr.length(); i++)
                            usuarios.add(arr.getJSONObject(i));
                        adapter.notifyDataSetChanged();
                    } catch (Exception ignored) {}
                    swipeRefresh.setRefreshing(false);
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> {
                    Toast.makeText(UsuariosActivity.this, "Error al cargar usuarios", Toast.LENGTH_SHORT).show();
                    swipeRefresh.setRefreshing(false);
                });
            }
        });
    }

    private ArrayAdapter<String> crearAdapterRoles() {
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, new String[]{"Admin", "Vendedor"});
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        return adapter;
    }

    private void mostrarDialogoCrear() {
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_usuario, null);
        EditText etUsername = view.findViewById(R.id.etUsername);
        EditText etPassword = view.findViewById(R.id.etPassword);
        EditText etConfirm  = view.findViewById(R.id.etConfirm);
        Spinner  spRol      = view.findViewById(R.id.spRol);
        spRol.setAdapter(crearAdapterRoles());
        spRol.setSelection(1); // Vendedor por defecto
        view.findViewById(R.id.layoutActivo).setVisibility(View.GONE);

        new AlertDialog.Builder(this)
                .setTitle("Crear Usuario")
                .setView(view)
                .setPositiveButton("Crear", (d, w) -> {
                    String username = etUsername.getText().toString().trim();
                    String password = etPassword.getText().toString();
                    String confirm  = etConfirm.getText().toString();
                    String rol = spRol.getSelectedItem().toString().equals("Admin") ? "admin" : "vendedor";

                    if (username.isEmpty() || password.isEmpty()) {
                        Toast.makeText(this, "Usuario y contraseña requeridos", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    if (!password.equals(confirm)) {
                        Toast.makeText(this, "Las contraseñas no coinciden", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    crearUsuario(username, password, rol);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void crearUsuario(String username, String password, String rol) {
        try {
            JSONObject body = new JSONObject();
            body.put("username", username);
            body.put("password", password);
            body.put("rol", rol);

            ApiClient.post("/auth/usuarios", body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String response) {
                    handler.post(() -> {
                        Toast.makeText(UsuariosActivity.this, "Usuario creado", Toast.LENGTH_SHORT).show();
                        cargarUsuarios();
                    });
                }
                @Override
                public void onError(String error) {
                    handler.post(() -> Toast.makeText(UsuariosActivity.this,
                            "Error: " + error, Toast.LENGTH_SHORT).show());
                }
            });
        } catch (Exception e) {
            Toast.makeText(this, "Error inesperado", Toast.LENGTH_SHORT).show();
        }
    }

    private void mostrarDialogoEditar(JSONObject usuario) {
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_usuario, null);
        EditText etUsername = view.findViewById(R.id.etUsername);
        EditText etPassword = view.findViewById(R.id.etPassword);
        EditText etConfirm  = view.findViewById(R.id.etConfirm);
        Spinner     spRol   = view.findViewById(R.id.spRol);
        spRol.setAdapter(crearAdapterRoles());
        SwitchCompat swActivo = view.findViewById(R.id.swActivo);

        try {
            etUsername.setText(usuario.getString("username"));
            etUsername.setEnabled(false);
            etUsername.setAlpha(0.5f);

            String rolActual = usuario.getString("rol");
            spRol.setSelection(rolActual.equals("admin") ? 0 : 1);

            swActivo.setChecked(usuario.getBoolean("activo"));
        } catch (Exception ignored) {}

        new AlertDialog.Builder(this)
                .setTitle("Editar Usuario")
                .setView(view)
                .setPositiveButton("Guardar", (d, w) -> {
                    String password = etPassword.getText().toString();
                    String confirm  = etConfirm.getText().toString();
                    String rol = spRol.getSelectedItem().toString().equals("Admin") ? "admin" : "vendedor";
                    boolean activo = swActivo.isChecked();

                    if (!password.isEmpty() && !password.equals(confirm)) {
                        Toast.makeText(this, "Las contraseñas no coinciden", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    try {
                        actualizarUsuario(usuario.getInt("id"), password, rol, activo);
                    } catch (Exception ignored) {}
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void actualizarUsuario(int userId, String password, String rol, boolean activo) {
        try {
            JSONObject body = new JSONObject();
            if (!password.isEmpty()) body.put("password", password);
            body.put("rol", rol);
            body.put("activo", activo);

            ApiClient.put("/auth/usuarios/" + userId, body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String response) {
                    handler.post(() -> {
                        Toast.makeText(UsuariosActivity.this, "Usuario actualizado", Toast.LENGTH_SHORT).show();
                        cargarUsuarios();
                    });
                }
                @Override
                public void onError(String error) {
                    handler.post(() -> Toast.makeText(UsuariosActivity.this,
                            "Error: " + error, Toast.LENGTH_SHORT).show());
                }
            });
        } catch (Exception e) {
            Toast.makeText(this, "Error inesperado", Toast.LENGTH_SHORT).show();
        }
    }

    private void confirmarEliminar(JSONObject usuario) {
        try {
            String username = usuario.getString("username");
            int userId = usuario.getInt("id");
            new AlertDialog.Builder(this)
                    .setTitle("Eliminar usuario")
                    .setMessage("¿Eliminar al usuario '" + username + "'?")
                    .setPositiveButton("Eliminar", (d, w) -> eliminarUsuario(userId))
                    .setNegativeButton("Cancelar", null)
                    .show();
        } catch (Exception ignored) {}
    }

    private void eliminarUsuario(int userId) {
        ApiClient.delete("/auth/usuarios/" + userId, new ApiClient.Callback() {
            @Override
            public void onSuccess(String response) {
                handler.post(() -> {
                    Toast.makeText(UsuariosActivity.this, "Usuario eliminado", Toast.LENGTH_SHORT).show();
                    cargarUsuarios();
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> Toast.makeText(UsuariosActivity.this,
                        "Error al eliminar: " + error, Toast.LENGTH_SHORT).show());
            }
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }


    // ── Adapter ────────────────────────────────────────────────────────────────

    interface OnEditListener  { void onEdit(JSONObject u); }
    interface OnDeleteListener { void onDelete(JSONObject u); }

    static class UsuarioAdapter extends RecyclerView.Adapter<UsuarioAdapter.VH> {
        private final List<JSONObject> items;
        private final OnEditListener onEdit;
        private final OnDeleteListener onDelete;

        UsuarioAdapter(List<JSONObject> items, OnEditListener onEdit, OnDeleteListener onDelete) {
            this.items    = items;
            this.onEdit   = onEdit;
            this.onDelete = onDelete;
        }

        @Override
        public VH onCreateViewHolder(ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.item_usuario, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(VH h, int position) {
            JSONObject u = items.get(position);
            try {
                String username = u.getString("username");
                String rol      = u.getString("rol");
                boolean activo  = u.optBoolean("activo", true);

                h.tvAvatar.setText(String.valueOf(username.charAt(0)).toUpperCase());
                h.tvUsername.setText(username);
                h.tvRol.setText(rol.equals("admin") ? "ADMIN" : "VENDEDOR");

                if (rol.equals("admin")) {
                    h.tvRol.setBackgroundResource(R.drawable.badge_bg);
                } else {
                    h.tvRol.setBackgroundResource(R.drawable.badge_green_bg);
                }

                h.tvActivo.setText(activo ? "activo" : "inactivo");
                h.tvActivo.setBackgroundResource(activo ? R.drawable.badge_green_bg : R.drawable.badge_red_bg);

                h.btnEditar.setOnClickListener(v -> onEdit.onEdit(u));
                h.btnEliminar.setOnClickListener(v -> onDelete.onDelete(u));
            } catch (Exception ignored) {}
        }

        @Override public int getItemCount() { return items.size(); }

        static class VH extends RecyclerView.ViewHolder {
            TextView tvAvatar, tvUsername, tvRol, tvActivo;
            ImageButton btnEditar, btnEliminar;
            VH(View v) {
                super(v);
                tvAvatar   = v.findViewById(R.id.tvAvatar);
                tvUsername = v.findViewById(R.id.tvUsername);
                tvRol      = v.findViewById(R.id.tvRol);
                tvActivo   = v.findViewById(R.id.tvActivo);
                btnEditar  = v.findViewById(R.id.btnEditar);
                btnEliminar = v.findViewById(R.id.btnEliminar);
            }
        }
    }
}
