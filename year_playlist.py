#!/usr/bin/env python3
"""
Spotify Year-Range Playlist Builder
Creates a playlist of songs released within a year range, up to a target duration.
"""

import argparse
import os
import random
import yaml
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    # Prefer env vars; fall back to whatever is in config.yaml.
    cfg['spotify']['client_id'] = (
        os.environ.get('SPOTIFY_CLIENT_ID') or cfg['spotify'].get('client_id'))
    cfg['spotify']['client_secret'] = (
        os.environ.get('SPOTIFY_CLIENT_SECRET') or cfg['spotify'].get('client_secret'))
    if not cfg['spotify']['client_id'] or not cfg['spotify']['client_secret']:
        raise SystemExit(
            "Missing Spotify credentials. Set client_id/client_secret in config.yaml "
            "or export SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET.")
    return cfg


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


def get_year(release_date):
    """Extract year from release date string."""
    if not release_date:
        return None
    try:
        return int(release_date[:4])
    except (ValueError, IndexError):
        return None


def filter_by_year(tracks, start_year, end_year):
    """Return tracks whose release year is within [start_year, end_year]."""
    matched = []
    no_date = 0
    for track in tracks:
        year = get_year(track.get('album', {}).get('release_date'))
        if year is None:
            no_date += 1
            continue
        if start_year <= year <= end_year:
            matched.append({
                'id': track['id'],
                'name': track['name'],
                'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown',
                'year': year,
                'duration_ms': track.get('duration_ms', 0),
            })
    if no_date:
        print(f"  Note: {no_date} tracks had no release date")
    return matched


def select_for_duration(tracks, target_ms, shuffle=True):
    """Pick tracks until the cumulative duration meets/exceeds the target."""
    pool = list(tracks)
    if shuffle:
        random.shuffle(pool)
    selected = []
    total = 0
    for t in pool:
        if total >= target_ms:
            break
        selected.append(t)
        total += t['duration_ms']
    return selected, total


def get_user_playlists(sp, user_id):
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


def find_or_create_playlist(sp, user_id, name, existing):
    if name in existing:
        return existing[name]
    new_playlist = sp.user_playlist_create(user_id, name, public=False)
    return new_playlist['id']


def fmt_duration(ms):
    mins = ms // 60000
    return f"{mins // 60}h {mins % 60}m"


def main():
    parser = argparse.ArgumentParser(description='Build a year-range playlist of a target length.')
    parser.add_argument('--start', type=int, default=2000, help='Start year (inclusive)')
    parser.add_argument('--end', type=int, default=2016, help='End year (inclusive)')
    parser.add_argument('--hours', type=float, default=3.0, help='Target playlist length in hours')
    parser.add_argument('--name', help='Playlist name (default: "<start>-<end> Mix")')
    parser.add_argument('--no-shuffle', action='store_true', help='Keep library order instead of shuffling')
    args = parser.parse_args()

    target_ms = int(args.hours * 3600 * 1000)
    playlist_name = args.name or f"{args.start}-{args.end} Mix"

    print("Spotify Year-Range Playlist Builder")
    print("=" * 40)

    config = load_config()
    sp = get_spotify_client(config)
    user = sp.current_user()
    user_id = user['id']
    print(f"Logged in as: {user['display_name']}\n")

    print("Fetching your library...")
    tracks = get_saved_tracks(sp)
    if not tracks:
        print("No saved tracks found!")
        return

    print(f"\nFiltering {args.start}-{args.end}...")
    matched = filter_by_year(tracks, args.start, args.end)
    matched_total = sum(t['duration_ms'] for t in matched)
    print(f"  {len(matched)} tracks in range ({fmt_duration(matched_total)} total)")

    if not matched:
        print("No tracks matched the year range.")
        return

    if matched_total < target_ms:
        print(f"  Warning: only {fmt_duration(matched_total)} available, "
              f"less than the {args.hours}h target. Using all matched tracks.")

    selected, total = select_for_duration(
        matched, target_ms, shuffle=not args.no_shuffle)
    print(f"\nSelected {len(selected)} tracks ({fmt_duration(total)})")

    print("\nFinding/creating playlist...")
    existing = get_user_playlists(sp, user_id)
    playlist_id = find_or_create_playlist(sp, user_id, playlist_name, existing)

    # Replace contents so re-runs don't pile up duplicates
    track_ids = [t['id'] for t in selected]
    sp.playlist_replace_items(playlist_id, track_ids[:100])
    for i in range(100, len(track_ids), 100):
        sp.playlist_add_items(playlist_id, track_ids[i:i+100])

    print(f"\nDone! '{playlist_name}': {len(selected)} tracks, {fmt_duration(total)}")


if __name__ == '__main__':
    main()
