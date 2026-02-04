import requests


def get_detailed_location():
    try:
        # ipinfo.io က မြန်မာနိုင်ငံမှာ ပိုပြီး stable ဖြစ်လေ့ရှိပါတယ်
        response = requests.get('https://ipinfo.io/json', timeout=20)
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