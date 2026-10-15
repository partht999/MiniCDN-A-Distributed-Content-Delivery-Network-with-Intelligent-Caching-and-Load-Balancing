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
	"sync"
	"time"

	"mini-cdn/pkg/cache"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	nodeID              = "edge-1"
	region              = "local"
	originURL           = "http://localhost:9000"
	controlURL          = "http://localhost:7000"
	port                = "8080"
	cdnCache            *cache.Cache
	cacheFills          fillGroup
	cacheOperations     sync.RWMutex
	purgeGeneration     int64
	coalescingEnabled         = true
	maxObjectBytes      int64 = 4 * 1024 * 1024
	originClient              = &http.Client{Timeout: 10 * time.Second}
	originRequestsTotal       = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "cdn_origin_requests_total",
		Help: "Origin HTTP attempts, including misses and bypasses.",
	}, []string{"node_id"})
	coalescedRequestsTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "cdn_coalesced_requests_total",
		Help: "Initial misses served from a cache filled by another request.",
	}, []string{"node_id"})

	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Number of HTTP requests processed by this edge node.",
		},
		[]string{"node_id", "path", "method", "status", "cache_status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "Latency of HTTP requests in seconds.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"node_id", "path", "method"},
	)
)

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (w *statusWriter) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}

func (w *statusWriter) Write(b []byte) (int, error) {
	if w.status == 0 {
		w.status = 200
	}
	return w.ResponseWriter.Write(b)
}

func metricsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}
		start := time.Now()
		sw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(sw, r)
		duration := time.Since(start).Seconds()

		// Get cache status (X-Cache header from response)
		cacheStatus := sw.Header().Get("X-Cache")
		if cacheStatus == "" {
			cacheStatus = "BYPASS"
		}

		path := r.URL.Path
		method := r.Method
		statusStr := strconv.Itoa(sw.status)

		httpRequestsTotal.WithLabelValues(nodeID, path, method, statusStr, cacheStatus).Inc()
		httpRequestDuration.WithLabelValues(nodeID, path, method).Observe(duration)
	})
}

type Node struct {
	ID     string `json:"id"`
	Host   string `json:"host"`
	Port   int    `json:"port"`
	Region string `json:"region"`
	Weight int    `json:"weight"`
}

type PurgeRequest struct {
	URLs       []string `json:"urls"`
	Prefixes   []string `json:"prefixes"`
	Generation int64    `json:"generation,omitempty"`
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

	capacity := int64(64 * 1024 * 1024)
	if value := os.Getenv("CACHE_MAX_BYTES"); value != "" {
		n, err := strconv.ParseInt(value, 10, 64)
		if err != nil || n <= 0 {
			log.Fatal("CACHE_MAX_BYTES must be positive")
		}
		capacity = n
	}
	if value := os.Getenv("CACHE_MAX_OBJECT_BYTES"); value != "" {
		n, err := strconv.ParseInt(value, 10, 64)
		if err != nil || n <= 0 {
			log.Fatal("CACHE_MAX_OBJECT_BYTES must be positive")
		}
		maxObjectBytes = n
	}
	cdnCache = cache.NewBoundedCache(capacity)
	prometheus.MustRegister(prometheus.NewGaugeFunc(prometheus.GaugeOpts{Name: "cache_body_bytes", Help: "Cached response-body bytes (metadata excluded).", ConstLabels: prometheus.Labels{"node_id": nodeID}}, func() float64 { n, _ := cdnCache.Usage(); return float64(n) }))
	prometheus.MustRegister(prometheus.NewGaugeFunc(prometheus.GaugeOpts{Name: "cache_evictions_total", Help: "Cumulative capacity evictions.", ConstLabels: prometheus.Labels{"node_id": nodeID}}, func() float64 { _, n := cdnCache.Usage(); return float64(n) }))
	coalescingEnabled = os.Getenv("COALESCING_ENABLED") != "false"

	// Register Prometheus metrics
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(originRequestsTotal, coalescedRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(prometheus.NewGaugeFunc(
		prometheus.GaugeOpts{
			Name:        "cache_size_items",
			Help:        "Number of active items in the local cache.",
			ConstLabels: prometheus.Labels{"node_id": nodeID},
		},
		func() float64 {
			if cdnCache != nil {
				return float64(cdnCache.Size())
			}
			return 0
		},
	))

	log.Printf("Starting Edge Node %s in region %s on port %s", nodeID, region, port)
	log.Printf("Origin URL: %s, Control URL: %s", originURL, controlURL)

	// Start Heartbeat registration background worker
	go startHeartbeat()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/internal/purge", handlePurge)
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/", handleProxy)

	if err := http.ListenAndServe(":"+port, metricsMiddleware(mux)); err != nil {
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
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		return
	}
	var acknowledgement struct {
		Generation int64 `json:"purge_generation"`
	}
	if json.NewDecoder(resp.Body).Decode(&acknowledgement) != nil {
		return
	}
	cacheOperations.Lock()
	if acknowledgement.Generation > purgeGeneration {
		cdnCache.Clear()
		purgeGeneration = acknowledgement.Generation
	}
	cacheOperations.Unlock()
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
	for _, prefix := range purgeReq.Prefixes {
		if !strings.HasPrefix(prefix, "/") {
			http.Error(w, "Prefixes must start with /", http.StatusBadRequest)
			return
		}
	}
	cacheOperations.Lock()
	defer cacheOperations.Unlock()
	// A skipped generation represents invalidations whose keys are unknown.
	if purgeReq.Generation > purgeGeneration+1 {
		cdnCache.Clear()
	}

	for _, url := range purgeReq.URLs {
		// Wait for an earlier fill before deleting, preventing that fill from
		// repopulating this exact key after purge acknowledgement.
		release, err := cacheFills.acquire(r.Context(), url)
		if err != nil {
			http.Error(w, "Purge canceled before completion", http.StatusRequestTimeout)
			return
		}
		log.Printf("[%s] Evicting from cache: %s", nodeID, url)
		cdnCache.Delete(url)
		release()
	}
	for _, prefix := range purgeReq.Prefixes {
		cdnCache.DeletePrefix(prefix)
	}
	if purgeReq.Generation > purgeGeneration {
		purgeGeneration = purgeReq.Generation
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "cleared"})
}

