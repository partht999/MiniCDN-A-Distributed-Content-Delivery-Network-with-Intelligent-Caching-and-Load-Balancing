FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/control ./cmd/control

FROM alpine:latest
WORKDIR /
COPY --from=builder /app/control /control
ENV PORT=7000
EXPOSE 7000
CMD ["/control"]
