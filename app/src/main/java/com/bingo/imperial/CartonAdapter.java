package com.bingo.imperial;

import android.content.res.ColorStateList;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONObject;

import java.util.List;

public class CartonAdapter extends RecyclerView.Adapter<CartonAdapter.ViewHolder> {

    public interface OnClickListener { void onClick(JSONObject carton); }

    private final List<JSONObject> items;
    private final OnClickListener listener;

    public CartonAdapter(List<JSONObject> items, OnClickListener listener) {
        this.items = items;
        this.listener = listener;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_carton, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder h, int position) {
        JSONObject item = items.get(position);
        try {
            String estado    = item.optString("estado", "");
            String numero    = item.optString("numero", "");
            String comprador = item.isNull("comprador") ? "" : item.optString("comprador", "");
            double precio    = item.optDouble("precio", 0);

            h.tvNumero.setText("#" + numero);
            h.tvEstado.setText(estado.toUpperCase());

            h.tvComprador.setVisibility(comprador.isEmpty() ? View.GONE : View.VISIBLE);
            h.tvComprador.setText(comprador);

            h.tvPrecio.setVisibility(precio > 0 ? View.VISIBLE : View.GONE);
            h.tvPrecio.setText(String.format("$%.2f", precio));

            int color, bg;
            switch (estado) {
                case "disponible": color = 0xFF22C55E; bg = 0x2222C55E; break;
                case "vendido":    color = 0xFFEF4444; bg = 0x22EF4444; break;
                case "reservado":  color = 0xFFF59E0B; bg = 0x22F59E0B; break;
                default:           color = 0xFF6B7280; bg = 0x226B7280; break;
            }
            h.tvEstado.setTextColor(color);
            h.estadoBadge.setBackgroundTintList(ColorStateList.valueOf(bg));
            h.itemView.setOnClickListener(v -> listener.onClick(item));
        } catch (Exception ignored) {}
    }

    @Override public int getItemCount() { return items.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        TextView tvNumero, tvEstado, tvComprador, tvPrecio;
        View estadoBadge;
        ViewHolder(View v) {
            super(v);
            tvNumero    = v.findViewById(R.id.tvNumero);
            tvEstado    = v.findViewById(R.id.tvEstado);
            tvComprador = v.findViewById(R.id.tvComprador);
            tvPrecio    = v.findViewById(R.id.tvPrecio);
            estadoBadge = v.findViewById(R.id.estadoBadge);
        }
    }
}
