import requests
import yaml
import time
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlparse
from collections import defaultdict

def create_session() -> requests.Session:
    """
    Create a requests.Session with retry disabled.

    Returns:
        requests.Session: A requests.Session object with retries disabled.
    """
    session = requests.Session()
    # Disable retries for all requests
    adapter = requests.adapters.HTTPAdapter(max_retries=0)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def send_request(method: str, url: str, headers: Dict[str, str], body: Optional[str], session: requests.Session) -> Tuple[str, Optional[float]]:
    """
    Send an HTTP request based on the specified method and return the status and latency.

    Args:
        method (str): The HTTP method to use for the request.
        url (str): The URL to send the request to.
        headers (dict): The headers to include in the request.
        body (str, optional): The body of the request for POST, PUT, PATCH, etc.
        session (requests.Session): The requests session to use for the HTTP request.

    Returns:
        Tuple[str, Optional[float]]: A tuple where the first element is 'UP' or 'DOWN'
                                     based on the response, and the second element is
                                     the response latency in milliseconds or None.
    """
    start_time = time.time()
    
    method_switcher = {
        'GET': session.get,
        'POST': session.post,
        'PUT': session.put,
        'DELETE': session.delete,
        'HEAD': session.head,
        'OPTIONS': session.options,
        'PATCH': session.patch,
    }

    try:
        request_function = method_switcher.get(method.upper(), session.get)  # Default to GET
        response = request_function(url, headers=headers, data=body, timeout=1)
        
        # Check if the response is considered UP
        if 200 <= response.status_code < 300:
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            if latency < 500:
                return 'UP'

    except requests.RequestException as e:
        return 'DOWN'

    return 'DOWN'

def check_endpoint(endpoint: Dict, session: requests.Session) -> Tuple[str, Optional[float]]:
    """
    Check the health of a single HTTP endpoint by sending an HTTP request.

    Args:
        endpoint (dict): A dictionary representing the HTTP endpoint to be tested.
        session (requests.Session): The requests session to use for the HTTP request.

    Returns:
        Tuple[str, Optional[float]]: A tuple where the first element is 'UP' or 'DOWN'
                                     based on the response, and the second element is
                                     the response latency in milliseconds or None.
    """
    url: str = endpoint.get('url')
    method: str = endpoint.get('method', 'GET')
    headers: Dict[str, str] = endpoint.get('headers', {})
    body: Optional[str] = endpoint.get('body')

    return send_request(method, url, headers, body, session)

def monitor_endpoints(endpoints: List[Dict[str, Optional[str]]]) -> None:
    """
    Continuously monitor the health of a list of HTTP endpoints by sending HTTP requests
    every 15 seconds.

    Args:
        endpoints (List[Dict[str, Optional[str]]]): A list of dictionaries representing
                                                     the HTTP endpoints.
    """
    domain_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'up': 0, 'down': 0})
    domain_totals: Dict[str, int] = defaultdict(int)
    
    session = create_session()  # Create a session with retries disabled

    while True:  # Run until there is a KeyboardInterrupt

        for endpoint in endpoints:
            url = endpoint['url']
            status = check_endpoint(endpoint, session)
            domain = urlparse(url).netloc  # Get only the domain, not the full URL
            
            domain_totals[domain] += 1
            if status == 'UP':
                domain_stats[domain]['up'] += 1
            else:
                domain_stats[domain]['down'] += 1

        # Log the availability percentages
        for domain, stats in domain_stats.items():
            total_count = domain_totals[domain]
            availability = (100 * stats['up'] / total_count) if total_count else 0
            print(f"{domain} has {round(availability)}% availability percentage")

        # Wait for 15 seconds before the next cycle
        time.sleep(15)

def load_endpoints(config_path: str) -> List[Dict[str, Optional[str]]]:
    """
    Load the list of HTTP endpoints from a YAML configuration file.

    Args:
        config_path (str): The path to the YAML configuration file containing the HTTP endpoints.

    Returns:
        List[Dict[str, Optional[str]]]: A list of dictionaries where each dictionary represents an HTTP endpoint.
    """
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)   # Parse the YAML to an object
    except FileNotFoundError:
        print(f"Error: The file at {config_path} was not found.")
        exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing the YAML file: {e}")
        exit(1)

def main() -> None:
    """
    Main function to run the health check program. It accepts a configuration file path as input,
    loads the endpoints, and starts monitoring their health every 15 seconds.
    """
    import sys
    if len(sys.argv) != 2:
        print("Usage: python health_check.py <config_file_path>")
        sys.exit(1)

    config_file_path = sys.argv[1]
    endpoints = load_endpoints(config_file_path)

    if not endpoints:
        print("No endpoints to monitor.")
        sys.exit(1)

    print(f"Monitoring {len(endpoints)} endpoints in an interval of 15 seconds... Press Ctrl+C to stop.")
    monitor_endpoints(endpoints)

if __name__ == "__main__":
    main()