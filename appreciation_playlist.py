#!/usr/bin/env python3
"""
Create "Thank You for Being You" appreciation playlist.
Heartfelt gratitude and love for a special person.
"""

import yaml
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def get_spotify_client(config):
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config['spotify']['client_id'],
        client_secret=config['spotify']['client_secret'],
        redirect_uri=config['spotify']['redirect_uri'],
        scope="user-library-read playlist-modify-public playlist-modify-private playlist-read-private",
        cache_path=str(Path(__file__).parent / ".cache")
    ))

def search_track(sp, query):
    """Search for a track and return its ID."""
    results = sp.search(q=query, type='track', limit=1)
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        return track['id'], f"{track['artists'][0]['name']} - {track['name']}"
    return None, None

def create_playlist(sp, name, description, track_queries):
    """Create a playlist and add tracks."""
    user_id = sp.current_user()['id']

    # Create playlist
    playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
    playlist_id = playlist['id']

    # Search and add tracks
    track_ids = []
    for query in track_queries:
        track_id, track_name = search_track(sp, query)
        if track_id:
            track_ids.append(track_id)
            print(f"  + {track_name}")
        else:
            print(f"  ? Not found: {query}")

    # Add tracks to playlist
    if track_ids:
        sp.playlist_add_items(playlist_id, track_ids)

    return playlist_id, len(track_ids)

def main():
    config = load_config()
    sp = get_spotify_client(config)

    print("Creating 'Thank You for Being You' appreciation playlist...\n")

    tracks = [
        # === OPENING - GRATITUDE & WONDER ===
        "Led Zeppelin Thank You",
        "Ray LaMontagne You Are the Best Thing",
        "Jack Johnson Better Together",
        "Jason Mraz I'm Yours",
        "Jason Mraz Colbie Caillat Lucky",

        # === DEEP APPRECIATION ===
        "Jason Isbell You Make It Easy",
        "Ben Folds The Luckiest",
        "Ed Sheeran Thinking Out Loud",
        "John Legend All of Me",
        "Adele Make You Feel My Love",
        "Carole King You've Got a Friend",
        "Bill Withers Lean on Me",
        "Marvin Gaye Tammi Terrell Ain't No Mountain High Enough",
        "Ben E. King Stand By Me",
        "Queen You're My Best Friend",

        # === WARM & TENDER ===
        "Norah Jones The Nearness of You",
        "Eric Clapton Wonderful Tonight",
        "Etta James At Last",
        "Louis Armstrong What a Wonderful World",
        "Audrey Hepburn Moon River",
        "Edith Piaf La Vie En Rose",

        # === CLOSING - TIMELESS LOVE ===
        "Whitney Houston I Will Always Love You",
        "Righteous Brothers Unchained Melody",
        "The Beatles In My Life",
        "The Beach Boys God Only Knows",
        "The Beatles Here Comes the Sun",
        "Israel Kamakawiwoole Somewhere Over the Rainbow",
        "Bon Jovi Thank You For Loving Me",
    ]

    playlist_id, count = create_playlist(
        sp,
        "Thank You for Being You",
        "Heartfelt appreciation for a loved one. Gratitude, warmth, and timeless love.",
        tracks
    )

    print(f"\nCreated playlist with {count} tracks!")
    print(f"https://open.spotify.com/playlist/{playlist_id}")

if __name__ == '__main__':
    main()
