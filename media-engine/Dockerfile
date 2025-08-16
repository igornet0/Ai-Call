# syntax=docker/dockerfile:1

FROM rust:1.79-alpine AS builder
RUN apk add --no-cache musl-dev pkgconfig
WORKDIR /app
COPY media-engine/Cargo.toml media-engine/Cargo.lock* ./media-engine/
COPY media-engine/src ./media-engine/src
WORKDIR /app/media-engine
RUN cargo build --release

FROM alpine:3.20
RUN adduser -D -H app
USER app
WORKDIR /home/app
COPY --from=builder /app/media-engine/target/release/media-engine /usr/local/bin/media-engine
ENV HOST=0.0.0.0
ENV PORT=7000
EXPOSE 7000
CMD ["/usr/local/bin/media-engine"]


