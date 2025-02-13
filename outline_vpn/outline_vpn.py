"""
API wrapper for Outline VPN
"""

from dataclasses import dataclass

import requests

from outline_vpn.utils import check_ssl_fingerprint


@dataclass
class OutlineKey:
    """
    Describes a key in the Outline server
    """

    key_id: int
    name: str
    password: str
    port: int
    method: str
    access_url: str
    used_bytes: int


class OutlineServerErrorException(Exception):
    pass


class OutlineVPN:
    """
    An Outline VPN connection
    """

    def __init__(self, api_url: str, cert_sha256: str = None):
        self.api_url = api_url

        if cert_sha256:
            check_ssl_fingerprint(api_url, cert_sha256)

    def get_keys(self):
        """Get all keys in the outline server"""
        response = requests.get(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 200 and "accessKeys" in response.json():
            response_metrics = requests.get(
                f"{self.api_url}/metrics/transfer", verify=False
            )
            if (
                response_metrics.status_code >= 400
                or "bytesTransferredByUserId" not in response_metrics.json()
            ):
                raise OutlineServerErrorException("Unable to get metrics")

            response_json = response.json()
            result = []
            for key in response_json.get("accessKeys"):
                result.append(
                    OutlineKey(
                        key_id=key.get("id"),
                        name=key.get("name"),
                        password=key.get("password"),
                        port=key.get("port"),
                        method=key.get("method"),
                        access_url=key.get("accessUrl"),
                        used_bytes=response_metrics.json()
                        .get("bytesTransferredByUserId")
                        .get(key.get("id")),
                    )
                )
            return result
        raise OutlineServerErrorException("Unable to retrieve keys")

    def create_key(self, key_name=None) -> OutlineKey:
        """Create a new key"""
        response = requests.post(f"{self.api_url}/access-keys/", verify=False)
        if response.status_code == 201:
            key = response.json()
            outline_key = OutlineKey(
                key_id=key.get("id"),
                name=key.get("name"),
                password=key.get("password"),
                port=key.get("port"),
                method=key.get("method"),
                access_url=key.get("accessUrl"),
                used_bytes=0,
            )
            if key_name and self.rename_key(outline_key.key_id, key_name):
                outline_key.name = key_name
            return outline_key

        raise OutlineServerErrorException("Unable to create key")

    def delete_key(self, key_id: int) -> bool:
        """Delete a key"""
        response = requests.delete(f"{self.api_url}/access-keys/{key_id}", verify=False)
        return response.status_code == 204

    def rename_key(self, key_id: int, name: str):
        """Rename a key"""
        files = {
            "name": (None, name),
        }

        response = requests.put(
            f"{self.api_url}/access-keys/{key_id}/name", files=files, verify=False
        )
        return response.status_code == 204

    def add_data_limit(self, key_id: int, limit_bytes: int) -> bool:
        """Set data limit for a key (in bytes)"""
        data = {"limit": {"bytes": limit_bytes}}

        response = requests.put(
            f"{self.api_url}/access-keys/{key_id}/data-limit", json=data, verify=False
        )
        return response.status_code == 204

    def delete_data_limit(self, key_id: int) -> bool:
        """Removes data limit for a key"""
        response = requests.delete(
            f"{self.api_url}/access-keys/{key_id}/data-limit", verify=False
        )
        return response.status_code == 204

    def get_transferred_data(self):
        """Gets how much data all keys have used
        {
            "bytesTransferredByUserId": {
                "1":1008040941,
                "2":5958113497,
                "3":752221577
            }
        }"""
        response = requests.get(f"{self.api_url}/metrics/transfer", verify=False)
        if (
            response.status_code >= 400
            or "bytesTransferredByUserId" not in response.json()
        ):
            raise OutlineServerErrorException("Unable to get metrics")
        return response.json()

    def get_server_information(self):
        """Get information about the server
        {
            "name":"My Server",
            "serverId":"7fda0079-5317-4e5a-bb41-5a431dddae21",
            "metricsEnabled":true,
            "createdTimestampMs":1536613192052,
            "version":"1.0.0",
            "accessKeyDataLimit":{"bytes":8589934592},
            "portForNewAccessKeys":1234,
            "hostnameForAccessKeys":"example.com"
        }
        """
        response = requests.get(f"{self.api_url}/server", verify=False)
        if response.status_code != 200:
            raise OutlineServerErrorException("Unable to get information about the server")
        return response.json()

    def set_server_name(self, name: str) -> bool:
        """Renames the server"""
        data = {"name": name}
        response = requests.put(f"{self.api_url}/name", verify=False, json=data)
        return response.status_code == 204

    def set_hostname(self, hostname: str) -> bool:
        """Changes the hostname for access keys.
        Must be a valid hostname or IP address."""
        data = {"hostname": hostname}
        response = requests.put(f"{self.api_url}/server/hostname-for-access-keys", verify=False, json=data)
        return response.status_code == 204

    def get_metrics_status(self) -> bool:
        """Returns whether metrics is being shared"""
        response = requests.get(f"{self.api_url}/metrics/enabled", verify=False)
        return response.json().get("metricsEnabled")

    def set_metrics_status(self, status: bool) -> bool:
        """Enables or disables sharing of metrics"""
        data = {"metricsEnabled": status}
        response = requests.put(f"{self.api_url}/metrics/enabled", verify=False, json=data)
        return response.status_code == 204

    def set_port_new_for_access_keys(self, port: int) -> bool:
        """Changes the default port for newly created access keys.
        This can be a port already used for access keys."""
        data = {"port": port}
        response = requests.put(f"{self.api_url}/server/port-for-new-access-keys", verify=False, json=data)
        if response.status_code == 400:
            raise OutlineServerErrorException(
                "The requested port wasn't an integer from 1 through 65535, or the request had no port parameter.")
        elif response.status_code == 409:
            raise OutlineServerErrorException("The requested port was already in use by another service.")
        return response.status_code == 204

    def set_data_limit_for_all_keys(self, limit_bytes: int) -> bool:
        """Sets a data transfer limit for all access keys."""
        data = {"limit": {"bytes": limit_bytes}}
        response = requests.put(f"{self.api_url}/server/access-key-data-limit", verify=False, json=data)
        return response.status_code == 204

    def delete_data_limit_for_all_keys(self) -> bool:
        """Removes the access key data limit, lifting data transfer restrictions on all access keys."""
        response = requests.delete(f"{self.api_url}/server/access-key-data-limit", verify=False)
        return response.status_code == 204