func handleProxy(w http.ResponseWriter, r *http.Request) {
	cacheOperations.RLock()
	defer cacheOperations.RUnlock()
	// Personalized, range, and explicit refresh requests bypass shared caching.
	if r.Header.Get("Authorization") != "" || r.Header.Get("Cookie") != "" ||
		r.Header.Get("Range") != "" || r.Header.Get("Cache-Control") != "" {
		w.Header().Set("X-Cache", "BYPASS")
		w.Header().Set("X-Edge-Node", nodeID)
		proxyToOriginDirect(w, r)
		return
	}
	// Let's only handle GET and HEAD requests for caching
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		log.Printf("[%s] Method not allowed for caching proxy: %s", nodeID, r.Method)
		proxyToOriginDirect(w, r)
		return
	}

	cacheKey := r.URL.Path
	if r.URL.RawQuery != "" {
		cacheKey = fmt.Sprintf("%s?%s", r.URL.Path, r.URL.RawQuery)
	}

	// 1. Check cache HIT
	if entry, hit := cdnCache.Get(cacheKey); hit {
		log.Printf("[%s] Cache HIT for key: %s", nodeID, cacheKey)

		// Serve from cache
		serveCachedEntry(w, r, entry)
		return
	}

	// 2. Cache MISS -> Fetch from Origin
	releaseFill := func() {}
	if r.Method == http.MethodGet && coalescingEnabled {
		release, err := cacheFills.acquire(r.Context(), cacheKey)
		if err != nil {
			return
		}
		defer release()
		releaseFill = release
		if entry, hit := cdnCache.Peek(cacheKey); hit {
			coalescedRequestsTotal.WithLabelValues(nodeID).Inc()
			serveCachedEntry(w, r, entry)
			return
		}
	}
	log.Printf("[%s] Cache MISS for key: %s", nodeID, cacheKey)
	fetchAndStoreFromOrigin(w, r, cacheKey, releaseFill)
}

func serveCachedEntry(w http.ResponseWriter, r *http.Request, entry *cache.CacheEntry) {
	serveCachedWithStatus(w, r, entry, "HIT")
}

