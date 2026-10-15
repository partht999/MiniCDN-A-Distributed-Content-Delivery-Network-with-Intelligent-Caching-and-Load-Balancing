package main

import (
	"mini-cdn/pkg/hash"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"
)

func testNode(t *testing.T, id, address string) Node {
	t.Helper()
	parsed, _ := url.Parse(address)
	host, port, err := net.SplitHostPort(parsed.Host)
	if err != nil {
		t.Fatal(err)
	}
	number, _ := strconv.Atoi(port)
	return Node{ID: id, Host: host, Port: number}
}

func testRoutingState(t *testing.T, nodes map[string]Node) string {
	t.Helper()
	oldRing, oldNodes, oldHealth, oldMode := hashRing, nodesMap, healthyNodes, routingMode
	t.Cleanup(func() { hashRing, nodesMap, healthyNodes, routingMode = oldRing, oldNodes, oldHealth, oldMode })
	hashRing = hash.NewRing(50)
	hashRing.SetNodes([]string{"first", "second"})
	nodesMap = nodes
	healthyNodes = map[string]bool{"first": true, "second": true}
	routingMode = "consistent_hash"
	for i := 0; i < 1000; i++ {
		path := "/test-" + strconv.Itoa(i)
		if hashRing.GetCandidates(path)[0] == "first" {
			return path
		}
	}
	t.Fatal("could not locate first owner's key")
	return ""
}

func TestRouterConnectionFailureFallsBack(t *testing.T) {
	dead := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	deadAddress := dead.URL
	dead.Close()
	live := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Edge-Node", "second")
		w.Write([]byte("content"))
	}))
	defer live.Close()
	path := testRoutingState(t, map[string]Node{"first": testNode(t, "first", deadAddress), "second": testNode(t, "second", live.URL)})
	rec := httptest.NewRecorder()
	handleRoute(rec, httptest.NewRequest("GET", path, nil))
	if rec.Code != 200 || rec.Body.String() != "content" || healthyNodes["first"] {
		t.Fatal("failed connection did not fall back")
	}
	if routeSelector.load("first") != 0 || routeSelector.load("second") != 0 {
		t.Fatal("fallback reservation leaked")
	}
}

func TestRouterDoesNotAppendAnotherResponseAfterPartialBody(t *testing.T) {
	first := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Length", "100")
		w.Write([]byte("partial"))
	}))
	defer first.Close()
	secondCalls := 0
	second := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { secondCalls++; w.Write([]byte("unexpected")) }))
	defer second.Close()
	path := testRoutingState(t, map[string]Node{"first": testNode(t, "first", first.URL), "second": testNode(t, "second", second.URL)})
	rec := httptest.NewRecorder()
	handleRoute(rec, httptest.NewRequest("GET", path, nil))
	if rec.Body.String() != "partial" || secondCalls != 0 {
		t.Fatal("fallback corrupted a committed response")
	}
}
