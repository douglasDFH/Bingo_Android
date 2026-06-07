package com.bingo.imperial;

import java.io.File;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class ApiClient {

    private static final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build();

    // Cliente con timeouts extendidos solo para subir archivos grandes
    private static final OkHttpClient uploadClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.MINUTES)
            .readTimeout(10, TimeUnit.MINUTES)
            .build();
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private static String token = null;

    public static void setToken(String t) { token = t; }
    public static String getToken()       { return token; }

    public interface Callback {
        void onSuccess(String body);
        void onError(String error);
    }

    private static Request.Builder baseRequest(String url) {
        Request.Builder builder = new Request.Builder().url(url);
        if (token != null) builder.header("Authorization", "Bearer " + token);
        return builder;
    }

    public static void get(String path, Callback callback) {
        Request request = baseRequest(Config.BASE_URL + path).build();
        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(Call call, IOException e) {
                callback.onError(e.getMessage());
            }
            @Override public void onResponse(Call call, Response response) throws IOException {
                String bodyStr = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) { callback.onError("HTTP " + response.code()); return; }
                if (bodyStr.startsWith("<") || bodyStr.startsWith("<!")) {
                    callback.onError("Proxy error: respuesta HTML inesperada (HTTP " + response.code() + ")");
                    return;
                }
                callback.onSuccess(bodyStr);
            }
        });
    }

    public static void post(String path, String jsonBody, Callback callback) {
        RequestBody body = RequestBody.create(jsonBody, JSON);
        Request request = baseRequest(Config.BASE_URL + path).post(body).build();
        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(Call call, IOException e) {
                callback.onError(e.getMessage());
            }
            @Override public void onResponse(Call call, Response response) throws IOException {
                String bodyStr = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    callback.onError("HTTP " + response.code() + ": " + bodyStr.substring(0, Math.min(200, bodyStr.length())));
                    return;
                }
                // Si el servidor devuelve HTML en vez de JSON, es un problema del proxy
                if (bodyStr.startsWith("<") || bodyStr.startsWith("<!")) {
                    callback.onError("Proxy error (HTTP " + response.code() + "): el servidor devolvio HTML. Verifica HTTPS en Coolify. Respuesta: " + bodyStr.substring(0, Math.min(200, bodyStr.length())));
                    return;
                }
                callback.onSuccess(bodyStr);
            }
        });
    }

    public static void put(String path, String jsonBody, Callback callback) {
        RequestBody body = RequestBody.create(jsonBody, JSON);
        Request request = baseRequest(Config.BASE_URL + path).put(body).build();
        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(Call call, IOException e) {
                callback.onError(e.getMessage());
            }
            @Override public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) { callback.onError("Error " + response.code()); return; }
                callback.onSuccess(response.body().string());
            }
        });
    }

    public static void delete(String path, Callback callback) {
        Request request = baseRequest(Config.BASE_URL + path).delete().build();
        client.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(Call call, IOException e) {
                callback.onError(e.getMessage());
            }
            @Override public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) { callback.onError("Error " + response.code()); return; }
                callback.onSuccess(response.body().string());
            }
        });
    }

    public static void uploadPdf(File file, Callback callback) {
        RequestBody fileBody = RequestBody.create(file, MediaType.get("application/pdf"));
        MultipartBody body = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("pdf", file.getName(), fileBody)
                .build();
        Request request = baseRequest(Config.BASE_URL + "/subir-pdf").post(body).build();
        uploadClient.newCall(request).enqueue(new okhttp3.Callback() {
            @Override public void onFailure(Call call, IOException e) {
                callback.onError(e.getMessage());
            }
            @Override public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) { callback.onError("Error " + response.code()); return; }
                callback.onSuccess(response.body().string());
            }
        });
    }
}
