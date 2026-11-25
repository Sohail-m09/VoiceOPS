
import re

from voiceops.agents.state import (
    AgentName,
    RequestIntent,
    VoiceOpsState,
    get_effective_request,
)


class SupervisorAgent:
    """Classifies requests and selects warehouse specialist agents."""

    INVENTORY_KEYWORDS = {
        "inventory",
        "stock",
        "quantity",
        "available",
        "availability",
        "warehouse",
        "product",
        "sku",
        "replenishment",
        "adjustment",
    }

    ORDER_KEYWORDS = {
        "order",
        "orders",
        "purchase",
        "purchased",
        "ord-",
    }

    SHIPMENT_KEYWORDS = {
        "shipment",
        "shipments",
        "shipping",
        "delivery",
        "deliveries",
        "delayed",
        "delay",
        "tracking",
        "dispatch",
        "transit",
        "dispatched",
        "shipped",
        "arrival",
    }

    KNOWLEDGE_KEYWORDS = {
        "sop",
        "procedure",
        "procedures",
        "policy",
        "policies",
        "guideline",
        "guidelines",
        "protocol",
        "protocols",
        "process",
        "processes",
        "work instruction",
        "standard operating procedure",
    }

    @staticmethod
    def _contains_keyword(text: str, keywords: set[str]) -> bool:
        """Check whether a request contains any configured keyword."""

        for keyword in keywords:
            if keyword.endswith("-"):
                if keyword in text:
                    return True
            else:
                pattern = rf"\b{re.escape(keyword)}\b"
                if re.search(pattern, text):
                    return True

        return False


    def classify_request(
        self,
        request_text: str,
    ) -> tuple[RequestIntent, list[AgentName]]:
        """Determine the request intent and required specialist agents."""

        normalized_text = request_text.lower().strip()

        if not normalized_text:
            return "unknown", []

        selected_agents: list[AgentName] = []

        has_knowledge = self._contains_keyword(
            normalized_text,
            self.KNOWLEDGE_KEYWORDS,
        )

        # Explicit operational actions should still select Inventory,
        # even when the same request also asks about an SOP.
        inventory_action_pattern = (
            r"\b(check|show|get|find|lookup|look up|"
            r"how many|calculate|verify)\b"
            r".{0,60}\b(inventory|stock|quantity|sku|product)\b"
        )

        has_inventory_action = bool(
            re.search(inventory_action_pattern, normalized_text)
        )

        has_inventory = self._contains_keyword(
            normalized_text,
            self.INVENTORY_KEYWORDS,
        )

        if has_inventory and (
            not has_knowledge or has_inventory_action
        ):
            selected_agents.append("inventory")

        has_order = self._contains_keyword(
            normalized_text,
            self.ORDER_KEYWORDS,
        )

        has_shipment = self._contains_keyword(
            normalized_text,
            self.SHIPMENT_KEYWORDS,
        )

        if has_order:
            selected_agents.append("order")

        if has_shipment or (
            has_order
            and any(
                keyword in normalized_text
                for keyword in ("delay", "delayed", "delivery", "tracking")
            )
        ):
            if "shipment" not in selected_agents:
                selected_agents.append("shipment")

        if has_knowledge:
            selected_agents.append("knowledge")

        if not selected_agents:
            return "unknown", []

        if len(selected_agents) > 1:
            return "mixed", selected_agents

        return selected_agents[0], selected_agents


    def run(self, state: VoiceOpsState) -> dict:
        """Return the Supervisor's state updates."""

        request_text = get_effective_request(state)

        intent, selected_agents = self.classify_request(
            request_text
        )

        return {
            "intent": intent,
            "selected_agents": selected_agents,
        }
