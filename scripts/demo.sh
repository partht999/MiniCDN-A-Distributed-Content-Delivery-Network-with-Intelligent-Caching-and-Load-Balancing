#!/bin/bash
# demo.sh - End-to-end Mini CDN demonstration script

# Formatting colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}                    MINI CDN PROTOTYPE DEMO                           ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Check if services are running
echo -e "\n${YELLOW}[1/6] Verifying all containers are healthy...${NC}"
docker compose ps

# Test Cache MISS
echo -e "\n${YELLOW}[2/6] Requesting logo.png (Expect: Cache MISS)...${NC}"
response1=$(curl -i -s http://localhost:8080/assets/logo.png)
echo "$response1" | grep -E "HTTP/|X-Cache|X-Edge-Node"
if echo "$response1" | grep -q "X-Cache: MISS"; then
    echo -e "${GREEN}✓ Success: Got Cache MISS as expected.${NC}"
else
    echo -e "${RED}✗ Error: Did not get Cache MISS.${NC}"
fi

# Test Cache HIT
echo -e "\n${YELLOW}[3/6] Requesting logo.png again (Expect: Cache HIT)...${NC}"
response2=$(curl -i -s http://localhost:8080/assets/logo.png)
echo "$response2" | grep -E "HTTP/|X-Cache|X-Edge-Node"
if echo "$response2" | grep -q "X-Cache: HIT"; then
    echo -e "${GREEN}✓ Success: Got Cache HIT as expected.${NC}"
else
    echo -e "${RED}✗ Error: Did not get Cache HIT.${NC}"
fi

# Extract serving node ID
node_id=$(echo "$response2" | grep -Fi "X-Edge-Node:" | awk '{print $2}' | tr -d '\r\n')
echo -e "${BLUE}Currently cached on edge node: ${node_id}${NC}"

# Invalidate cache via Control Plane
echo -e "\n${YELLOW}[4/6] Purging /assets/logo.png via Control Plane...${NC}"
purge_res=$(curl -s -X POST http://localhost:7000/api/v1/purge \
     -H "Content-Type: application/json" \
     -d '{"urls":["/assets/logo.png"]}')
echo "Control Plane response: $purge_res"

# Test Cache MISS after purge
echo -e "\n${YELLOW}[5/6] Requesting logo.png after purge (Expect: Cache MISS)...${NC}"
response3=$(curl -i -s http://localhost:8080/assets/logo.png)
echo "$response3" | grep -E "HTTP/|X-Cache|X-Edge-Node"
if echo "$response3" | grep -q "X-Cache: MISS"; then
    echo -e "${GREEN}✓ Success: Got Cache MISS after purge as expected.${NC}"
else
    echo -e "${RED}✗ Error: Did not get Cache MISS after purge.${NC}"
fi

# Test Failover Capability
echo -e "\n${YELLOW}[6/6] Demonstrating automated failover...${NC}"
# Determine which node is currently serving a request for logo.png
fresh_node=$(curl -i -s http://localhost:8080/assets/logo.png | grep -Fi "X-Edge-Node:" | awk '{print $2}' | tr -d '\r\n')

if [ -z "$fresh_node" ]; then
    fresh_node="edge-1"
fi
echo -e "${BLUE}Stopping container for serving node: ${fresh_node}...${NC}"
docker compose stop "$fresh_node"

echo -e "${YELLOW}Waiting 2 seconds for router to detect...${NC}"
sleep 2

echo -e "${YELLOW}Requesting logo.png again while ${fresh_node} is down...${NC}"
response_failover=$(curl -i -s http://localhost:8080/assets/logo.png)
echo "$response_failover" | grep -E "HTTP/|X-Cache|X-Edge-Node"

failover_node=$(echo "$response_failover" | grep -Fi "X-Edge-Node:" | awk '{print $2}' | tr -d '\r\n')

if [ -n "$failover_node" ] && [ "$failover_node" != "$fresh_node" ]; then
    echo -e "${GREEN}✓ Success: Failover occurred! Request routed to healthy node: ${failover_node}${NC}"
else
    echo -e "${RED}✗ Error: Failover failed or routed to same node.${NC}"
fi

echo -e "\n${YELLOW}Restarting stopped node ${fresh_node} to restore cluster health...${NC}"
docker compose start "$fresh_node"
echo -e "${GREEN}Restarted container ${fresh_node}.${NC}"

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}                      DEMO COMPLETED SUCCESSFULLY                      ${NC}"
echo -e "${GREEN}======================================================================${NC}"
