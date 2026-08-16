// demo_mock.js - Simulated preview of the Mini CDN Demo sequence

const GREEN = '\x1b[32m';
const BLUE = '\x1b[34m';
const YELLOW = '\x1b[33m';
const RED = '\x1b[31m';
const NC = '\x1b[0m'; // No Color

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function runDemo() {
    console.log(`${BLUE}======================================================================${NC}`);
    console.log(`${BLUE}             MINI CDN PROTOTYPE DEMO (CONSOLES SIMULATION)            ${NC}`);
    console.log(`${BLUE}======================================================================${NC}`);

    await sleep(1000);
    console.log(`\n${YELLOW}[1/6] Verifying all containers are healthy...${NC}`);
    console.log(`NAME                IMAGE               COMMAND             SERVICE             CREATED             STATUS              PORTS`);
    console.log(`control             mini-cdn-control    "/control"          control             10 seconds ago      Up 9 seconds        0.0.0.0:7000->7000/tcp`);
    console.log(`edge-1              mini-cdn-edge       "/edge"             edge-1              10 seconds ago      Up 9 seconds        0.0.0.0:8081->8080/tcp`);
    console.log(`edge-2              mini-cdn-edge       "/edge"             edge-2              10 seconds ago      Up 9 seconds        0.0.0.0:8082->8080/tcp`);
    console.log(`edge-3              mini-cdn-edge       "/edge"             edge-3              10 seconds ago      Up 9 seconds        0.0.0.0:8083->8080/tcp`);
    console.log(`origin              mini-cdn-origin     "/origin"           origin              10 seconds ago      Up 9 seconds        0.0.0.0:9000->9000/tcp`);
    console.log(`redis               redis:7-alpine      "docker-entrypoint.s…"   redis               10 seconds ago      Up 9 seconds        0.0.0.0:6379->6379/tcp`);
    console.log(`router              mini-cdn-router     "/router"           router              10 seconds ago      Up 9 seconds        0.0.0.0:8080->8080/tcp`);

    await sleep(2000);
    console.log(`\n${YELLOW}[2/6] Requesting logo.png (Expect: Cache MISS)...${NC}`);
    console.log(`${BLUE}> curl -i http://localhost:8080/assets/logo.png${NC}`);
    await sleep(800);
    console.log(`HTTP/1.1 200 OK`);
    console.log(`Content-Type: image/png`);
    console.log(`Cache-Control: public, max-age=3600`);
    console.log(`ETag: "a7681bc7e8293776cd64"`);
    console.log(`Last-Modified: Sun, 16 Aug 2026 18:00:00 GMT`);
    console.log(`Content-Length: 48102`);
    console.log(`${GREEN}X-Cache: MISS${NC}`);
    console.log(`${GREEN}X-Edge-Node: edge-1${NC}`);
    console.log(`${GREEN}✓ Success: Got Cache MISS as expected.${NC}`);

    await sleep(2000);
    console.log(`\n${YELLOW}[3/6] Requesting logo.png again (Expect: Cache HIT)...${NC}`);
    console.log(`${BLUE}> curl -i http://localhost:8080/assets/logo.png${NC}`);
    await sleep(200);
    console.log(`HTTP/1.1 200 OK`);
    console.log(`Content-Type: image/png`);
    console.log(`Cache-Control: public, max-age=3600`);
    console.log(`ETag: "a7681bc7e8293776cd64"`);
    console.log(`Last-Modified: Sun, 16 Aug 2026 18:00:00 GMT`);
    console.log(`Content-Length: 48102`);
    console.log(`${GREEN}X-Cache: HIT${NC}`);
    console.log(`${GREEN}X-Edge-Node: edge-1${NC}`);
    console.log(`${GREEN}✓ Success: Got Cache HIT as expected.${NC}`);
    console.log(`${BLUE}Currently cached on edge node: edge-1${NC}`);

    await sleep(2000);
    console.log(`\n${YELLOW}[4/6] Purging /assets/logo.png via Control Plane...${NC}`);
    console.log(`${BLUE}> curl -X POST http://localhost:7000/api/v1/purge -d '{"urls":["/assets/logo.png"]}'${NC}`);
    await sleep(500);
    console.log(`Control Plane response: {"status":"completed","details":{"edge-1":"success","edge-2":"success","edge-3":"success"}}`);

    await sleep(2000);
    console.log(`\n${YELLOW}[5/6] Requesting logo.png after purge (Expect: Cache MISS)...${NC}`);
    console.log(`${BLUE}> curl -i http://localhost:8080/assets/logo.png${NC}`);
    await sleep(800);
    console.log(`HTTP/1.1 200 OK`);
    console.log(`Content-Type: image/png`);
    console.log(`Cache-Control: public, max-age=3600`);
    console.log(`ETag: "a7681bc7e8293776cd64"`);
    console.log(`Last-Modified: Sun, 16 Aug 2026 18:00:00 GMT`);
    console.log(`Content-Length: 48102`);
    console.log(`${GREEN}X-Cache: MISS${NC}`);
    console.log(`${GREEN}X-Edge-Node: edge-1${NC}`);
    console.log(`${GREEN}✓ Success: Got Cache MISS after purge as expected.${NC}`);

    await sleep(2000);
    console.log(`\n${YELLOW}[6/6] Demonstrating automated failover...${NC}`);
    console.log(`${BLUE}Stopping container for serving node: edge-1...${NC}`);
    console.log(`${BLUE}> docker compose stop edge-1${NC}`);
    await sleep(1000);
    console.log(`Stopping edge-1 ... done`);
    console.log(`${YELLOW}Waiting 2 seconds for router to detect...${NC}`);
    await sleep(2000);
    console.log(`${YELLOW}Requesting logo.png again while edge-1 is down...${NC}`);
    console.log(`${BLUE}> curl -i http://localhost:8080/assets/logo.png${NC}`);
    await sleep(300);
    console.log(`HTTP/1.1 200 OK`);
    console.log(`Content-Type: image/png`);
    console.log(`Cache-Control: public, max-age=3600`);
    console.log(`ETag: "a7681bc7e8293776cd64"`);
    console.log(`Last-Modified: Sun, 16 Aug 2026 18:00:00 GMT`);
    console.log(`Content-Length: 48102`);
    console.log(`${GREEN}X-Cache: MISS${NC}`);
    console.log(`${GREEN}X-Edge-Node: edge-2${NC}`);
    console.log(`${GREEN}✓ Success: Failover occurred! Request routed to healthy node: edge-2${NC}`);

    await sleep(2000);
    console.log(`\n${YELLOW}Restarting stopped node edge-1 to restore cluster health...${NC}`);
    console.log(`${BLUE}> docker compose start edge-1${NC}`);
    await sleep(1000);
    console.log(`Starting edge-1 ... done`);
    console.log(`${GREEN}Restarted container edge-1.${NC}`);

    await sleep(1000);
    console.log(`\n${GREEN}======================================================================${NC}`);
    console.log(`${GREEN}                      DEMO COMPLETED SUCCESSFULLY                      ${NC}`);
    console.log(`${GREEN}======================================================================${NC}`);
}

runDemo();
