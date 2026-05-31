package com.bingo.imperial;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class PDFsActivity extends AppCompatActivity {

    private RecyclerView recyclerView;
    private SwipeRefreshLayout swipeRefresh;
    private PDFAdapter adapter;
    private final List<JSONObject> pdfs = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_pdfs);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("PDFs subidos");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        recyclerView = findViewById(R.id.recyclerView);
        swipeRefresh = findViewById(R.id.swipeRefresh);
        swipeRefresh.setColorSchemeColors(0xFF6C63FF);
        swipeRefresh.setOnRefreshListener(this::cargar);

        adapter = new PDFAdapter(pdfs, this::confirmarEliminar);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        recyclerView.setAdapter(adapter);

        cargar();
    }

    private void cargar() {
        swipeRefresh.setRefreshing(true);
        ApiClient.get("/pdfs", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        pdfs.clear();
                        for (int i = 0; i < arr.length(); i++)
                            pdfs.add(arr.getJSONObject(i));
                        adapter.notifyDataSetChanged();
                    } catch (Exception ignored) {}
                    swipeRefresh.setRefreshing(false);
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> {
                    Toast.makeText(PDFsActivity.this, "Error al cargar PDFs", Toast.LENGTH_SHORT).show();
                    swipeRefresh.setRefreshing(false);
                });
            }
        });
    }

    private void confirmarEliminar(JSONObject pdf) {
        try {
            String nombre = pdf.getString("nombre_archivo");
            int total = pdf.optInt("total_cartones", 0);
            int id = pdf.getInt("id");
            new AlertDialog.Builder(this)
                    .setTitle("Eliminar PDF")
                    .setMessage("¿Eliminar \"" + nombre + "\"?\n\nEsto eliminará también los " + total + " cartones asociados.\nEsta acción no se puede deshacer.")
                    .setPositiveButton("Eliminar todo", (d, w) -> eliminarPDF(id))
                    .setNegativeButton("Cancelar", null)
                    .show();
        } catch (Exception ignored) {}
    }

    private void eliminarPDF(int pdfId) {
        ApiClient.delete("/pdfs/" + pdfId, new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    Toast.makeText(PDFsActivity.this, "PDF y cartones eliminados", Toast.LENGTH_SHORT).show();
                    cargar();
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> Toast.makeText(PDFsActivity.this, "Error al eliminar", Toast.LENGTH_SHORT).show());
            }
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }


    // ── Adapter ──────────────────────────────────────────────────────────────

    interface OnDeleteListener { void onDelete(JSONObject pdf); }

    static class PDFAdapter extends RecyclerView.Adapter<PDFAdapter.VH> {
        private final List<JSONObject> items;
        private final OnDeleteListener onDelete;

        PDFAdapter(List<JSONObject> items, OnDeleteListener onDelete) {
            this.items = items;
            this.onDelete = onDelete;
        }

        @Override
        public VH onCreateViewHolder(ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.item_pdf, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(VH h, int pos) {
            JSONObject p = items.get(pos);
            try {
                h.tvNombre.setText(p.getString("nombre_archivo"));
                int totalCartones = p.optInt("total_cartones", p.optInt("paginas_ok", 0));
                h.tvCartones.setText(totalCartones + " cartones");
                h.tvEstado.setText(p.optString("estado", ""));

                String fecha = p.optString("fecha_procesado", "");
                if (fecha.length() > 10) fecha = fecha.substring(0, 10);
                h.tvFecha.setText(fecha);

                h.btnEliminar.setOnClickListener(v -> onDelete.onDelete(p));
            } catch (Exception ignored) {}
        }

        @Override public int getItemCount() { return items.size(); }

        static class VH extends RecyclerView.ViewHolder {
            TextView tvNombre, tvCartones, tvEstado, tvFecha;
            ImageButton btnEliminar;
            VH(View v) {
                super(v);
                tvNombre    = v.findViewById(R.id.tvNombre);
                tvCartones  = v.findViewById(R.id.tvCartones);
                tvEstado    = v.findViewById(R.id.tvEstado);
                tvFecha     = v.findViewById(R.id.tvFecha);
                btnEliminar = v.findViewById(R.id.btnEliminar);
            }
        }
    }
}
