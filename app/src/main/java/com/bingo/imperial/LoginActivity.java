package com.bingo.imperial;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONObject;

public class LoginActivity extends AppCompatActivity {

    private TextInputEditText etUsuario, etPassword;
    private Button btnLogin;
    private ProgressBar progressBar;
    private TextView tvError;
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        SessionManager session = new SessionManager(this);
        if (session.isLoggedIn()) {
            irAMain();
            return;
        }

        setContentView(R.layout.activity_login);

        etUsuario   = findViewById(R.id.etUsuario);
        etPassword  = findViewById(R.id.etPassword);
        btnLogin    = findViewById(R.id.btnLogin);
        progressBar = findViewById(R.id.progressBar);
        tvError     = findViewById(R.id.tvError);

        btnLogin.setOnClickListener(v -> intentarLogin());
    }

    private void intentarLogin() {
        String usuario  = etUsuario.getText().toString().trim();
        String password = etPassword.getText().toString();

        if (usuario.isEmpty() || password.isEmpty()) {
            mostrarError("Completa todos los campos");
            return;
        }

        btnLogin.setEnabled(false);
        progressBar.setVisibility(View.VISIBLE);
        tvError.setVisibility(View.GONE);

        try {
            JSONObject body = new JSONObject();
            body.put("username", usuario);
            body.put("password", password);

            ApiClient.post("/auth/login", body.toString(), new ApiClient.Callback() {
                @Override
                public void onSuccess(String response) {
                    handler.post(() -> {
                        try {
                            JSONObject json = new JSONObject(response);
                            String token = json.getString("token");
                            JSONObject user = json.getJSONObject("user");
                            new SessionManager(LoginActivity.this)
                                    .guardarSesion(token, user.getString("username"), user.getString("rol"));
                            irAMain();
                        } catch (Exception e) {
                            mostrarError("Error al procesar respuesta");
                        }
                    });
                }

                @Override
                public void onError(String error) {
                    handler.post(() -> mostrarError("Usuario o contraseña incorrectos"));
                }
            });
        } catch (Exception e) {
            mostrarError("Error inesperado");
        }
    }

    private void mostrarError(String msg) {
        btnLogin.setEnabled(true);
        progressBar.setVisibility(View.GONE);
        tvError.setText(msg);
        tvError.setVisibility(View.VISIBLE);
    }

    private void irAMain() {
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }
}
