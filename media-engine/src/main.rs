use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::{get, post}, Json, Router};
use serde::{Deserialize, Serialize};
use std::{net::SocketAddr, sync::Arc};
use tracing::{error, info};

#[derive(Clone)]
struct AppState {}

#[derive(Debug, Deserialize)]
struct OfferRequest {
    sdp: String,
}

#[derive(Debug, Serialize)]
struct AnswerResponse {
    sdp: String,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();

    let app_state = Arc::new(AppState {});

    let app = Router::new()
        .route("/health", get(health))
        .route("/api/ai/offer", post(offer))
        .with_state(app_state);

    let host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
    let port: u16 = std::env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(7000);
    let addr: SocketAddr = format!("{}:{}", host, port).parse()?;
    info!(%addr, "media-engine listening");
    axum::serve(tokio::net::TcpListener::bind(addr).await?, app).await?;
    Ok(0.into())
}

fn init_tracing() {
    use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::registry()
        .with(filter)
        .with(fmt::layer())
        .init();
}

async fn health() -> impl IntoResponse {
    (StatusCode::OK, Json(serde_json::json!({"status":"ok"})))
}

async fn offer(State(_state): State<Arc<AppState>>, Json(req): Json<OfferRequest>) -> impl IntoResponse {
    // TODO: integrate with str0m to create a PeerConnection and generate an SDP answer
    info!(len = req.sdp.len(), "received offer");
    // Placeholder: echo minimal fake SDP to allow wiring tests. Replace with real SDP answer.
    let fake_answer_sdp = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=rtpmap:111 opus/48000/2\r\n".to_string();
    (StatusCode::OK, Json(AnswerResponse { sdp: fake_answer_sdp }))
}


