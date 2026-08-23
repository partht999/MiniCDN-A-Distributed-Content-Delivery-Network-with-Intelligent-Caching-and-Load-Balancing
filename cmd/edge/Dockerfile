FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/edge ./cmd/edge

FROM alpine:latest
WORKDIR /
COPY --from=builder /app/edge /edge
ENV PORT=8080
EXPOSE 8080
CMD ["/edge"]
