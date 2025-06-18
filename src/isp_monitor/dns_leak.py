"""
DNS leak testing module for ISP Uptime Monitoring.
"""
import socket
import concurrent.futures
import logging
from typing import List, Dict, Set
import dns.resolver
import requests

logger = logging.getLogger(__name__)

class DNSLeakTester:
    """Class for performing DNS leak tests."""
    
    def __init__(self):
        self.dns_servers = set()
        self.test_domains = [
            "www.google.com",
            "www.cloudflare.com",
            "www.amazon.com",
            "www.microsoft.com",
            "www.facebook.com"
        ]
    
    def get_system_dns(self) -> List[str]:
        """Get the system's configured DNS servers."""
        try:
            resolver = dns.resolver.Resolver()
            return [str(server) for server in resolver.nameservers]
        except Exception as e:
            logger.error(f"Error getting system DNS: {e}")
            return []

    def resolve_domain(self, domain: str) -> Set[str]:
        """Resolve a domain and track which DNS servers were used."""
        servers = set()
        try:
            # Try to get the A record
            answers = dns.resolver.resolve(domain, 'A')
            for rdata in answers:
                servers.add(str(rdata))
            
            # Also get the authoritative nameservers
            ns_answers = dns.resolver.resolve(domain, 'NS')
            for rdata in ns_answers:
                servers.add(str(rdata))
        except Exception as e:
            logger.error(f"Error resolving {domain}: {e}")
        
        return servers

    def check_dns_leaks(self, progress_callback=None) -> Dict:
        """
        Perform a DNS leak test by resolving multiple domains and analyzing the DNS servers used.
        
        Returns:
            Dict containing:
            - configured_dns: List of configured DNS servers
            - detected_servers: List of all DNS servers detected during resolution
            - is_leaking: Boolean indicating if DNS leaks were detected
            - details: Additional information about the test
        """
        configured_dns = set(self.get_system_dns())
        detected_servers = set()
        
        # Use a thread pool to resolve domains concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_domain = {
                executor.submit(self.resolve_domain, domain): domain 
                for domain in self.test_domains
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_domain):
                domain = future_to_domain[future]
                try:
                    servers = future.result()
                    detected_servers.update(servers)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / len(self.test_domains) * 100)
                except Exception as e:
                    logger.error(f"Error testing domain {domain}: {e}")

        # Check if we're detecting servers outside our configured ones
        unexpected_servers = detected_servers - configured_dns
        is_leaking = len(unexpected_servers) > 0

        return {
            "configured_dns": list(configured_dns),
            "detected_servers": list(detected_servers),
            "unexpected_servers": list(unexpected_servers),
            "is_leaking": is_leaking,
            "details": {
                "domains_tested": len(self.test_domains),
                "total_servers_detected": len(detected_servers)
            }
        }

    def get_public_ip(self) -> str:
        """Get the public IP address."""
        try:
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            return response.json()['ip']
        except Exception as e:
            logger.error(f"Error getting public IP: {e}")
            return "Unknown" 