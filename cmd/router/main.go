package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"

	"mini-cdn/pkg/hash"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type Node struct {
	ID     string `json:"id"`
	Host   string `json:"host"`
	Port   int    `json:"port"`
	Region string `json:"region"`
	Weight int    `json:"weight"`
}

var (
	controlURL    = "http://localhost:7000"
	port          = "8080"
	routingMode   = "consistent_hash"
	adaptiveSlack = 2
	routeSelector selector
	proxyClient   = &http.Client{Timeout: 12 * time.Second, Transport: &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           (&net.Dialer{Timeout: 500 * time.Millisecond, KeepAlive: 30 * time.Second}).DialContext,
		ResponseHeaderTimeout: 1500 * time.Millisecond,
		MaxIdleConns:          256, MaxIdleConnsPerHost: 64, IdleConnTimeout: 90 * time.Second,
	}}
	hashRing     *hash.Ring
	nodesMap     = make(map[string]Node)
	healthyNodes = make(map[string]bool)
	nodesMu      sync.RWMutex

	routerRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "router_requests_total",
			Help: "Number of requests routed by the smart router.",
		},
		[]string{"path", "method", "status", "target_node", "routing_mode"},
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
		sw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(sw, r)

		targetNode := sw.Header().Get("X-Edge-Node")
		if targetNode == "" {
			targetNode = "none"
		}

		path := r.URL.Path
		method := r.Method
		statusStr := strconv.Itoa(sw.status)

		routerRequestsTotal.WithLabelValues(path, method, statusStr, targetNode, routingMode).Inc()
	})
}

func main() {
	if mode := os.Getenv("ROUTING_MODE"); mode != "" {
		routingMode = mode
	}
	if routingMode != "consistent_hash" && routingMode != "round_robin" && routingMode != "adaptive" {
		log.Fatal("ROUTING_MODE must be consistent_hash, round_robin or adaptive")
	}
	if value := os.Getenv("ADAPTIVE_SLACK"); value != "" {
		n, err := strconv.Atoi(value)
		if err != nil || n < 0 {
			log.Fatal("ADAPTIVE_SLACK must be nonnegative")
		}
		adaptiveSlack = n
	}
	if ctrl := os.Getenv("CONTROL_URL"); ctrl != "" {
		controlURL = ctrl
	}
	if p := os.Getenv("PORT"); p != "" {
		port = p
	}

	// Initialize Consistent Hash Ring with 50 virtual nodes per physical node
	hashRing = hash.NewRing(50)

	// Register Prometheus metrics
	prometheus.MustRegister(routerRequestsTotal)
	prometheus.MustRegister(&routeSelector)
	prometheus.MustRegister(prometheus.NewGaugeFunc(
		prometheus.GaugeOpts{
			Name: "router_active_nodes",
			Help: "Number of active healthy edge nodes currently registered in the hash ring.",
		},
		func() float64 {
			nodesMu.RLock()
			defer nodesMu.RUnlock()
			count := 0
			for _, healthy := range healthyNodes {
				if healthy {
					count++
				}
			}
			return float64(count)
		},
	))

	log.Printf("Starting Smart Router on port %s", port)
	log.Printf("Control Plane URL: %s", controlURL)

	// Start background node sync and health checking worker
	go startDiscoveryAndHealthChecks()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "routing_mode": routingMode})
	})
	mux.HandleFunc("/", handleRoute)
	mux.Handle("/metrics", promhttp.Handler())

	if err := http.ListenAndServe(":"+port, metricsMiddleware(mux)); err != nil {
		log.Fatalf("Router failed to start: %v", err)
	}
}

func startDiscoveryAndHealthChecks() {
	// Sync and check health immediately, then every 4 seconds
	for {
		syncNodesAndCheckHealth()
		time.Sleep(time.Second)
	}
}

