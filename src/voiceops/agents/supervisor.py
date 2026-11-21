
import re

from voiceops.agents.state import (
    AgentName,
    RequestIntent,
    VoiceOpsState,
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

    @staticmethod
    def _contains_keyword(
        text: str,
        keywords: set[str],
    ) -> bool:
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

        if self._contains_keyword(
            normalized_text,
            self.INVENTORY_KEYWORDS,
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

        # An order delay or delivery question requires shipment
        # investigation as well as order investigation.
        if has_shipment or has_order and any(
            keyword in normalized_text
            for keyword in ("delay", "delayed", "delivery", "tracking")
        ):
            selected_agents.append("shipment")

        if not selected_agents:
            return "unknown", []

        if len(selected_agents) > 1:
            return "mixed", selected_agents

        return selected_agents[0], selected_agents

    def run(
        self,
        state: VoiceOpsState,
    ) -> dict:
        """Return the Supervisor's state updates."""

        request_text = state.get("request_text", "")

        intent, selected_agents = self.classify_request(
            request_text
        )

        return {
            "intent": intent,
            "selected_agents": selected_agents,
        }
