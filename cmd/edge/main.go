package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"mini-cdn/pkg/cache"
)

var (
	nodeID     = "edge-1"
	region     = "local"
	originURL  = "http://localhost:9000"
	controlURL = "http://localhost:7000"
	port       = "8080"
	cdnCache   *cache.Cache
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

func main() {
	if nid := os.Getenv("NODE_ID"); nid != "" {
		nodeID = nid
	}
	if reg := os.Getenv("REGION"); reg != "" {
		region = reg
	}
	if orig := os.Getenv("ORIGIN_URL"); orig != "" {
		originURL = orig
	}
	if ctrl := os.Getenv("CONTROL_URL"); ctrl != "" {
		controlURL = ctrl
	}
	if p := os.Getenv("PORT"); p != "" {
		port = p
	}

	cdnCache = cache.NewCache()

	log.Printf("Starting Edge Node %s in region %s on port %s", nodeID, region, port)
	log.Printf("Origin URL: %s, Control URL: %s", originURL, controlURL)

	// Start Heartbeat registration background worker
	go startHeartbeat()

	http.HandleFunc("/health", handleHealth)
	http.HandleFunc("/internal/purge", handlePurge)
	http.HandleFunc("/", handleProxy)

	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatalf("Edge Node failed to start: %v", err)
	}
}

func startHeartbeat() {
	// Register immediately, then every 5 seconds
	for {
		registerWithControl()
		time.Sleep(5 * time.Second)
	}
}

func registerWithControl() {
	regURL := fmt.Sprintf("%s/api/v1/nodes", controlURL)

	node := Node{
		ID:     nodeID,
		Host:   nodeID, // host matches service name in docker-compose network
		Port:   8080,   // internal port inside container
		Region: region,
		Weight: 100,
	}

	bodyBytes, err := json.Marshal(node)
	if err != nil {
		log.Printf("Heartbeat: failed to marshal node info: %v", err)
		return
	}

	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Post(regURL, "application/json", bytes.NewBuffer(bodyBytes))
	if err != nil {
		log.Printf("Heartbeat: registration failed to %s: %v", regURL, err)
		return
	}
	resp.Body.Close()
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	_, _, hitRatio := cdnCache.Stats()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "ok",
		"node_id":   nodeID,
		"region":    region,
		"hit_ratio": hitRatio,
	})
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

	for _, url := range purgeReq.URLs {
		log.Printf("[%s] Evicting from cache: %s", nodeID, url)
		cdnCache.Delete(url)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "cleared"})
}

func handleProxy(w http.ResponseWriter, r *http.Request) {
	// Let's only handle GET and HEAD requests for caching
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		log.Printf("[%s] Method not allowed for caching proxy: %s", nodeID, r.Method)
		proxyToOriginDirect(w, r)
		return
	}

	cacheKey := r.URL.Path

	// 1. Check cache HIT
	if entry, hit := cdnCache.Get(cacheKey); hit {
		log.Printf("[%s] Cache HIT for key: %s", nodeID, cacheKey)

		// Serve from cache
		serveCachedEntry(w, r, entry)
		return
	}

	// 2. Cache MISS -> Fetch from Origin
	log.Printf("[%s] Cache MISS for key: %s", nodeID, cacheKey)
	fetchAndStoreFromOrigin(w, r, cacheKey)
}

func serveCachedEntry(w http.ResponseWriter, r *http.Request, entry *cache.CacheEntry) {
	// Set cached headers
	for k, vv := range entry.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}

	// Identify Cache node and Hit status
	w.Header().Set("X-Cache", "HIT")
	w.Header().Set("X-Edge-Node", nodeID)

	// Evaluate client-side conditional headers
	ifNoneMatch := r.Header.Get("If-None-Match")
	etag := entry.Header.Get("ETag")
	if ifNoneMatch != "" && (ifNoneMatch == etag || ifNoneMatch == "*") {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	ifModifiedSinceHeader := r.Header.Get("If-Modified-Since")
	lastModifiedHeader := entry.Header.Get("Last-Modified")
	if ifModifiedSinceHeader != "" && lastModifiedHeader != "" {
		if tClient, err1 := time.Parse(http.TimeFormat, ifModifiedSinceHeader); err1 == nil {
			if tMod, err2 := time.Parse(http.TimeFormat, lastModifiedHeader); err2 == nil {
				if !tMod.After(tClient) {
					w.WriteHeader(http.StatusNotModified)
					return
				}
			}
		}
	}

	w.WriteHeader(entry.StatusCode)
	if r.Method == http.MethodGet {
		w.Write(entry.Body)
	}
}