func serveCachedWithStatus(w http.ResponseWriter, r *http.Request, entry *cache.CacheEntry, cacheStatus string) {
	// Set cached headers
	for k, vv := range entry.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}

	// Identify Cache node and Hit status
	w.Header().Set("X-Cache", cacheStatus)
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
	if ifNoneMatch == "" && ifModifiedSinceHeader != "" && lastModifiedHeader != "" {
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

func fetchAndStoreFromOrigin(w http.ResponseWriter, r *http.Request, cacheKey string, releaseFill func()) {
	originRequestURL := fmt.Sprintf("%s%s", originURL, r.URL.Path)
	if r.URL.RawQuery != "" {
		originRequestURL = fmt.Sprintf("%s?%s", originRequestURL, r.URL.RawQuery)
	}

	log.Printf("[%s] Fetching from Origin: %s", nodeID, originRequestURL)

	req, err := http.NewRequestWithContext(r.Context(), r.Method, originRequestURL, nil)
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

	stale, hasStale := cdnCache.Stale(cacheKey)
	if hasStale && r.Method == http.MethodGet {
		req.Header.Del("If-None-Match")
		req.Header.Del("If-Modified-Since")
		if etag := stale.Header.Get("ETag"); etag != "" {
			req.Header.Set("If-None-Match", etag)
		} else if modified := stale.Header.Get("Last-Modified"); modified != "" {
			req.Header.Set("If-Modified-Since", modified)
		}
	}
	originRequestsTotal.WithLabelValues(nodeID).Inc()
	resp, err := originClient.Do(req)
	if err != nil {
		log.Printf("[%s] Error fetching from origin: %v", nodeID, err)
		http.Error(w, "Origin Unreachable", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	if hasStale && r.Method == http.MethodGet && resp.StatusCode == http.StatusNotModified && (req.Header.Get("If-None-Match") != "" || req.Header.Get("If-Modified-Since") != "") {
		headers := stale.Header.Clone()
		for key, values := range resp.Header {
			headers[key] = append([]string(nil), values...)
		}
		entry := &cache.CacheEntry{StatusCode: stale.StatusCode, Body: stale.Body, Header: headers}
		cdnCache.Delete(cacheKey)
		if headers.Get("Vary") == "" && headers.Get("Set-Cookie") == "" {
			cdnCache.Set(cacheKey, entry.StatusCode, entry.Body, headers, parseCacheControl(headers.Get("Cache-Control")))
		}
		releaseFill()
		serveCachedWithStatus(w, r, entry, "REVALIDATED")
		return
	}

	bodyBytes, err := io.ReadAll(io.LimitReader(resp.Body, maxObjectBytes+1))
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

	// Caching decision: only cache successful GET responses with positive TTL
	if r.Method == http.MethodGet && resp.StatusCode == http.StatusOK &&
		int64(len(bodyBytes)) <= maxObjectBytes && resp.Header.Get("Vary") == "" && resp.Header.Get("Set-Cookie") == "" {
		ttl := parseCacheControl(resp.Header.Get("Cache-Control"))
		if ttl > 0 {
			log.Printf("[%s] Caching key: %s with TTL: %v", nodeID, cacheKey, ttl)
			cdnCache.Set(cacheKey, resp.StatusCode, bodyBytes, resp.Header, ttl)
		} else {
			cdnCache.Delete(cacheKey)
			log.Printf("[%s] Skipping cache for key: %s (TTL: %v)", nodeID, cacheKey, ttl)
		}
	} else if hasStale {
		cdnCache.Delete(cacheKey)
	}
	// Publish the fill before writing to a potentially slow client.
	releaseFill()
	w.WriteHeader(resp.StatusCode)
	if r.Method == http.MethodGet {
		w.Write(bodyBytes)
		if int64(len(bodyBytes)) > maxObjectBytes {
			io.Copy(w, resp.Body)
		}
	}
}

func proxyToOriginDirect(w http.ResponseWriter, r *http.Request) {
	originRequestURL := fmt.Sprintf("%s%s", originURL, r.URL.Path)
	if r.URL.RawQuery != "" {
		originRequestURL = fmt.Sprintf("%s?%s", originRequestURL, r.URL.RawQuery)
	}

	req, err := http.NewRequestWithContext(r.Context(), r.Method, originRequestURL, r.Body)
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
	originRequestsTotal.WithLabelValues(nodeID).Inc()
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
		directive := strings.ToLower(strings.TrimSpace(strings.SplitN(part, "=", 2)[0]))
		if directive == "no-cache" || directive == "no-store" || directive == "private" {
			return 0 // Do not cache
		}
	}

	for _, directive := range []string{"s-maxage", "max-age"} {
		for _, part := range parts {
			part = strings.TrimSpace(part)
			keyValue := strings.SplitN(part, "=", 2)
			if len(keyValue) == 2 && strings.EqualFold(strings.TrimSpace(keyValue[0]), directive) {
				secondsStr := strings.Trim(strings.TrimSpace(keyValue[1]), "\"")
				seconds, err := strconv.Atoi(secondsStr)
				if err == nil {
					if seconds <= 0 {
						return 0
					}
					return time.Duration(seconds) * time.Second
				}
			}
		}
	}

	return defaultTTL
}
