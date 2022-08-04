import requests
import json

requests.packages.urllib3.disable_warnings()
Main = object()
desigo_ip = str()
desigo_username = str()
desigo_password = str()

def check_ip():
    url = f"https://{desigo_ip}/WSI/api/token"
    payload = {
            "grant_type": "password",
            "username": desigo_username,
            "password": desigo_password
    }
    check_ip_response = requests.post(url,data = payload, verify=False)
    if check_ip_response.status_code == 400:
        Main.info("Desigo CC connect fail")
    else:
        token = json.loads(check_ip_response.text)["access_token"]
        url = f"https://{desigo_ip}/WSI/api/token"
        headers = {
                    "Authorization":f"Bearer {token}",
                    "Content-Type": "application/json"
                }
        delete_check_ip_token_response = requests.delete(url,headers = headers, verify=False)
        if delete_check_ip_token_response.status_code == 200:
            Main.info("Desigo CC connect success")

def get_token():
    url = f"https://{desigo_ip}/WSI/api/token"
    payload = {
            "grant_type": "password",
            "username": desigo_username,
            "password": desigo_password
    }
    get_token_response = requests.post(url,data = payload, verify=False)
    return get_token_response

def delete_token(token):
    url = f"https://{desigo_ip}/WSI/api/token"
    headers = {
                "Authorization":f"Bearer {token}",
                "Content-Type": "application/json"
            }
    requests.delete(url,headers = headers, verify=False)

def get(token, url):
    headers = {
        "Authorization":f"Bearer {token}",
        "Content-Type": "application/json"
    }
    return requests.get(url, headers = headers, verify=False)

def post(token, url, payload):
    headers = {
            "Authorization":f"Bearer {token}",
            "Content-Type": "application/json"
    }
    return requests.post(url, headers = headers, data = payload, verify=False)