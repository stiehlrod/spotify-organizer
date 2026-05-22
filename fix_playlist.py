#!/usr/bin/env python3
"""
Fix the Reasonable State of Rage playlist with correct tracks.
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

def main():
    config = load_config()
    sp = get_spotify_client(config)

    playlist_id = "4jzeoCMNNcCJLMxNQ1rdPy"

    print("Rebuilding 'Reasonable State of Rage' playlist...\n")

    # Specific track searches to avoid duplicates
    tracks = [
        # LL Cool J
        "track:Mama Said Knock You Out artist:LL Cool J",

        # Rage Against the Machine
        "track:Killing In the Name artist:Rage Against the Machine",
        "track:Bulls On Parade artist:Rage Against the Machine",
        "track:Guerrilla Radio artist:Rage Against the Machine",
        "track:Bombtrack artist:Rage Against the Machine",
        "track:Know Your Enemy artist:Rage Against the Machine",
        "track:Sleep Now In the Fire artist:Rage Against the Machine",
        "track:Testify artist:Rage Against the Machine",
        "track:Renegades of Funk artist:Rage Against the Machine",

        # Eminem
        "track:Till I Collapse artist:Eminem",
        "track:Lose Yourself artist:Eminem",
        "track:The Way I Am artist:Eminem",
        "track:Survival artist:Eminem",
        "track:Not Afraid artist:Eminem",
        "track:Cinderella Man artist:Eminem",
        "track:Godzilla artist:Eminem",
        "track:Rap God artist:Eminem",
        "track:Berzerk artist:Eminem",

        # DMX
        "track:X Gon Give It To Ya artist:DMX",
        "track:Party Up artist:DMX",
        "track:Ruff Ryders Anthem artist:DMX",

        # Classic hip-hop
        "track:It's Tricky artist:Run-D.M.C.",
        "track:Jump Around artist:House of Pain",
        "track:Insane in the Brain artist:Cypress Hill",
        "track:Fight the Power artist:Public Enemy",
        "track:Sabotage artist:Beastie Boys",
        "track:No Sleep Till Brooklyn artist:Beastie Boys",

        # Rock/Metal
        "track:Enter Sandman artist:Metallica",
        "track:Thunderstruck artist:AC/DC",
        "track:Back in Black artist:AC/DC",
        "track:Walk artist:Pantera",
        "track:Dragula artist:Rob Zombie",
        "track:Crazy Train artist:Ozzy Osbourne",
        "track:Bodies artist:Drowning Pool",

        # Pump-up
        "track:Eye of the Tiger artist:Survivor",
        "track:Stronger artist:Kanye West",
        "track:Power artist:Kanye West",
        "track:Run This Town artist:Jay-Z",
        "track:Remember the Name artist:Fort Minor",
        "track:In Da Club artist:50 Cent",
        "track:DNA artist:Kendrick Lamar",
        "track:HUMBLE artist:Kendrick Lamar",
    ]

    # Search and collect tracks
    track_ids = []
    seen_ids = set()

    for query in tracks:
        track_id, track_name = search_track(sp, query)
        if track_id and track_id not in seen_ids:
            track_ids.append(track_id)
            seen_ids.add(track_id)
            print(f"  + {track_name}")
        elif track_id:
            print(f"  ~ Skipping duplicate: {track_name}")
        else:
            print(f"  ? Not found: {query}")

    # Replace playlist contents
    sp.playlist_replace_items(playlist_id, [])
    if track_ids:
        # Add in batches of 100
        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id, track_ids[i:i+100])

    print(f"\nPlaylist rebuilt with {len(track_ids)} tracks!")
    print(f"https://open.spotify.com/playlist/{playlist_id}")

if __name__ == '__main__':
    main()
