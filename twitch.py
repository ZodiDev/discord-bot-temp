import requests

client_secret = "qx300tyrf6y0dlphqnpyhtcsqh8z1h"
client_id = "pwrva8e4zzvqwwpha1kdtzw6ccempn"
 
class Stream:
 
    def __init__(self, title, streamer, game, thumbnail_url):
        self.title = title
        self.streamer = streamer
        self.game = game
        self.thumbnail_url = thumbnail_url
        
# getting the auth token from the twitch API
def getOAuthToken():
    body = {
        'client_id': client_id,
        'client_secret': client_secret,
        "grant_type": 'client_credentials'
    }
    r = requests.post('https://id.twitch.tv/oauth2/token', body)
 
    #data output
    keys = r.json()
    return keys['access_token']
 
def checkIfLive(channel):
    # Calling the twitch api to check if a specific is live
    url = "https://api.twitch.tv/helix/streams?user_login=" + channel
    token = getOAuthToken()
 
    HEADERS = {
        'Client-ID': client_id,
        'Authorization': 'Bearer ' + token
    }
 
    try:
        
        req = requests.get(url, headers=HEADERS)
        
        res = req.json()
 
        if len(res['data']) > 0: # the twitch channel is live
            data = res['data'][0]
            title = data['title']
            streamer = data['user_name']
            game = data['game_name']
            thumbnail_url = data['thumbnail_url']
            stream = Stream(title, streamer, game, thumbnail_url)
            return stream
        else:
            return "OFFLINE"
    except Exception as e:
        return "An error occured: " + str(e)