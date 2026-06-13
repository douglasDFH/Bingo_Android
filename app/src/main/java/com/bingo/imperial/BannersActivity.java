package com.bingo.imperial;

import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.google.android.material.floatingactionbutton.FloatingActionButton;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class BannersActivity extends AppCompatActivity implements BannerAdapter.Listener {

    private RecyclerView rvBanners;
    private View emptyView;
    private final List<BannerAdapter.BannerItem> banners = new ArrayList<>();
    private BannerAdapter adapter;
    private final Handler handler = new Handler(Looper.getMainLooper());

    // Para el dialog de crear banner
    private Uri pickedImageUri;
    private ImageView dialogPreview;
    private TextView dialogTvImagen;

    private final ActivityResultLauncher<String[]> imagePicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    pickedImageUri = uri;
                    if (dialogPreview != null) {
                        dialogPreview.setVisibility(View.VISIBLE);
                        Glide.with(this).load(uri).into(dialogPreview);
                    }
                    if (dialogTvImagen != null) {
                        dialogTvImagen.setText("Imagen seleccionada ✓");
                    }
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_banners);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        getSupportActionBar().setTitle("Banners");
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        rvBanners = findViewById(R.id.rvBanners);
        emptyView = findViewById(R.id.emptyView);

        adapter = new BannerAdapter(this, banners, this);
        rvBanners.setLayoutManager(new LinearLayoutManager(this));
        rvBanners.setAdapter(adapter);

        FloatingActionButton fab = findViewById(R.id.fabAgregarBanner);
        fab.setOnClickListener(v -> mostrarDialogCrear());

        cargarBanners();
    }

    private void cargarBanners() {
        ApiClient.get("/banners", new ApiClient.Callback() {
            @Override
            public void onSuccess(String body) {
                handler.post(() -> {
                    try {
                        JSONArray arr = new JSONArray(body);
                        banners.clear();
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject obj = arr.getJSONObject(i);
                            banners.add(new BannerAdapter.BannerItem(
                                    obj.getInt("id"),
                                    obj.getString("nombre")
                            ));
                        }
                        adapter.notifyDataSetChanged();
                        emptyView.setVisibility(banners.isEmpty() ? View.VISIBLE : View.GONE);
                        rvBanners.setVisibility(banners.isEmpty() ? View.GONE : View.VISIBLE);
                    } catch (Exception ignored) {}
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() ->
                        Toast.makeText(BannersActivity.this, "Error al cargar banners", Toast.LENGTH_SHORT).show());
            }
        });
    }

    private void mostrarDialogCrear() {
        pickedImageUri = null;

        View dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_crear_banner, null);
        EditText etNombre = dialogView.findViewById(R.id.etNombreBanner);
        Button btnElegirImagen = dialogView.findViewById(R.id.btnElegirImagenBanner);
        dialogPreview = dialogView.findViewById(R.id.ivPreviewBanner);
        dialogTvImagen = dialogView.findViewById(R.id.tvImagenSeleccionada);

        btnElegirImagen.setOnClickListener(v ->
                imagePicker.launch(new String[]{"image/jpeg", "image/png"}));

        new AlertDialog.Builder(this)
                .setTitle("Nuevo banner")
                .setView(dialogView)
                .setPositiveButton("Guardar", (d, w) -> {
                    String nombre = etNombre.getText().toString().trim();
                    if (nombre.isEmpty()) {
                        Toast.makeText(this, "Ingresa un nombre", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    if (pickedImageUri == null) {
                        Toast.makeText(this, "Elige una imagen", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    subirBanner(nombre, pickedImageUri);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void subirBanner(String nombre, Uri imageUri) {
        Toast.makeText(this, "Subiendo banner...", Toast.LENGTH_SHORT).show();

        new Thread(() -> {
            try {
                InputStream is = getContentResolver().openInputStream(imageUri);
                java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
                byte[] buf = new byte[8192]; int len;
                while ((len = is.read(buf)) != -1) baos.write(buf, 0, len);
                is.close();
                byte[] imageBytes = baos.toByteArray();

                String mime = getContentResolver().getType(imageUri);
                String ext = (mime != null && mime.contains("png")) ? "png" : "jpg";

                OkHttpClient client = new OkHttpClient.Builder()
                        .connectTimeout(30, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(30, TimeUnit.SECONDS)
                        .build();

                RequestBody imageBody = RequestBody.create(
                        imageBytes, MediaType.get("image/*"));
                MultipartBody body = new MultipartBody.Builder()
                        .setType(MultipartBody.FORM)
                        .addFormDataPart("nombre", nombre)
                        .addFormDataPart("imagen", "banner." + ext, imageBody)
                        .build();

                Request req = new Request.Builder()
                        .url(Config.BASE_URL + "/banners")
                        .header("Authorization", "Bearer " + ApiClient.getToken())
                        .post(body)
                        .build();

                try (Response response = client.newCall(req).execute()) {
                    String respBody = response.body() != null ? response.body().string() : "";
                    if (response.isSuccessful()) {
                        handler.post(() -> {
                            Toast.makeText(this, "Banner creado ✓", Toast.LENGTH_SHORT).show();
                            cargarBanners();
                        });
                    } else {
                        handler.post(() ->
                                Toast.makeText(this, "Error: " + respBody, Toast.LENGTH_LONG).show());
                    }
                }
            } catch (Exception e) {
                handler.post(() ->
                        Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }).start();
    }

    @Override
    public void onEditar(BannerAdapter.BannerItem banner) {
        EditText etNombre = new EditText(this);
        etNombre.setText(banner.nombre);
        etNombre.setSelectAllOnFocus(true);

        new AlertDialog.Builder(this)
                .setTitle("Renombrar banner")
                .setView(etNombre)
                .setPositiveButton("Guardar", (d, w) -> {
                    String nuevoNombre = etNombre.getText().toString().trim();
                    if (nuevoNombre.isEmpty()) {
                        Toast.makeText(this, "El nombre no puede estar vacío", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    renameBanner(banner.id, nuevoNombre);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void renameBanner(int bannerId, String nuevoNombre) {
        try {
            JSONObject body = new JSONObject();
            body.put("nombre", nuevoNombre);
            ApiClient.put("/banners/" + bannerId, body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String resp) {
                    handler.post(() -> {
                        Toast.makeText(BannersActivity.this, "Banner renombrado ✓", Toast.LENGTH_SHORT).show();
                        cargarBanners();
                    });
                }
                @Override
                public void onError(String error) {
                    handler.post(() ->
                            Toast.makeText(BannersActivity.this, "Error: " + error, Toast.LENGTH_SHORT).show());
                }
            });
        } catch (Exception e) {
            Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onEliminar(BannerAdapter.BannerItem banner) {
        new AlertDialog.Builder(this)
                .setTitle("Eliminar banner")
                .setMessage("¿Eliminar \"" + banner.nombre + "\"?\n\nLos cartones ya generados no se modifican.")
                .setPositiveButton("Eliminar", (d, w) -> deleteBanner(banner.id))
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void deleteBanner(int bannerId) {
        ApiClient.delete("/banners/" + bannerId, new ApiClient.Callback() {
            @Override
            public void onSuccess(String resp) {
                handler.post(() -> {
                    Toast.makeText(BannersActivity.this, "Banner eliminado", Toast.LENGTH_SHORT).show();
                    cargarBanners();
                });
            }
            @Override
            public void onError(String error) {
                handler.post(() ->
                        Toast.makeText(BannersActivity.this, "Error: " + error, Toast.LENGTH_SHORT).show());
            }
        });
    }

    @Override
    public boolean onSupportNavigateUp() { finish(); return true; }
}
