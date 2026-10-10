import json, copy
from pathlib import Path
file = Path(__file__).resolve().parents[1] / 'configs/grafana/provisioning/dashboards/minicdn_dashboard.json'
dashboard = json.loads(file.read_text())
for panel in dashboard['panels']:
    if panel['id'] == 2:
        panel['targets'][0]['expr'] = 'max(router_active_nodes)'
        panel['description'] = 'Healthy edge count (maximum across policy routers, not their sum).'
dashboard['panels'] = [p for p in dashboard['panels'] if p['id'] < 10]
base = next(p for p in dashboard['panels'] if p['id'] == 4)
bottom = max(p['gridPos']['y'] + p['gridPos']['h'] for p in dashboard['panels'])
for index, (title, expression, unit, legend) in enumerate([
    ('Cached response-body bytes', 'cache_body_bytes{job="mini-cdn-edges"}', 'bytes', '{{node_id}}'),
    ('Capacity evictions per second', 'rate(cache_evictions_total{job="mini-cdn-edges"}[1m])', 'ops', '{{node_id}}'),
    ('Routing policy requests per second', 'sum by (routing_mode) (rate(router_requests_total{path!~"/health|/metrics"}[1m]))', 'reqps', '{{routing_mode}}'),
    ('Router in-flight requests per edge', 'router_inflight_requests{job="mini-cdn-router"}', 'short', '{{instance}} / {{node_id}}')
]):
    panel = copy.deepcopy(base)
    panel['id'] = 10 + index; panel['title'] = title
    panel['gridPos'] = {'x':(index%2)*12,'y':bottom+(index//2)*8,'w':12,'h':8}
    panel['targets'] = [dict(base['targets'][0], expr=expression, legendFormat=legend)]
    panel.setdefault('fieldConfig', {}).setdefault('defaults', {})['unit'] = unit
    dashboard['panels'].append(panel)
dashboard['version'] = dashboard.get('version', 1) + 1
file.write_text(json.dumps(dashboard, indent=2)+'\n')
print('Dashboard panels:',len(dashboard['panels']))
