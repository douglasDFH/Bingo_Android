package com.bingo.imperial;

import android.content.Context;
import android.content.SharedPreferences;

public class SessionManager {
    private static final String PREFS        = "bingo_session";
    private static final String KEY_TOKEN    = "token";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_ROL      = "rol";
    private static final String KEY_USER_ID  = "user_id";
    private static final String KEY_PERMISOS = "permisos";

    // Permisos disponibles en el sistema
    public static final String PERM_SUBIR_PDF = "subir_pdf";
    public static final String PERM_VENDER    = "vender";
    public static final String PERM_RESERVAR  = "reservar";
    public static final String PERM_LIBERAR   = "liberar";

    private final SharedPreferences prefs;

    public SessionManager(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public void guardarSesion(String token, String username, String rol, int userId) {
        prefs.edit()
             .putString(KEY_TOKEN, token)
             .putString(KEY_USERNAME, username)
             .putString(KEY_ROL, rol)
             .putInt(KEY_USER_ID, userId)
             .apply();
    }

    /** Guarda los permisos recibidos del servidor como cadena CSV. */
    public void guardarPermisos(String permisosCsv) {
        prefs.edit().putString(KEY_PERMISOS, permisosCsv).apply();
    }

    public String getToken()    { return prefs.getString(KEY_TOKEN, null); }
    public String getUsername() { return prefs.getString(KEY_USERNAME, ""); }
    public String getRol()      { return prefs.getString(KEY_ROL, ""); }
    public int getUserId()      { return prefs.getInt(KEY_USER_ID, 0); }
    public boolean isAdmin()    { return "admin".equals(getRol()); }
    public boolean isLoggedIn() { return getToken() != null; }

    /**
     * Devuelve true si el usuario tiene el permiso dado.
     * El admin siempre tiene todos los permisos.
     */
    public boolean tienePermiso(String permiso) {
        if (isAdmin()) return true;
        String csv = prefs.getString(KEY_PERMISOS, PERM_VENDER + "," + PERM_RESERVAR + "," + PERM_LIBERAR);
        for (String p : csv.split(",")) {
            if (p.trim().equals(permiso)) return true;
        }
        return false;
    }

    public void cerrarSesion() {
        prefs.edit().clear().apply();
    }
}
