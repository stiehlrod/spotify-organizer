#!/usr/bin/env python3
"""
Create a custom playlist from search terms.
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

    print("Creating 'Reasonable State of Rage' playlist...\n")

    # Aggressive lifting tracks (no nu-metal)
    tracks = [
        # LL Cool J
        "LL Cool J Mama Said Knock You Out",

        # Rage Against the Machine
        "Rage Against the Machine Killing In the Name",
        "Rage Against the Machine Bulls on Parade",
        "Rage Against the Machine Guerrilla Radio",
        "Rage Against the Machine Bombtrack",
        "Rage Against the Machine Know Your Enemy",
        "Rage Against the Machine Sleep Now in the Fire",
        "Rage Against the Machine Testify",

        # Eminem
        "Eminem Till I Collapse",
        "Eminem Lose Yourself",
        "Eminem The Way I Am",
        "Eminem Survival",
        "Eminem Not Afraid",
        "Eminem Cinderella Man",
        "Eminem Won't Back Down",
        "Eminem Godzilla",
        "Eminem Rap God",

        # Classic aggressive hip-hop
        "DMX X Gon Give It To Ya",
        "DMX Party Up",
        "Run DMC It's Tricky",
        "House of Pain Jump Around",
        "Cypress Hill Insane in the Brain",
        "Public Enemy Fight the Power",
        "Beastie Boys Sabotage",
        "Beastie Boys No Sleep Till Brooklyn",

        # Heavy rock/metal
        "Metallica Enter Sandman",
        "AC/DC Thunderstruck",
        "AC/DC Back in Black",
        "Pantera Walk",
        "Rob Zombie Dragula",
        "Ozzy Osbourne Crazy Train",

        # Classic pump-up
        "Survivor Eye of the Tiger",
        "Kanye West Stronger",
        "Kanye West Power",
        "Jay-Z Run This Town",
        "Fort Minor Remember the Name",
        "50 Cent In Da Club",
        "Kendrick Lamar DNA",
        "Kendrick Lamar HUMBLE",
    ]

    playlist_id, count = create_playlist(
        sp,
        "Reasonable State of Rage",
        "Aggressive lifting playlist - Eminem, RATM, LL Cool J and more",
        tracks
    )

    print(f"\nCreated playlist with {count} tracks!")
    print(f"https://open.spotify.com/playlist/{playlist_id}")

if __name__ == '__main__':
    main()
