import requests
import json


def check_nvidia_limits():
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

    # သင့် API Key ကို ဤနေရာတွင် ထည့်ပါ
    api_key = "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"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "mistralai/mistral-large-3-675b-instruct-2512",
        "messages": [{"role": "user", "content": "Hello"}],  # Limit စစ်ရန် test message
        "max_tokens": 10
    }

    response = requests.post(invoke_url, headers=headers, json=payload)

    if response.status_code == 200:
        print("--- API Rate Limit Information ---")

        # Header ထဲက Limit အချက်အလက်များကို ဆွဲထုတ်ခြင်း
        # မှတ်ချက်- Header key နာမည်များသည် NVIDIA update ပေါ်မူတည်၍ အနည်းငယ်ပြောင်းလဲနိုင်သည်
        rpm_limit = response.headers.get("x-ratelimit-limit-requests", "N/A")
        rpm_remaining = response.headers.get("x-ratelimit-remaining-requests", "N/A")

        tpm_limit = response.headers.get("x-ratelimit-limit-tokens", "N/A")
        tpm_remaining = response.headers.get("x-ratelimit-remaining-tokens", "N/A")

        reset_time = response.headers.get("x-ratelimit-reset-requests", "N/A")

        print(f"Requests Per Minute (RPM) Limit: {rpm_limit}")
        print(f"Requests Remaining: {rpm_remaining}")
        print(f"Tokens Per Minute (TPM) Limit: {tpm_limit}")
        print(f"Tokens Remaining: {tpm_remaining}")
        print(f"Limit Reset In: {reset_time} seconds")

    else:
        print(f"Error: {response.status_code}")
        print(response.text)


check_nvidia_limits()