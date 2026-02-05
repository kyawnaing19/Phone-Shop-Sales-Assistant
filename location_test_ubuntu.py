import os
import requests

# Proxy
PROXY = "socks5h://10.58.39.212:1080"   # use socks5h for DNS through proxy

proxies = {
    "http": PROXY,
    "https": PROXY
}

def get_detailed_location():
    try:
        response = requests.get(
            "https://ipinfo.io/json",
            proxies=proxies,
            timeout=20
        )
        data = response.json()

        print(f"IP: {data.get('ip')}")
        print(f"City: {data.get('city')}")
        print(f"Region: {data.get('region')}")
        print(f"Country: {data.get('country')}")
        print(f"ISP: {data.get('org')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_detailed_location()
