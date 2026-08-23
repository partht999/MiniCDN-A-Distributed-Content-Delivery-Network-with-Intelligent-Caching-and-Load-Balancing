FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/origin ./cmd/origin

FROM alpine:latest
WORKDIR /
COPY --from=builder /app/origin /origin
ENV CONTENT_DIR=/sample-content
ENV PORT=9000
EXPOSE 9000
CMD ["/origin"]
