package com.bingo.imperial;

import android.content.Context;
import android.content.SharedPreferences;

public class SessionManager {
    private static final String PREFS = "bingo_session";
    private static final String KEY_TOKEN    = "token";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_ROL      = "rol";

    private final SharedPreferences prefs;

    public SessionManager(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public void guardarSesion(String token, String username, String rol) {
        prefs.edit().putString(KEY_TOKEN, token)
                    .putString(KEY_USERNAME, username)
                    .putString(KEY_ROL, rol)
                    .apply();
    }

    public String getToken()    { return prefs.getString(KEY_TOKEN, null); }
    public String getUsername() { return prefs.getString(KEY_USERNAME, ""); }
    public String getRol()      { return prefs.getString(KEY_ROL, ""); }
    public boolean isLoggedIn() { return getToken() != null; }

    public void cerrarSesion() {
        prefs.edit().clear().apply();
    }
}
