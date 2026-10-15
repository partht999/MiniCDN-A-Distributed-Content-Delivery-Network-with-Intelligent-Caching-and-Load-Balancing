# Public dashboard deployment

Target hostname: minicdn.jaynishthakar.tech, updated at the user's request on 10 October 2026. There is currently no hosting server, public IP or DNS change. The user has chosen Render Free; packaging for Render and linking its service to this hostname are pending. The VPS Compose configuration below remains an alternative, not an already published site. Earlier generated Phase IV documents use the previously proposed metrics subdomain; this hostname supersedes that proposal.

## Recommended path

A small Linux VPS running Docker Compose fits this project because its Go services, Redis, Prometheus and Grafana can share a private network on one host. Render can host services, but moving this whole multi-service Compose prototype there requires separate service/persistence/network configuration. For Phase IV, preserve the verified local setup and deploy after the local regression and experiment run, before the ESE rehearsal.

A 2 GiB VPS is a starting estimate for a light demonstration, not a measured memory guarantee. A 4 GiB server gives more room for builds, metrics and future projects. DigitalOcean's regular Basic plans currently list 2 GiB/1 vCPU at $12/month and 4 GiB/2 vCPU at $24/month, before extras and applicable taxes. Check the current quote before purchase. No server has been purchased or account created.

Source checked 10 October 2026: https://www.digitalocean.com/pricing/droplets

## Deployment checklist

1. Provision a Linux VPS and install Docker Engine with Compose using official instructions. Use SSH keys. Allow inbound 22 from your administration address and 80/443 for HTTPS.
2. Copy this repository to the server, excluding .env secrets and local runtime installers. Build from a tested commit. Record image digests after testing instead of indefinitely relying on floating latest tags.
3. For a VPS, create an A record named minicdn in the jaynishthakar.tech DNS zone pointing to the server's real public IPv4. Add AAAA only if IPv6 is configured and reachable. Keep other primary-domain records unchanged. Render will instead provide its own custom-domain DNS instructions after a service exists.
4. Copy deployment/.env.example to deployment/.env and set a unique Grafana password. Run from the repo root: `docker compose --env-file deployment/.env -f deployment/compose.production.yml config --quiet`, then `docker compose --env-file deployment/.env -f deployment/compose.production.yml up --build -d`.
5. Verify HTTPS at https://minicdn.jaynishthakar.tech, login, dashboard datasource, and scrape health. Caddy obtains a certificate when DNS reaches the VPS and required ports are reachable. The private services have no public published ports. The router's optional host port binds to localhost for SSH-based demos.
6. Create a Grafana Viewer account for group/evaluator access. Do not distribute the administrator password. Verify sign-up and anonymous access remain disabled. Grafana persistent credentials are initialized on first boot; changing an environment variable later does not necessarily reset an existing admin password.
7. Run a small content demo on the server, save a screenshot, record deployment date, DNS name, costs and versions. Verify rollback by restarting the previously tested images. Back up Redis and Grafana volumes separately from source code.

Keep public-host measurements separate from single-machine local experimental results. This deployment demonstrates public observability; it is not evidence of a global edge network.
