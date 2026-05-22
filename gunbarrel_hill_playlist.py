#!/usr/bin/env python3
"""
Create "Out to Gunbarrel Hill" adventure playlist for Boulder bike route.
Route: https://ridewithgps.com/routes/53668773
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

    print("Creating 'Out to Gunbarrel Hill' adventure playlist...\n")
    print("Route: Boulder, CO - 31.2km loop, mixed terrain\n")

    # Tracks organized by ride section
    tracks = [
        # === WARM-UP / START (0-15 min) ===
        # Easy rolling out of Boulder - chill, scenic vibes
        "The Lumineers Ho Hey",
        "Edward Sharpe Magnetic Zeros Home",
        "Mumford Sons I Will Wait",
        "Nathaniel Rateliff Night Sweats S.O.B.",
        "The Lumineers Ophelia",

        # === TRAIL SECTIONS (15-40 min) ===
        # Unpaved adventure on Fourmile Creek & Cottonwood Trails
        "Of Monsters and Men Little Talks",
        "Lord Huron The Night We Met",
        "Vance Joy Riptide",
        "Fleet Foxes White Winter Hymnal",
        "Of Monsters and Men Mountain Sound",
        "Lord Huron Ends of the Earth",
        "Vance Joy Georgia",
        "Fleet Foxes Mykonos",
        "Of Monsters and Men Dirty Paws",

        # === CRUISING PAVED SECTIONS (40-65 min) ===
        # East Boulder Trail - pick up the pace
        "The War on Drugs Under the Pressure",
        "Hozier No Plan",
        "Harry Styles Golden",
        "Arcade Fire Sprawl II Mountains Beyond Mountains",
        "Band of Horses No One's Gonna Love You",
        "Local Natives Sun Hands",
        "The War on Drugs Red Eyes",
        "Milky Chance Stolen Dance",

        # === FINAL PUSH / GUNBARREL HILL (65-90 min) ===
        # Building energy, triumphant finish
        "Band of Horses The Funeral",
        "Arcade Fire Wake Up",
        "Local Natives Heavy Feet",
        "Radiohead Burn the Witch",
        "Daughter Youth",
        "Empire of the Sun Alive",
    ]

    playlist_id, count = create_playlist(
        sp,
        "Out to Gunbarrel Hill",
        "Boulder adventure ride - 31km loop through Fourmile Creek, Cottonwood & East Boulder Trails. Mixed terrain, easy rolling. ridewithgps.com/routes/53668773",
        tracks
    )

    print(f"\nCreated playlist with {count} tracks!")
    print(f"https://open.spotify.com/playlist/{playlist_id}")

if __name__ == '__main__':
    main()
