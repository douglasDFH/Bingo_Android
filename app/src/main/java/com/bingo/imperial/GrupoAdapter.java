package com.bingo.imperial;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import java.util.List;

public class GrupoAdapter extends RecyclerView.Adapter<GrupoAdapter.VH> {

    public interface Listener {
        void onEditar(GrupoItem grupo);
        void onEliminar(GrupoItem grupo);
    }

    public static class GrupoItem {
        public final int id;
        public final String nombre;
        public final int totalUsuarios;

        public GrupoItem(int id, String nombre, int totalUsuarios) {
            this.id = id;
            this.nombre = nombre;
            this.totalUsuarios = totalUsuarios;
        }
    }

    private final List<GrupoItem> items;
    private final Listener listener;

    public GrupoAdapter(List<GrupoItem> items, Listener listener) {
        this.items = items;
        this.listener = listener;
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_grupo, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH holder, int position) {
        GrupoItem item = items.get(position);
        holder.tvNombre.setText(item.nombre);
        holder.tvUsuarios.setText(item.totalUsuarios + " usuario" + (item.totalUsuarios != 1 ? "s" : ""));
        holder.btnEditar.setOnClickListener(v -> listener.onEditar(item));
        holder.btnEliminar.setOnClickListener(v -> listener.onEliminar(item));
    }

    @Override
    public int getItemCount() { return items.size(); }

    static class VH extends RecyclerView.ViewHolder {
        final TextView tvNombre, tvUsuarios;
        final Button btnEditar, btnEliminar;

        VH(View v) {
            super(v);
            tvNombre   = v.findViewById(R.id.tvGrupoNombre);
            tvUsuarios = v.findViewById(R.id.tvGrupoUsuarios);
            btnEditar  = v.findViewById(R.id.btnEditarGrupo);
            btnEliminar = v.findViewById(R.id.btnEliminarGrupo);
        }
    }
}
