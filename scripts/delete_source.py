#!/usr/bin/env python3
"""
Script to delete a source by its ID using the API endpoint.
"""

import argparse
import requests
import sys
import json


def parse_arguments():
    parser = argparse.ArgumentParser(description='Delete a source by its ID using the API endpoint.')
    parser.add_argument('source_id', help='Source ID to delete')
    parser.add_argument('--host', default='localhost', help='API host (default: localhost)')
    parser.add_argument('--port', type=int, default=8001, help='API port (default: 8001)')
    parser.add_argument('--https', action='store_true', help='Use HTTPS instead of HTTP')
    return parser.parse_args()


def delete_source(source_id: str, host: str, port: int, use_https: bool = False):
    """Delete a source using the API endpoint"""

    protocol = 'https' if use_https else 'http'
    url = f"{protocol}://{host}:{port}/sources/{source_id}"

    try:
        print(f"Deleting source {source_id}...")
        response = requests.delete(url)

        if response.status_code == 204:
            print(f"✅ Source {source_id} deleted successfully")
            return True
        elif response.status_code == 404:
            print(f"❌ Source {source_id} not found")
            return False
        else:
            print(f"❌ Failed to delete source. Status code: {response.status_code}")
            if response.content:
                try:
                    error_data = response.json()
                    print(f"Error: {error_data.get('detail', 'Unknown error')}")
                except json.JSONDecodeError:
                    print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to API at {protocol}://{host}:{port}")
        print("Make sure the API server is running")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        return False


def main():
    args = parse_arguments()

    success = delete_source(
        source_id=args.source_id,
        host=args.host,
        port=args.port,
        use_https=args.https
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()