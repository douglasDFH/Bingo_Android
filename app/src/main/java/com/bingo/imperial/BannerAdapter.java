package com.bingo.imperial;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.bumptech.glide.load.model.GlideUrl;
import com.bumptech.glide.load.model.LazyHeaders;

import java.util.List;

public class BannerAdapter extends RecyclerView.Adapter<BannerAdapter.VH> {

    public interface Listener {
        void onEditar(BannerItem banner);
        void onEliminar(BannerItem banner);
    }

    public static class BannerItem {
        public final int id;
        public final String nombre;

        public BannerItem(int id, String nombre) {
            this.id = id;
            this.nombre = nombre;
        }
    }

    private final List<BannerItem> items;
    private final Listener listener;
    private final Context context;

    public BannerAdapter(Context context, List<BannerItem> items, Listener listener) {
        this.context = context;
        this.items = items;
        this.listener = listener;
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_banner, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH holder, int position) {
        BannerItem item = items.get(position);
        holder.tvNombre.setText(item.nombre);

        String imageUrl = Config.BASE_URL + "/banners/" + item.id + "/imagen";
        GlideUrl glideUrl = new GlideUrl(imageUrl,
                new LazyHeaders.Builder()
                        .addHeader("Authorization", "Bearer " + ApiClient.getToken())
                        .build());
        Glide.with(context)
                .load(glideUrl)
                .into(holder.ivThumb);

        holder.btnEditar.setOnClickListener(v -> listener.onEditar(item));
        holder.btnEliminar.setOnClickListener(v -> listener.onEliminar(item));
    }

    @Override
    public int getItemCount() {
        return items.size();
    }

    static class VH extends RecyclerView.ViewHolder {
        final ImageView ivThumb;
        final TextView tvNombre;
        final Button btnEditar;
        final Button btnEliminar;

        VH(View v) {
            super(v);
            ivThumb = v.findViewById(R.id.ivBannerThumb);
            tvNombre = v.findViewById(R.id.tvBannerNombre);
            btnEditar = v.findViewById(R.id.btnEditarBanner);
            btnEliminar = v.findViewById(R.id.btnEliminarBanner);
        }
    }
}
