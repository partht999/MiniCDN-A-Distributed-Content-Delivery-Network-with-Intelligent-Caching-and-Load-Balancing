package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

type Node struct {
	ID     string `json:"id"`
	Host   string `json:"host"`
	Port   int    `json:"port"`
	Region string `json:"region"`
	Weight int    `json:"weight"`
}

type PurgeRequest struct {
	URLs []string `json:"urls"`
}

var (
	redisClient *redis.Client
	ctx         = context.Background()
	port        = "7000"
)

func main() {
	if p := os.Getenv("PORT"); p != "" {
		port = p
	}

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379"
	}

	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Fatalf("Failed to parse Redis URL: %v", err)
	}

	redisClient = redis.NewClient(opt)
	defer redisClient.Close()

	// Ping Redis to verify connection
	for i := 0; i < 5; i++ {
		_, err = redisClient.Ping(ctx).Result()
		if err == nil {
			break
		}
		log.Printf("Waiting for Redis... (%d/5)", i+1)
		time.Sleep(2 * time.Second)
	}
	if err != nil {
		log.Fatalf("Could not connect to Redis: %v", err)
	}
	log.Println("Connected to Redis successfully.")

	http.HandleFunc("/api/v1/nodes", handleNodes)
	http.HandleFunc("/api/v1/purge", handlePurge)

	log.Printf("Starting Control Plane on port %s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Control Plane failed to start: %v", err)
	}
}

func handleNodes(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodPost:
		var node Node
		if err := json.NewDecoder(r.Body).Decode(&node); err != nil {
			http.Error(w, "Bad request", http.StatusBadRequest)
			return
		}

		if node.ID == "" || node.Host == "" || node.Port == 0 {
			http.Error(w, "Missing required fields", http.StatusBadRequest)
			return
		}

		nodeData, err := json.Marshal(node)
		if err != nil {
			http.Error(w, "Internal error", http.StatusInternalServerError)
			return
		}

		// Store node info in Redis with a 15-second TTL
		redisKey := fmt.Sprintf("node:%s", node.ID)
		err = redisClient.Set(ctx, redisKey, nodeData, 15*time.Second).Err()
		if err != nil {
			log.Printf("Error storing node in Redis: %v", err)
			http.Error(w, "Failed to register node", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(map[string]string{"status": "registered"})

	case http.MethodGet:
		nodes, err := getActiveNodes()
		if err != nil {
			log.Printf("Error getting nodes: %v", err)
			http.Error(w, "Failed to retrieve nodes", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(nodes)

	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func handlePurge(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var purgeReq PurgeRequest
	if err := json.NewDecoder(r.Body).Decode(&purgeReq); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	if len(purgeReq.URLs) == 0 {
		http.Error(w, "No URLs provided for purge", http.StatusBadRequest)
		return
	}

	nodes, err := getActiveNodes()
	if err != nil {
		log.Printf("Error retrieving active nodes for purge: %v", err)
		http.Error(w, "Failed to retrieve nodes", http.StatusInternalServerError)
		return
	}

	if len(nodes) == 0 {
		log.Println("Purge received but no active nodes registered.")
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "skipped",
			"detail": "no active edge nodes found",
		})
		return
	}

	var wg sync.WaitGroup
	results := make(map[string]string)
	var mu sync.Mutex

	for _, node := range nodes {
		wg.Add(1)
		go func(n Node) {
			defer wg.Done()
			success := purgeNode(n, purgeReq.URLs)
			mu.Lock()
			if success {
				results[n.ID] = "success"
			} else {
				results[n.ID] = "failed"
			}
			mu.Unlock()
		}(node)
	}

	wg.Wait()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "completed",
		"details": results,
	})
}

func getActiveNodes() ([]Node, error) {
	keys, err := redisClient.Keys(ctx, "node:*").Result()
	if err != nil {
		return nil, err
	}

	nodes := make([]Node, 0, len(keys))
	for _, key := range keys {
		val, err := redisClient.Get(ctx, key).Result()
		if err != nil {
			// Key might have expired between Keys() and Get()
			continue
		}

		var node Node
		if err := json.Unmarshal([]byte(val), &node); err != nil {
			log.Printf("Error unmarshaling node data for key %s: %v", key, err)
			continue
		}
		nodes = append(nodes, node)
	}

	return nodes, nil
}

func purgeNode(node Node, urls []string) bool {
	// Send cache clear HTTP request to edge node
	purgeURL := fmt.Sprintf("http://%s:%d/internal/purge", node.Host, node.Port)
	log.Printf("Broadcasting purge request to %s: %v", purgeURL, urls)

	reqBody, err := json.Marshal(PurgeRequest{URLs: urls})
	if err != nil {
		log.Printf("Error marshaling purge request for node %s: %v", node.ID, err)
		return false
	}

	client := http.Client{Timeout: 5 * time.Second}
	resp, err := client.Post(purgeURL, "application/json", bytes.NewBuffer(reqBody))
	if err != nil {
		log.Printf("Failed to connect to edge %s for purge: %v", node.ID, err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Edge %s returned non-200 status for purge: %d", node.ID, resp.StatusCode)
		return false
	}

	return true
}
