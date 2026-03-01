FROM golang:1.23-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o /api ./cmd/api
RUN CGO_ENABLED=0 GOOS=linux go build -o /ws ./cmd/ws

FROM alpine:3.20

RUN apk --no-cache add ca-certificates tzdata

COPY --from=builder /api /usr/local/bin/api
COPY --from=builder /ws /usr/local/bin/ws

EXPOSE 8080 8081

CMD ["api"]
