"""Translate public SFC service labels to Tekton's VNF types and templates."""


_SERVICE_TEMPLATES = {
    "attack": ("firewall", "vnf-firewall.yaml"),
    "firewall": ("firewall", "vnf-firewall.yaml"),
    "idps": ("idps", "vnf-idps.yaml"),
    "nat": ("nat", "vnf-nat.yaml"),
    "lb": ("lb", "vnf-lb.yaml"),
    "voc": ("voc", "vnf-voc.yaml"),
    "frr": ("router", "vnf-frr.yaml"),
    "router": ("router", "vnf-frr.yaml"),
    "video": ("router", "vnf-frr.yaml"),
    "data": ("router", "vnf-frr.yaml"),
}


def resolve_vnf_service(service_type):
    """Return ``(Tekton vnf_type, manifest filename)`` deterministically."""
    if not isinstance(service_type, str) or not service_type.strip():
        return _SERVICE_TEMPLATES["data"]
    return _SERVICE_TEMPLATES.get(service_type.strip().lower(), _SERVICE_TEMPLATES["data"])