func syncNodesAndCheckHealth() {
	// 1. Fetch nodes from control plane registry
	nodesURL := fmt.Sprintf("%s/api/v1/nodes", controlURL)
	client := http.Client{Timeout: time.Second}
	resp, err := client.Get(nodesURL)
	if err != nil {
		log.Printf("Discovery error: failed to fetch nodes from control plane: %v", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return
	}

	var nodes []Node
	if err := json.NewDecoder(resp.Body).Decode(&nodes); err != nil {
		log.Printf("Discovery error: failed to decode nodes: %v", err)
		return
	}

	// Track newly discovered nodes and update configuration
	newNodesMap := make(map[string]Node)
	for _, n := range nodes {
		newNodesMap[n.ID] = n
	}
	newHealthy := make(map[string]bool)

	// 2. Perform direct health checks on each node
	var activeNodeIDs []string
	var checkMu sync.Mutex
	var checks sync.WaitGroup
	for id, node := range newNodesMap {
		checks.Add(1)
		go func(id string, node Node) {
			defer checks.Done()
			healthURL := fmt.Sprintf("http://%s:%d/health", node.Host, node.Port)
			hResp, hErr := client.Get(healthURL)
			if hErr == nil && hResp.StatusCode == http.StatusOK {
				hResp.Body.Close()
				checkMu.Lock()
				newHealthy[id] = true
				activeNodeIDs = append(activeNodeIDs, id)
				checkMu.Unlock()
				log.Printf("Node %s is HEALTHY", id)
			} else {
				if hErr == nil {
					hResp.Body.Close()
				}
				log.Printf("Node %s is UNHEALTHY or unreachable: %v", id, hErr)
			}
		}(id, node)
	}
	checks.Wait()
	sort.Strings(activeNodeIDs)
	nodesMu.Lock()
	defer nodesMu.Unlock()
	nodesMap = newNodesMap
	healthyNodes = newHealthy

	// 3. Rebuild consistent hash ring with healthy nodes only
	hashRing.SetNodes(activeNodeIDs)
}

func handleRoute(w http.ResponseWriter, r *http.Request) {
	log.Printf("Router received request: %s %s", r.Method, r.URL.Path)

	nodesMu.RLock()
	candidates := hashRing.GetCandidates(r.URL.RequestURI())
	available := make(map[string]Node)
	filtered := candidates[:0]
	for _, id := range candidates {
		if healthyNodes[id] {
			available[id] = nodesMap[id]
			filtered = append(filtered, id)
		}
	}
	nodesMu.RUnlock()
	candidates, release := routeSelector.reserve(routingMode, filtered, adaptiveSlack)
	defer release()

	if len(candidates) == 0 {
		log.Println("Router warning: no healthy edge nodes available in the hash ring")
		http.Error(w, "Service Unavailable (No healthy edge nodes)", http.StatusServiceUnavailable)
		return
	}

	var success bool
	for index, nodeID := range candidates {
		attemptRelease := release
		if index > 0 {
			_, attemptRelease = routeSelector.reserve("consistent_hash", []string{nodeID}, 0)
		}
		// Verify node is healthy and exists
		node, ok := available[nodeID]
		if !ok {
			continue
		}

		w.Header().Set("X-Routing-Mode", routingMode)
		err := proxyToNode(w, r, node)
		attemptRelease()
		if err == nil {
			success = true
			break
		}

		log.Printf("Router error: failed to proxy to node %s: %v. Trying next node on hash ring...", nodeID, err)
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			break
		}
		// Mark node unhealthy locally immediately so next requests bypass it before the next cron poll
		nodesMu.Lock()
		healthyNodes[nodeID] = false
		nodesMu.Unlock()
	}

	if !success {
		log.Println("Router error: all edge nodes failed to respond")
		http.Error(w, "Bad Gateway (All edge nodes failed to respond)", http.StatusBadGateway)
	}
}

func proxyToNode(w http.ResponseWriter, r *http.Request, node Node) error {
	destURL := fmt.Sprintf("http://%s:%d%s", node.Host, node.Port, r.URL.Path)
	if r.URL.RawQuery != "" {
		destURL = fmt.Sprintf("%s?%s", destURL, r.URL.RawQuery)
	}

	req, err := http.NewRequestWithContext(r.Context(), r.Method, destURL, r.Body)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Copy client headers
	for k, vv := range r.Header {
		for _, v := range vv {
			req.Header.Add(k, v)
		}
	}

	// Use short timeout for proxying to enable quick failover
	resp, err := proxyClient.Do(req)
	if err != nil {
		return fmt.Errorf("connection error: %w", err)
	}
	defer resp.Body.Close()

	// Copy response headers back to client
	for k, vv := range resp.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}

	w.WriteHeader(resp.StatusCode)
	// Once headers are committed, a second edge response must never be
	// appended to a partial body. Failover applies only before commitment.
	_, copyErr := io.Copy(w, resp.Body)
	if copyErr != nil {
		log.Printf("response stream interrupted: %v", copyErr)
	}
	return nil
}
