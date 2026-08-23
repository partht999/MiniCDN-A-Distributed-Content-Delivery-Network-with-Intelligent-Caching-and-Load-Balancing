package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
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
	controlURL   = "http://localhost:7000"
	port         = "8080"
	hashRing     *hash.Ring
	nodesMap     = make(map[string]Node)
	healthyNodes = make(map[string]bool)
	nodesMu      sync.RWMutex

	routerRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "router_requests_total",
			Help: "Number of requests routed by the smart router.",
		},
		[]string{"path", "method", "status", "target_node"},
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

		routerRequestsTotal.WithLabelValues(path, method, statusStr, targetNode).Inc()
	})
}

func main() {
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
		time.Sleep(4 * time.Second)
	}
}

func syncNodesAndCheckHealth() {
	// 1. Fetch nodes from control plane registry
	nodesURL := fmt.Sprintf("%s/api/v1/nodes", controlURL)
	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(nodesURL)
	if err != nil {
		log.Printf("Discovery error: failed to fetch nodes from control plane: %v", err)
		return
	}
	defer resp.Body.Close()

	var nodes []Node
	if err := json.NewDecoder(resp.Body).Decode(&nodes); err != nil {
		log.Printf("Discovery error: failed to decode nodes: %v", err)
		return
	}

	nodesMu.Lock()
	defer nodesMu.Unlock()

	// Track newly discovered nodes and update configuration
	newNodesMap := make(map[string]Node)
	for _, n := range nodes {
		newNodesMap[n.ID] = n
	}
	nodesMap = newNodesMap

	// 2. Perform direct health checks on each node
	var activeNodeIDs []string
	for id, node := range nodesMap {
		healthURL := fmt.Sprintf("http://%s:%d/health", node.Host, node.Port)
		hResp, hErr := client.Get(healthURL)
		if hErr == nil && hResp.StatusCode == http.StatusOK {
			hResp.Body.Close()
			healthyNodes[id] = true
			activeNodeIDs = append(activeNodeIDs, id)
			log.Printf("Node %s is HEALTHY", id)
		} else {
			if hErr == nil {
				hResp.Body.Close()
			}
			healthyNodes[id] = false
			log.Printf("Node %s is UNHEALTHY or unreachable: %v", id, hErr)
		}
	}

	// 3. Rebuild consistent hash ring with healthy nodes only
	hashRing.SetNodes(activeNodeIDs)
}

func handleRoute(w http.ResponseWriter, r *http.Request) {
	log.Printf("Router received request: %s %s", r.Method, r.URL.Path)

	hashKey := r.URL.Path
	candidates := hashRing.GetCandidates(hashKey)

	if len(candidates) == 0 {
		log.Println("Router warning: no healthy edge nodes available in the hash ring")
		http.Error(w, "Service Unavailable (No healthy edge nodes)", http.StatusServiceUnavailable)
		return
	}

	nodesMu.RLock()
	defer nodesMu.RUnlock()

	var success bool
	for _, nodeID := range candidates {
		// Verify node is healthy and exists
		if !healthyNodes[nodeID] {
			continue
		}
		node, ok := nodesMap[nodeID]
		if !ok {
			continue
		}

		log.Printf("Routing request %s to node %s", r.URL.Path, nodeID)
		err := proxyToNode(w, r, node)
		if err == nil {
			success = true
			break
		}

		log.Printf("Router error: failed to proxy to node %s: %v. Trying next node on hash ring...", nodeID, err)
		// Mark node unhealthy locally immediately so next requests bypass it before the next cron poll
		nodesMu.RUnlock()
		nodesMu.Lock()
		healthyNodes[nodeID] = false
		nodesMu.Unlock()
		nodesMu.RLock()
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

	req, err := http.NewRequest(r.Method, destURL, r.Body)
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
	client := http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
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
	_, err = io.Copy(w, resp.Body)
	return err
}
