"""
Hostinger DNS API Client for TableTap Subdomain Provisioning.

Manages DNS records (CNAME/A) on Hostinger for custom restaurant slugs:
https://<slug>.tabletap.space -> TableTap Customer Menu Frontend.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class HostingerDNSClient:
    """Client for Hostinger DNS Zone Management API."""

    def __init__(self):
        self.api_token = getattr(settings, 'HOSTINGER_API_TOKEN', '')
        self.base_domain = getattr(settings, 'HOSTINGER_BASE_DOMAIN', 'tabletap.space')
        self.cname_target = getattr(settings, 'HOSTINGER_CNAME_TARGET', '8534e62137f12ea9.vercel-dns-017.com.')
        self.api_base = getattr(settings, 'HOSTINGER_API_BASE', 'https://developers.hostinger.com').rstrip('/')

    @property
    def is_configured(self) -> bool:
        """Returns True if the Hostinger API token is configured."""
        return bool(self.api_token and self.api_token.strip())

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_token.strip()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def sync_tenant_subdomain(self, new_slug: str, old_slug: str = None) -> dict:
        """
        Create or update a DNS CNAME record for the tenant's new slug.
        Optionally deletes the old subdomain CNAME if it changed.
        """
        clean_new_slug = (new_slug or '').lower().strip()
        clean_old_slug = (old_slug or '').lower().strip() if old_slug else None

        if not clean_new_slug:
            return {'success': False, 'error': 'New slug is required'}

        if not self.is_configured:
            logger.info(
                f"[Hostinger DNS] Mock Mode (no token): Subdomain '{clean_new_slug}.{self.base_domain}' -> '{self.cname_target}'."
            )
            return {
                'success': True,
                'mock': True,
                'domain': f"{clean_new_slug}.{self.base_domain}",
                'target': self.cname_target,
            }

        # 1. Create or update the new subdomain CNAME record
        create_res = self.add_or_update_cname(clean_new_slug, self.cname_target)
        if not create_res.get('success'):
            logger.error(f"[Hostinger DNS] Failed to provision {clean_new_slug}.{self.base_domain}: {create_res.get('error')}")
            return create_res

        # 2. If old slug exists and is different from new slug, delete old CNAME
        if clean_old_slug and clean_old_slug != clean_new_slug:
            try:
                self.delete_cname(clean_old_slug)
            except Exception as e:
                logger.warning(f"[Hostinger DNS] Could not delete old subdomain {clean_old_slug}: {e}")

        return {
            'success': True,
            'domain': f"{clean_new_slug}.{self.base_domain}",
            'target': self.cname_target,
        }

    def add_or_update_cname(self, subdomain: str, target: str, ttl: int = 14400) -> dict:
        """Add or update a CNAME record on Hostinger DNS zone."""
        if not self.is_configured:
            return {'success': True, 'mock': True}

        url = f"{self.api_base}/api/dns/v1/zones/{self.base_domain}"

        # Hostinger DNS API format: { "domain": "...", "overwrite": false, "zone": [...] }
        payload = {
            "overwrite": False,
            "zone": [
                {
                    "name": subdomain,
                    "type": "CNAME",
                    "records": [
                        {
                            "content": target
                        }
                    ],
                    "ttl": ttl,
                }
            ]
        }

        try:
            resp = requests.put(url, json=payload, headers=self._headers(), timeout=15)
            if resp.ok:
                logger.info(f"[Hostinger DNS] Successfully created/updated CNAME: {subdomain}.{self.base_domain} -> {target}")
                return {'success': True, 'response': resp.json() if resp.text else {}}

            error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
            logger.error(f"[Hostinger DNS] Error updating DNS zone: {error_msg}")
            return {'success': False, 'error': error_msg}
        except requests.RequestException as exc:
            logger.error(f"[Hostinger DNS] Network error: {exc}")
            return {'success': False, 'error': str(exc)}

    def delete_cname(self, subdomain: str) -> dict:
        """Delete a CNAME record from Hostinger DNS zone."""
        if not self.is_configured:
            return {'success': True, 'mock': True}

        url = f"{self.api_base}/api/dns/v1/zones/{self.base_domain}"
        payload = {
            "filters": [
                {
                    "name": subdomain,
                    "type": "CNAME",
                }
            ]
        }

        try:
            resp = requests.delete(url, json=payload, headers=self._headers(), timeout=15)
            if resp.ok:
                logger.info(f"[Hostinger DNS] Successfully removed CNAME: {subdomain}.{self.base_domain}")
                return {'success': True}
            return {'success': False, 'error': f"HTTP {resp.status_code}: {resp.text[:500]}"}
        except requests.RequestException as exc:
            logger.warning(f"[Hostinger DNS] Failed to delete CNAME {subdomain}: {exc}")
            return {'success': False, 'error': str(exc)}


# Singleton instance
hostinger_dns = HostingerDNSClient()