func fetchAndStoreFromOrigin(w http.ResponseWriter, r *http.Request, cacheKey string) {
	originRequestURL := fmt.Sprintf("%s%s", originURL, r.URL.Path)
	if r.URL.RawQuery != "" {
		originRequestURL = fmt.Sprintf("%s?%s", originRequestURL, r.URL.RawQuery)
	}

	log.Printf("[%s] Fetching from Origin: %s", nodeID, originRequestURL)

	req, err := http.NewRequest(r.Method, originRequestURL, nil)
	if err != nil {
		log.Printf("[%s] Failed to create origin request: %v", nodeID, err)
		http.Error(w, "Proxy Error", http.StatusInternalServerError)
		return
	}

	// Forward client headers to origin (except connection/keepalive headers)
	for k, vv := range r.Header {
		if k == "Connection" || k == "Keep-Alive" {
			continue
		}
		for _, v := range vv {
			req.Header.Add(k, v)
		}
	}

	client := http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("[%s] Error fetching from origin: %v", nodeID, err)
		http.Error(w, "Origin Unreachable", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Printf("[%s] Error reading origin response body: %v", nodeID, err)
		http.Error(w, "Origin Read Error", http.StatusInternalServerError)
		return
	}

	// Write response headers to client
	for k, vv := range resp.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}
	w.Header().Set("X-Cache", "MISS")
	w.Header().Set("X-Edge-Node", nodeID)

	w.WriteHeader(resp.StatusCode)
	if r.Method == http.MethodGet {
		w.Write(bodyBytes)
	}

	// Caching decision: only cache successful GET responses
	if r.Method == http.MethodGet && resp.StatusCode == http.StatusOK {
		ttl := parseCacheControl(resp.Header.Get("Cache-Control"))
		log.Printf("[%s] Caching key: %s with TTL: %v", nodeID, cacheKey, ttl)
		cdnCache.Set(cacheKey, resp.StatusCode, bodyBytes, resp.Header, ttl)
	}
}

func proxyToOriginDirect(w http.ResponseWriter, r *http.Request) {
	originRequestURL := fmt.Sprintf("%s%s", originURL, r.URL.Path)
	if r.URL.RawQuery != "" {
		originRequestURL = fmt.Sprintf("%s?%s", originRequestURL, r.URL.RawQuery)
	}

	req, err := http.NewRequest(r.Method, originRequestURL, r.Body)
	if err != nil {
		http.Error(w, "Proxy Error", http.StatusInternalServerError)
		return
	}

	for k, vv := range r.Header {
		for _, v := range vv {
			req.Header.Add(k, v)
		}
	}

	client := http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		http.Error(w, "Origin Unreachable", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	for k, vv := range resp.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func parseCacheControl(headerVal string) time.Duration {
	defaultTTL := 60 * time.Second // Default cache TTL if not defined

	if headerVal == "" {
		return defaultTTL
	}

	parts := strings.Split(headerVal, ",")
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if strings.HasPrefix(part, "max-age=") {
			secondsStr := strings.TrimPrefix(part, "max-age=")
			seconds, err := strconv.Atoi(secondsStr)
			if err == nil {
				return time.Duration(seconds) * time.Second
			}
		}
		if part == "no-cache" || part == "no-store" || part == "private" {
			return 0 // Do not cache
		}
	}

	return defaultTTL
}
