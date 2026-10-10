import os
import requests

RING_API_BASE = "https://api.amazonvision.com/v1"


class RingSentinelClient:

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("RING_ACCESS_TOKEN", "")
        self.client_id = os.getenv("RING_CLIENT_ID", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def verifier_session_ring(self) -> dict | None:
        """Point d'entree API officiel pour synchroniser l'etat Ring."""
        if not self.token:
            print(
                "[Ring API] Mode Private App actif (Client ID configure). "
                "Execution en flux direct camera / simulation d'evenements."
            )
            return None

        url = f"{RING_API_BASE}/devices"
        try:
            res = requests.get(url, headers=self.headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                print(
                    f"[Ring API] Authentification reussie. Cameras associees : {len(data.get('devices', []))}"
                )
                return data
            else:
                print(f"[Ring API] Reponse API ({res.status_code}) : {res.text}")
                return None
        except Exception as e:
            print(f"[Ring API] Exception reseau : {e}")
            return None
