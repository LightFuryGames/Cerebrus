
from typing import Dict, Any
from . import ReportTab

class DeviceInfoTab(ReportTab):
    def __init__(self):
        super().__init__("Device Info", "device-info")
        
    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        html = ""
        metadata = context.get("metadata", {})
        active_cls = " active" if is_active else ""
        
        if not metadata:
             return f'<div id="{self.id}" class="tab-content{active_cls}"><div class="loading">No Device Info Found</div></div>'
             
        for k, v in metadata.items():
            html += f'<div class="stat-card"><div class="stat-label">{k}</div><div class="stat-value">{v}</div></div>'
        return f'<div id="{self.id}" class="tab-content{active_cls}"><div class="stats-grid">{html}</div></div>'
