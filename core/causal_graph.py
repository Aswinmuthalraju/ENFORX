import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

class CausalNode:
    def __init__(self, node_id: str, node_type: str, content: Any, metadata: Dict[str, Any] = None):
        self.node_id = node_id
        self.node_type = node_type  # intent, reasoning, constraint, tool_call, data_source
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.parents: List[str] = []
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "content": str(self.content),
            "metadata": self.metadata,
            "parents": sorted(self.parents)
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "parents": self.parents,
            "hash": self.hash
        }

class CausalGraphEngine:
    """
    Constructs a Directed Acyclic Graph (DAG) representing the causal chain 
    of an agent's decision process.
    """
    def __init__(self):
        self.nodes: Dict[str, CausalNode] = {}

    def add_node(self, node_id: str, node_type: str, content: Any, 
                 parents: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        node = CausalNode(node_id, node_type, content, metadata)
        if parents:
            for parent_id in parents:
                if parent_id in self.nodes:
                    node.parents.append(parent_id)
        
        # Re-compute hash after adding parents
        node.hash = node._compute_hash()
        self.nodes[node_id] = node
        return node_id

    def get_graph(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "root_nodes": [nid for nid, node in self.nodes.items() if not node.parents],
            "leaf_nodes": [nid for nid, node in self.nodes.items() if nid not in 
                           [p for n in self.nodes.values() for p in n.parents]]
        }

    def verify_integrity(self) -> bool:
        """Verifies that all node hashes are valid based on content and parents."""
        for node in self.nodes.values():
            if node.hash != node._compute_hash():
                return False
        return True

    def export_mermaid(self) -> str:
        """Generates a Mermaid JS representation for visualization."""
        lines = ["graph TD"]
        for node in self.nodes.values():
            content_snippet = str(node.content)[:30].replace('"', "'") + "..."
            label = f"{node.node_id}[{node.node_type}: {content_snippet}]"
            lines.append(f"  {label}")
            for parent_id in node.parents:
                lines.append(f"  {parent_id} --> {node.node_id}")
        return "\n".join(lines)
