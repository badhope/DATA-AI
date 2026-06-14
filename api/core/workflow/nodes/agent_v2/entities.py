from typing import Literal

from pydantic import model_validator

from graphon.entities.base_node_data import BaseNodeData
from graphon.enums import BuiltinNodeTypes, NodeType


class DATAAgentNodeData(BaseNodeData):
    type: NodeType = BuiltinNodeTypes.AGENT
    agent_node_kind: Literal["data_agent"] = "data_agent"

    @model_validator(mode="after")
    def validate_version(self) -> "DATAAgentNodeData":
        if self.version != "2":
            raise ValueError("DATA Agent Node v2 requires version='2'")
        return self
