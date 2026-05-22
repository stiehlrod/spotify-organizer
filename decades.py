#!/usr/bin/env python3
"""
Spotify Decade Organizer
Creates playlists based on track release decade.
"""

import yaml
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pathlib import Path
from collections import defaultdict

CONFIG_PATH = Path(__file__).parent / "config.yaml"

DECADE_NAMES = {
    1950: "50s Classics",
    1960: "60s Classics",
    1970: "70s Classics",
    1980: "80s Hits",
    1990: "90s Hits",
    2000: "2000s",
    2010: "2010s",
    2020: "2020s",
}

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def get_spotify_client(config):
    """Authenticate and return Spotify client."""
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config['spotify']['client_id'],
        client_secret=config['spotify']['client_secret'],
        redirect_uri=config['spotify']['redirect_uri'],
        scope=config['spotify']['scope'],
        cache_path=str(Path(__file__).parent / ".cache")
    ))

def get_saved_tracks(sp):
    """Get all saved tracks from user's library."""
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        for item in results['items']:
            track = item['track']
            if track and track['id']:
                tracks.append(track)
        print(f"  Fetched {len(tracks)} tracks...", end='\r')
        if results['next']:
            results = sp.next(results)
        else:
            break
    print(f"  Fetched {len(tracks)} tracks total")
    return tracks

def get_decade(release_date):
    """Extract decade from release date string."""
    if not release_date:
        return None
    try:
        year = int(release_date[:4])
        decade = (year // 10) * 10
        return decade
    except (ValueError, IndexError):
        return None

def organize_by_decade(tracks):
    """Group tracks by release decade."""
    decades = defaultdict(list)
    no_date_count = 0

    for track in tracks:
        album = track.get('album', {})
        release_date = album.get('release_date')
        decade = get_decade(release_date)

        if decade:
            decades[decade].append({
                'id': track['id'],
                'name': track['name'],
                'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                'year': release_date[:4] if release_date else 'Unknown'
            })
        else:
            no_date_count += 1

    if no_date_count:
        print(f"  Note: {no_date_count} tracks had no release date")

    return decades

def get_user_playlists(sp, user_id):
    """Get all user playlists."""
    playlists = {}
    results = sp.current_user_playlists(limit=50)
    while results:
        for p in results['items']:
            if p['owner']['id'] == user_id:
                playlists[p['name']] = p['id']
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists

def find_or_create_playlist(sp, user_id, name, existing_playlists):
    """Find existing playlist or create new one."""
    if name in existing_playlists:
        return existing_playlists[name]
    new_playlist = sp.user_playlist_create(user_id, name, public=False)
    return new_playlist['id']

def get_playlist_track_ids(sp, playlist_id):
    """Get all track IDs already in a playlist."""
    track_ids = set()
    results = sp.playlist_tracks(playlist_id, fields='items.track.id,next')
    while results:
        for item in results['items']:
            if item['track'] and item['track']['id']:
                track_ids.add(item['track']['id'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return track_ids

def main():
    print("Spotify Decade Organizer")
    print("=" * 40)

    config = load_config()
    sp = get_spotify_client(config)

    user = sp.current_user()
    user_id = user['id']
    print(f"Logged in as: {user['display_name']}\n")

    # Get all saved tracks
    print("Fetching your library...")
    tracks = get_saved_tracks(sp)

    if not tracks:
        print("No saved tracks found!")
        return

    # Organize by decade
    print("\nOrganizing by decade...")
    decades = organize_by_decade(tracks)

    # Show summary
    print("\nTracks by decade:")
    print("-" * 30)
    for decade in sorted(decades.keys()):
        playlist_name = DECADE_NAMES.get(decade, f"{decade}s")
        print(f"  {playlist_name}: {len(decades[decade])} tracks")

    # Get existing playlists
    print("\nFetching your playlists...")
    existing_playlists = get_user_playlists(sp, user_id)

    # Create/update decade playlists
    print("\nCreating/updating decade playlists...")

    for decade in sorted(decades.keys()):
        playlist_name = DECADE_NAMES.get(decade, f"{decade}s")
        decade_tracks = decades[decade]

        if not decade_tracks:
            continue

        # Find or create playlist
        playlist_id = find_or_create_playlist(sp, user_id, playlist_name, existing_playlists)

        # Get existing tracks in playlist
        existing_track_ids = get_playlist_track_ids(sp, playlist_id)

        # Find new tracks to add
        new_track_ids = [t['id'] for t in decade_tracks if t['id'] not in existing_track_ids]

        if new_track_ids:
            # Add in batches of 100 (Spotify API limit)
            for i in range(0, len(new_track_ids), 100):
                batch = new_track_ids[i:i+100]
                sp.playlist_add_items(playlist_id, batch)
            print(f"  {playlist_name}: Added {len(new_track_ids)} new tracks (total: {len(decade_tracks)})")
        else:
            print(f"  {playlist_name}: Already up to date ({len(decade_tracks)} tracks)")

    print("\nDone!")

if __name__ == '__main__':
    main()
