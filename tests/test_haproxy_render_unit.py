import importlib.util
import unittest
from pathlib import Path


def _load_renderer_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "ops" / "render_haproxy_cfg.py"
    spec = importlib.util.spec_from_file_location("render_haproxy_cfg", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HAProxyRenderUnitTests(unittest.TestCase):
    def test_backend_servers_render_with_check(self):
        renderer = _load_renderer_module()
        nodes = [
            {"id": 1, "name": "DE-1", "backend_host": "10.10.0.11", "backend_port": 29940, "backend_weight": 120},
            {"id": 2, "name": "Node West", "backend_host": "10.10.0.12", "backend_port": 29940, "backend_weight": 80},
        ]

        backend_block = renderer._render_backend_servers(nodes)

        self.assertIn("server node_1_de-1 10.10.0.11:29940 check weight 120", backend_block)
        self.assertIn("server node_2_node-west 10.10.0.12:29940 check weight 80", backend_block)

    def test_full_config_contains_tcp_and_leastconn_with_servers(self):
        renderer = _load_renderer_module()
        repo_root = Path(__file__).resolve().parents[1]
        template_path = repo_root / "ops" / "haproxy" / "haproxy.cfg.tpl"
        nodes = [
            {"id": 7, "name": "cluster-a", "backend_host": "172.16.0.7", "backend_port": 29940, "backend_weight": 100}
        ]
        backend_servers = renderer._render_backend_servers(nodes)

        cfg = renderer._render_config(
            template_path=template_path,
            frontend_bind_addr="0.0.0.0",
            frontend_port=29940,
            backend_servers=backend_servers,
        )

        self.assertIn("mode tcp", cfg)
        self.assertIn("balance leastconn", cfg)
        self.assertIn("option clitcpka", cfg)
        self.assertIn("option srvtcpka", cfg)
        self.assertIn("timeout client 4h", cfg)
        self.assertIn("timeout server 4h", cfg)
        self.assertIn("default-server inter 3s rise 2 fall 3 slowstart 60s", cfg)
        self.assertIn("server node_7_cluster-a 172.16.0.7:29940 check weight 100", cfg)

    def test_empty_nodes_render_disabled_placeholder_server(self):
        renderer = _load_renderer_module()
        backend_block = renderer._render_backend_servers([])
        self.assertIn("server cluster_empty 127.0.0.1:65535 disabled", backend_block)

    def test_backend_servers_render_with_send_proxy_when_enabled(self):
        renderer = _load_renderer_module()
        nodes = [
            {"id": 1, "name": "DE-1", "backend_host": "10.10.0.11", "backend_port": 29940, "backend_weight": 120},
        ]

        backend_block = renderer._render_backend_servers(nodes, send_proxy=True)

        self.assertIn("server node_1_de-1 10.10.0.11:29940 check weight 120 send-proxy", backend_block)

    def test_reality_filter_keeps_majority_signature_group(self):
        renderer = _load_renderer_module()
        nodes = [
            {
                "id": 1,
                "name": "old-node",
                "backend_host": "10.10.0.11",
                "backend_port": 29940,
                "backend_weight": 100,
                "last_reality_public_key": "old-key",
                "last_reality_short_id": "aaaa",
                "last_reality_sni": "old.example.com",
                "last_reality_fingerprint": "chrome",
            },
            {
                "id": 2,
                "name": "new-node-a",
                "backend_host": "10.10.0.12",
                "backend_port": 29940,
                "backend_weight": 100,
                "last_reality_public_key": "new-key",
                "last_reality_short_id": "bbbb",
                "last_reality_sni": "www.cloudflare.com",
                "last_reality_fingerprint": "chrome",
            },
            {
                "id": 3,
                "name": "new-node-b",
                "backend_host": "10.10.0.13",
                "backend_port": 29940,
                "backend_weight": 100,
                "last_reality_public_key": "new-key",
                "last_reality_short_id": "bbbb",
                "last_reality_sni": "www.cloudflare.com",
                "last_reality_fingerprint": "chrome",
            },
        ]

        filtered = renderer._filter_nodes_with_matching_reality(nodes)

        self.assertEqual([node["id"] for node in filtered], [2, 3])


if __name__ == "__main__":
    unittest.main()
