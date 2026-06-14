package com.bingo.imperial;

import android.app.AlertDialog;
import android.content.ContentValues;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import com.bumptech.glide.Glide;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.URL;

public class CartonDetalleActivity extends AppCompatActivity {

    private int cartonId;
    private JSONObject carton;

    private ImageView imageView;
    private TextView tvNumero, tvEstado, tvComprador, tvTelefono, tvPrecio, tvNotas, tvFecha;
    private View infoComprador;
    private Button btnVender, btnReservar, btnLiberar, btnEliminarCarton;

    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_carton_detalle);

        cartonId = getIntent().getIntExtra("id", 0);
        String numero = getIntent().getStringExtra("numero");

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Cartón #" + numero);
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        imageView     = findViewById(R.id.imageView);
        tvNumero      = findViewById(R.id.tvNumero);
        tvEstado      = findViewById(R.id.tvEstado);
        tvComprador   = findViewById(R.id.tvComprador);
        tvTelefono    = findViewById(R.id.tvTelefono);
        tvPrecio      = findViewById(R.id.tvPrecio);
        tvNotas       = findViewById(R.id.tvNotas);
        tvFecha       = findViewById(R.id.tvFecha);
        infoComprador = findViewById(R.id.infoComprador);
        btnVender          = findViewById(R.id.btnVender);
        btnReservar        = findViewById(R.id.btnReservar);
        btnLiberar         = findViewById(R.id.btnLiberar);
        btnEliminarCarton  = findViewById(R.id.btnEliminarCarton);

        SessionManager session = new SessionManager(this);
        if (session.isAdmin()) btnEliminarCarton.setVisibility(android.view.View.VISIBLE);
        btnEliminarCarton.setOnClickListener(v -> confirmarEliminarCarton());

        findViewById(R.id.btnDescargar).setOnClickListener(v -> descargarImagen());

        cargarDetalle();
    }

    @Override
    protected void onResume() {
        super.onResume();
        cargarDetalle();
    }

    private void cargarDetalle() {
        ApiClient.get("/cartones/" + cartonId, new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        carton = new JSONObject(body);
                        mostrarDetalle();
                    } catch (Exception e) {
                        Toast.makeText(CartonDetalleActivity.this, "Error al cargar", Toast.LENGTH_SHORT).show();
                    }
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() -> Toast.makeText(CartonDetalleActivity.this, "Sin conexión", Toast.LENGTH_SHORT).show());
            }
        });
    }

    private void mostrarDetalle() throws Exception {
        String estado = carton.optString("estado", "");
        String numero = carton.optString("numero", "");

        Glide.with(this)
                .load(Config.MEDIA_URL + "/cartones/" + cartonId + "/imagen")
                .skipMemoryCache(true)
                .diskCacheStrategy(com.bumptech.glide.load.engine.DiskCacheStrategy.NONE)
                .into(imageView);

        tvNumero.setText("Cartón #" + numero);
        tvEstado.setText(estado.toUpperCase());

        int color;
        switch (estado) {
            case "disponible": color = 0xFF22C55E; break;
            case "vendido":    color = 0xFFEF4444; break;
            case "reservado":  color = 0xFFF59E0B; break;
            default:           color = 0xFF6B7280; break;
        }
        tvEstado.setTextColor(color);

        String comprador = carton.isNull("comprador") ? "" : carton.optString("comprador", "");
        if (!comprador.isEmpty()) {
            infoComprador.setVisibility(View.VISIBLE);
            tvComprador.setText(comprador);
            tvTelefono.setText(carton.optString("telefono_comprador", "-"));
            double precio = carton.optDouble("precio", 0);
            tvPrecio.setText(precio > 0 ? String.format("$%.2f", precio) : "-");
            tvNotas.setText(carton.optString("notas", "-"));
            tvFecha.setText(carton.optString("fecha_venta", "-"));
        } else {
            infoComprador.setVisibility(View.GONE);
        }

        btnVender.setVisibility(View.GONE);
        btnReservar.setVisibility(View.GONE);
        btnLiberar.setVisibility(View.GONE);

        SessionManager sessionDetalle = new SessionManager(this);
        boolean puedeVender  = sessionDetalle.tienePermiso(SessionManager.PERM_VENDER);
        boolean puedeReservar = sessionDetalle.tienePermiso(SessionManager.PERM_RESERVAR);
        boolean puedeLiberar  = sessionDetalle.tienePermiso(SessionManager.PERM_LIBERAR);

        switch (estado) {
            case "disponible":
                if (puedeVender)   btnVender.setVisibility(View.VISIBLE);
                if (puedeReservar) btnReservar.setVisibility(View.VISIBLE);
                break;
            case "reservado":
                if (puedeVender)  btnVender.setVisibility(View.VISIBLE);
                if (puedeLiberar) btnLiberar.setVisibility(View.VISIBLE);
                break;
            case "vendido":
                if (puedeLiberar) {
                    btnLiberar.setVisibility(View.VISIBLE);
                    btnLiberar.setText("Liberar (devolver)");
                }
                break;
        }

        btnVender.setOnClickListener(v -> mostrarDialogoVender());
        btnReservar.setOnClickListener(v -> mostrarDialogoReservar());
        btnLiberar.setOnClickListener(v -> confirmarLiberar());
    }

    private void mostrarDialogoVender() {
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_vender, null);
        EditText etComprador = view.findViewById(R.id.etComprador);
        EditText etTelefono  = view.findViewById(R.id.etTelefono);
        EditText etPrecio    = view.findViewById(R.id.etPrecio);
        EditText etNotas     = view.findViewById(R.id.etNotas);

        etComprador.setText(carton.optString("comprador", ""));
        etTelefono.setText(carton.optString("telefono_comprador", ""));

        new AlertDialog.Builder(this)
                .setTitle("Vender Cartón #" + carton.optString("numero"))
                .setView(view)
                .setPositiveButton("Vender", (d, w) -> {
                    String comp = etComprador.getText().toString().trim();
                    if (comp.isEmpty()) {
                        Toast.makeText(this, "Nombre del comprador requerido", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    try {
                        JSONObject body = new JSONObject();
                        body.put("comprador", comp);
                        body.put("telefono", etTelefono.getText().toString());
                        String ps = etPrecio.getText().toString();
                        if (!ps.isEmpty()) body.put("precio", Double.parseDouble(ps));
                        body.put("notas", etNotas.getText().toString());
                        ApiClient.post("/cartones/" + cartonId + "/vender", body.toString(), new ApiClient.Callback() {
                            @Override public void onSuccess(String b) { handler.post(() -> cargarDetalle()); }
                            @Override public void onError(String e) { handler.post(() -> Toast.makeText(CartonDetalleActivity.this, "Error al vender", Toast.LENGTH_SHORT).show()); }
                        });
                    } catch (Exception ignored) {}
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void mostrarDialogoReservar() {
        View view = LayoutInflater.from(this).inflate(R.layout.dialog_reservar, null);
        EditText etComprador = view.findViewById(R.id.etComprador);
        EditText etTelefono  = view.findViewById(R.id.etTelefono);

        new AlertDialog.Builder(this)
                .setTitle("Reservar Cartón #" + carton.optString("numero"))
                .setView(view)
                .setPositiveButton("Reservar", (d, w) -> {
                    try {
                        JSONObject body = new JSONObject();
                        body.put("comprador", etComprador.getText().toString());
                        body.put("telefono", etTelefono.getText().toString());
                        ApiClient.post("/cartones/" + cartonId + "/reservar", body.toString(), new ApiClient.Callback() {
                            @Override public void onSuccess(String b) { handler.post(() -> cargarDetalle()); }
                            @Override public void onError(String e) { handler.post(() -> Toast.makeText(CartonDetalleActivity.this, "Error al reservar", Toast.LENGTH_SHORT).show()); }
                        });
                    } catch (Exception ignored) {}
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void confirmarLiberar() {
        new AlertDialog.Builder(this)
                .setTitle("Liberar cartón")
                .setMessage("¿Marcar como disponible?")
                .setPositiveButton("Liberar", (d, w) -> {
                    ApiClient.post("/cartones/" + cartonId + "/liberar", "{}", new ApiClient.Callback() {
                        @Override public void onSuccess(String b) { handler.post(() -> cargarDetalle()); }
                        @Override public void onError(String e) { handler.post(() -> Toast.makeText(CartonDetalleActivity.this, "Error", Toast.LENGTH_SHORT).show()); }
                    });
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void confirmarEliminarCarton() {
        String numero = carton != null ? carton.optString("numero", "") : "";
        new AlertDialog.Builder(this)
                .setTitle("Eliminar cartón")
                .setMessage("¿Eliminar el cartón #" + numero + "? Esta acción no se puede deshacer.")
                .setPositiveButton("Eliminar", (d, w) -> {
                    ApiClient.delete("/cartones/" + cartonId, new ApiClient.Callback() {
                        @Override
                        public void onSuccess(String body) {
                            handler.post(() -> {
                                Toast.makeText(CartonDetalleActivity.this, "Cartón eliminado", Toast.LENGTH_SHORT).show();
                                finish();
                            });
                        }
                        @Override
                        public void onError(String error) {
                            handler.post(() -> Toast.makeText(CartonDetalleActivity.this, "Error al eliminar", Toast.LENGTH_SHORT).show());
                        }
                    });
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void descargarImagen() {
        Toast.makeText(this, "Descargando...", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            try {
                String url = Config.MEDIA_URL + "/cartones/" + cartonId + "/imagen";
                byte[] bytes = new URL(url).openStream().readAllBytes();

                String fileName = "carton_" + carton.optString("numero", String.valueOf(cartonId)) + ".jpg";
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
                    values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES);

                android.net.Uri uri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                if (uri != null) {
                    try (OutputStream os = getContentResolver().openOutputStream(uri)) {
                        os.write(bytes);
                    }
                    handler.post(() -> {
                        Toast.makeText(this, "Guardado en la galería", Toast.LENGTH_SHORT).show();
                        android.content.Intent shareIntent = new android.content.Intent(android.content.Intent.ACTION_SEND);
                        shareIntent.setType("image/jpeg");
                        shareIntent.putExtra(android.content.Intent.EXTRA_STREAM, uri);
                        shareIntent.addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivity(android.content.Intent.createChooser(shareIntent, "Compartir cartón"));
                    });
                }
            } catch (Exception e) {
                handler.post(() -> Toast.makeText(this, "Error al descargar", Toast.LENGTH_SHORT).show());
            }
        }).start();
    }

    @Override public boolean onSupportNavigateUp() { finish(); return true; }
}
