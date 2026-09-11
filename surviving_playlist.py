#!/usr/bin/env python3
"""
Create a 'Surviving' playlist - songs about resilience, grit, and getting through.
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

def normalize(s):
    return ''.join(c.lower() for c in s if c.isalnum())

def find_track(sp, artist, title):
    """Search with field filters, then verify artist/title match. Try fallbacks."""
    queries = [
        f'artist:"{artist}" track:"{title}"',
        f'artist:{artist} track:{title}',
        f'{artist} {title}',
    ]
    artist_norm = normalize(artist)
    title_norm = normalize(title)

    for q in queries:
        results = sp.search(q=q, type='track', limit=5)
        for track in results['tracks']['items']:
            track_title_norm = normalize(track['name'])
            artist_names_norm = [normalize(a['name']) for a in track['artists']]
            artist_match = any(artist_norm in a or a in artist_norm for a in artist_names_norm)
            title_match = title_norm in track_title_norm or track_title_norm in title_norm
            if artist_match and title_match:
                return track['id'], f"{track['artists'][0]['name']} - {track['name']}"
    return None, None

def find_or_replace_playlist(sp, name):
    """Find existing playlist by name and return its ID, or None."""
    user_id = sp.current_user()['id']
    offset = 0
    while True:
        results = sp.current_user_playlists(limit=50, offset=offset)
        for pl in results['items']:
            if pl['name'] == name and pl['owner']['id'] == user_id:
                return pl['id']
        if not results['next']:
            return None
        offset += 50

def build_playlist(sp, name, description, tracks):
    user_id = sp.current_user()['id']

    existing_id = find_or_replace_playlist(sp, name)
    if existing_id:
        print(f"Found existing playlist '{name}' — clearing and refilling.\n")
        sp.playlist_replace_items(existing_id, [])
        playlist_id = existing_id
    else:
        playlist = sp.user_playlist_create(user_id, name, public=False, description=description)
        playlist_id = playlist['id']

    track_ids = []
    seen = set()
    not_found = []

    for artist, title in tracks:
        track_id, track_name = find_track(sp, artist, title)
        if track_id and track_id not in seen:
            seen.add(track_id)
            track_ids.append(track_id)
            print(f"  + {track_name}")
        elif track_id:
            print(f"  = duplicate skipped: {track_name}")
        else:
            not_found.append(f"{artist} - {title}")
            print(f"  ? Not found: {artist} - {title}")

    if track_ids:
        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id, track_ids[i:i+100])

    return playlist_id, len(track_ids), not_found

def main():
    config = load_config()
    sp = get_spotify_client(config)

    print("Creating 'Surviving' playlist...\n")

    tracks = [
        # (artist, title)
        ("Gloria Gaynor", "I Will Survive"),
        ("Destiny's Child", "Survivor"),
        ("Survivor", "Eye of the Tiger"),
        ("Kelly Clarkson", "Stronger (What Doesn't Kill You)"),
        ("Sia", "Unstoppable"),
        ("Sia", "Alive"),
        ("Rachel Platten", "Fight Song"),
        ("Andra Day", "Rise Up"),
        ("Katy Perry", "Roar"),
        ("Katy Perry", "Rise"),
        ("Christina Aguilera", "Fighter"),
        ("Alicia Keys", "Girl on Fire"),
        ("Sara Bareilles", "Brave"),
        ("P!nk", "Try"),
        ("P!nk", "So What"),
        ("Demi Lovato", "Skyscraper"),
        ("Whitney Houston", "I'm Every Woman"),
        ("Eminem", "Survival"),
        ("Eminem", "Not Afraid"),
        ("Eminem", "Lose Yourself"),
        ("Eminem", "Till I Collapse"),
        ("Kanye West", "Stronger"),
        ("Linkin Park", "In the End"),
        ("Linkin Park", "Numb"),
        ("Imagine Dragons", "Believer"),
        ("Imagine Dragons", "Whatever It Takes"),
        ("Imagine Dragons", "Thunder"),
        ("Twenty One Pilots", "Heathens"),
        ("Twenty One Pilots", "Stressed Out"),
        ("The Score", "Unstoppable"),
        ("The Score", "Legend"),
        ("Bishop Briggs", "River"),
        ("Florence + The Machine", "Shake It Out"),
        ("Florence + The Machine", "Dog Days Are Over"),
        ("Mary J. Blige", "No More Drama"),
        ("2Pac", "Keep Ya Head Up"),
        ("2Pac", "Changes"),
        ("Journey", "Don't Stop Believin'"),
        ("Lady Gaga", "Born This Way"),
    ]

    playlist_id, count, not_found = build_playlist(
        sp,
        "Survivor",
        "Songs about resilience, grit, and getting through",
        tracks
    )

    print(f"\nCreated playlist with {count} tracks.")
    if not_found:
        print(f"\n{len(not_found)} not found (search miss — may need manual add):")
        for q in not_found:
            print(f"  - {q}")
    print(f"\nhttps://open.spotify.com/playlist/{playlist_id}")

if __name__ == '__main__':
    main()
