import csv
import functools # Importazione necessaria per la cache
import ipaddress
import duckdb
from pathlib import Path
from typing import Optional, Dict


class NetworkFinder:
    """
    A class to search for network information based on IP addresses.

    This class reads network data from a CSV file and provides methods to find
    which network range an IP address belongs to.
    """

    def __init__(self, csv_file_path: str = "data/networks/networks_converted.csv"):
        """
        Initialize the NetworkFinder with the path to the networks CSV file.

        Args:
            csv_file_path: Path to the CSV file containing network data.
                          Default is "data/networks/networks_converted.csv"
        """
        self.csv_file_path = Path(csv_file_path)
        self.conn = duckdb.connect(':memory:')

        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        # Registrazione della sorgente dati come VIEW
        self.conn.sql(f"""
            CREATE OR REPLACE VIEW network_ranges AS
            SELECT network, min_ip, max_ip, asn, organization, country, max_ip - min_ip AS range_size
            FROM read_csv_auto('{self.csv_file_path}', types={{'min_ip': 'HUGEINT', 'max_ip': 'HUGEINT'}})
        """)

        # Inizializza un Lock per l'accesso Thread-Safe alla connessione
        # Questo è VITALE se la UDF viene eseguita in parallelo.
        import threading
        self.lock = threading.Lock()

    def ip_to_int(self, ip_address: str) -> int:
        """
        Convert an IP address string to an integer.

        Args:
            ip_address: IP address in string format (e.g., "1.2.3.4")

        Returns:
            Integer representation of the IP address

        Raises:
            ValueError: If the IP address is invalid
        """
        try:
            return int(ipaddress.IPv4Address(ip_address))
        except (ipaddress.AddressValueError, ValueError) as e:
            raise ValueError(f"Invalid IP address: {ip_address}") from e

    # Applica la cache LRU (thread-safe, ma deve essere gestito l'accesso al DB)
    @functools.lru_cache(maxsize=10000)
    def find_network(self, ip_address: str) -> Optional[Dict[str, str]]:

        # Il codice nf.find_network è ora molto più semplice e usa la VIEW
        try:
            ip_int = self.ip_to_int(ip_address)
        except ValueError:
            return None

        # ACQUISISCI IL LOCK PRIMA DI ACCEDERE A SELF.CONN
        # Solo un thread alla volta può eseguire la query su self.conn
        with self.lock:
            query = f"""
                SELECT network, min_ip, max_ip, asn, organization, country
                FROM network_ranges
                WHERE min_ip <= {ip_int} AND {ip_int} <= max_ip
                ORDER BY range_size
                LIMIT 1
            """
            result = self.conn.execute(query).fetchone()

        result_network= {
            'network': ip_address,
            'min_ip': str(ip_int),
            'max_ip': str(ip_int),
            'asn': '00000000',
            'organization': 'unknown',
            'country': 'XX'
        }

        if result:
            result_network= {
                'network': result[0],
                'min_ip': str(result[1]),
                'max_ip': str(result[2]),
                'asn': result[3],
                'organization': result[4],
                'country': result[5]
            }

        return result_network

    def find_network_info(self, ip_address: str) -> Optional[str]:
        """
        Get a formatted string with network information for an IP address.

        Args:
            ip_address: IP address in string format (e.g., "1.2.3.4")

        Returns:
            Formatted string with network information, or None if not found
        """
        result = self.find_network(ip_address)

        if result:
            return (
                f"IP: {ip_address}\n"
                f"Network: {result['network']}\n"
                f"ASN: {result['asn']}\n"
                f"Organization: {result['organization']}\n"
                f"Country: {result['country']}"
            )

        return None

    def __del__(self):
        # Chiudi la connessione DuckDB quando l'istanza viene distrutta
        if hasattr(self, 'conn'):
            self.conn.close()


# Example usage
if __name__ == "__main__":
    # Create an instance of NetworkFinder
    finder = NetworkFinder()

    # Test with some IP addresses
    test_ips = [
        "1.0.0.1",      # Should find Cloudflare
        "1.1.1.1",      # Should find Cloudflare
        "8.8.8.8",      # Google DNS
        "1.20.100.50",  # Should find TOT Public Company Limited
    ]

    for ip in test_ips:
        print(f"\nSearching for IP: {ip}")
        print("-" * 50)
        result = finder.find_network(ip)
        if result:
            print(f"Network: {result['network']}")
            print(f"ASN: {result['asn']}")
            print(f"Organization: {result['organization']}")
            print(f"Country: {result['country']}")
        else:
            print("Network not found")
