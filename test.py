import requests

proxies = {
    "http": "http://ztkwyxsu-at-10:epgki0xf3yn0@p.webshare.io:80",
    "https": "http://ztkwyxsu-at-10:epgki0xf3yn0@p.webshare.io:80",
}

r = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
print(r.text)