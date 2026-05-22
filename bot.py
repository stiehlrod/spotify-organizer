#!/usr/bin/env python3
"""
Spotify Organizer Bot
Refreshes "Fresh" rotation playlists with non-repeating songs.
"""

import argparse
import os
import sqlite3
import yaml
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timedelta
from pathlib import Path
import random

# Paths
CONFIG_PATH = Path(__file__).parent / "config.yaml"
DB_PATH = Path(__file__).parent / "rotation_history.db"

def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    cfg['spotify']['client_id'] = os.environ['SPOTIFY_CLIENT_ID']
    cfg['spotify']['client_secret'] = os.environ['SPOTIFY_CLIENT_SECRET']
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

def init_db():
    """Initialize SQLite database for rotation history."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS rotation_history (
            id INTEGER PRIMARY KEY,
            track_id TEXT NOT NULL,
            mood TEXT NOT NULL,
            rotation_date TEXT NOT NULL,
            rotation_number INTEGER NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rotation_meta (
            mood TEXT PRIMARY KEY,
            last_rotation_date TEXT,
            last_rotation_number INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def get_user_playlists(sp):
    """Get all user playlists."""
    playlists = []
    results = sp.current_user_playlists(limit=50)
    while results:
        playlists.extend(results['items'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return playlists

def find_playlist_by_name(playlists, name, user_id):
    """Find playlist by name (with or without emoji prefix)."""
    # Try exact match first
    for p in playlists:
        if p['name'] == name and p['owner']['id'] == user_id:
            return p['id']
    # Try with common emoji prefixes
    emoji_variants = [f"😌 {name}", f"🔥 {name}", f"😊 {name}", f"😢 {name}", f"🎯 {name}", f"🔄 {name}"]
    for variant in emoji_variants:
        for p in playlists:
            if p['name'] == variant and p['owner']['id'] == user_id:
                return p['id']
    # Try partial match (name contains)
    for p in playlists:
        if name in p['name'] and p['owner']['id'] == user_id:
            return p['id']
    return None

def find_or_create_playlist(sp, user_id, name, playlists):
    """Find existing playlist or create new one."""
    playlist_id = find_playlist_by_name(playlists, name, user_id)
    if playlist_id:
        return playlist_id
    # Create new playlist
    new_playlist = sp.user_playlist_create(user_id, name, public=False)
    return new_playlist['id']

def get_playlist_tracks(sp, playlist_id):
    """Get all track IDs from a playlist."""
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            if item['track'] and item['track']['id']:
                tracks.append(item['track']['id'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    return tracks

def get_excluded_tracks(conn, mood, num_rotations):
    """Get track IDs that should be excluded (recently played)."""
    c = conn.cursor()
    c.execute('''
        SELECT DISTINCT track_id FROM rotation_history
        WHERE mood = ?
        AND rotation_number > (
            SELECT COALESCE(MAX(rotation_number), 0) - ?
            FROM rotation_history WHERE mood = ?
        )
    ''', (mood, num_rotations, mood))
    return set(row[0] for row in c.fetchall())

def record_rotation(conn, mood, track_ids):
    """Record tracks used in this rotation."""
    c = conn.cursor()

    # Get next rotation number
    c.execute('SELECT COALESCE(MAX(rotation_number), 0) + 1 FROM rotation_history WHERE mood = ?', (mood,))
    rotation_num = c.fetchone()[0]

    # Record tracks
    today = datetime.now().isoformat()
    for track_id in track_ids:
        c.execute('''
            INSERT INTO rotation_history (track_id, mood, rotation_date, rotation_number)
            VALUES (?, ?, ?, ?)
        ''', (track_id, mood, today, rotation_num))

    # Update meta
    c.execute('''
        INSERT OR REPLACE INTO rotation_meta (mood, last_rotation_date, last_rotation_number)
        VALUES (?, ?, ?)
    ''', (mood, today, rotation_num))

    conn.commit()
    return rotation_num

def should_rotate(conn, mood, refresh_days):
    """Check if enough time has passed since last rotation."""
    c = conn.cursor()
    c.execute('SELECT last_rotation_date FROM rotation_meta WHERE mood = ?', (mood,))
    row = c.fetchone()
    if not row or not row[0]:
        return True
    last_date = datetime.fromisoformat(row[0])
    return datetime.now() - last_date >= timedelta(days=refresh_days)

def rotate_playlists(sp, config, conn, force=False, mood_filter=None):
    """Create/refresh rotation playlists."""
    user_id = sp.current_user()['id']
    playlists = get_user_playlists(sp)
    rotation_config = config['rotation']

    songs_per_playlist = rotation_config['songs_per_playlist']
    refresh_days = rotation_config['refresh_days']
    history_rotations = rotation_config['history_rotations']
    prefix = rotation_config['naming']['prefix']
    sources = rotation_config['sources']

    moods_to_process = list(sources.keys())
    if mood_filter:
        moods_to_process = [m for m in moods_to_process if m == mood_filter]

    results = []

    for mood in moods_to_process:
        source_name = sources[mood]

        # Check if rotation is due
        if not force and not should_rotate(conn, mood, refresh_days):
            print(f"  Skipping {mood} - not due yet (use --force to override)")
            continue

        # Find source playlist
        source_playlist_id = find_playlist_by_name(playlists, source_name, user_id)

        if not source_playlist_id:
            print(f"  Source playlist '{source_name}' not found - skipping {mood}")
            continue

        # Get all tracks from source
        all_tracks = get_playlist_tracks(sp, source_playlist_id)
        print(f"  {mood}: Found {len(all_tracks)} tracks in source")

        # Get excluded tracks (recently rotated)
        excluded = get_excluded_tracks(conn, mood, history_rotations)

        # Filter available tracks
        available = [t for t in all_tracks if t not in excluded]
        print(f"  {mood}: {len(available)} available (excluding {len(excluded)} recently played)")

        if len(available) < songs_per_playlist:
            print(f"  Warning: Only {len(available)} available tracks for {mood}")
            # Reset history if we've run out
            if len(available) < songs_per_playlist // 2:
                print(f"  Resetting history for {mood} - not enough fresh tracks")
                c = conn.cursor()
                c.execute('DELETE FROM rotation_history WHERE mood = ?', (mood,))
                c.execute('DELETE FROM rotation_meta WHERE mood = ?', (mood,))
                conn.commit()
                available = all_tracks

        # Select tracks for rotation
        random.shuffle(available)
        selected = available[:songs_per_playlist]

        # Create rotation playlist name
        rotation_name = f"{prefix} {mood.title()}"

        # Find or create rotation playlist
        rotation_playlist_id = find_or_create_playlist(sp, user_id, rotation_name, playlists)

        # Clear existing tracks
        sp.playlist_replace_items(rotation_playlist_id, [])

        # Add new tracks
        if selected:
            sp.playlist_add_items(rotation_playlist_id, selected)

        # Record rotation
        rotation_num = record_rotation(conn, mood, selected)

        results.append({
            'mood': mood,
            'playlist': rotation_name,
            'tracks': len(selected),
            'rotation': rotation_num
        })

        print(f"  Refreshed '{rotation_name}' with {len(selected)} tracks (rotation #{rotation_num})")

    return results

def show_history(conn):
    """Display rotation history."""
    c = conn.cursor()
    c.execute('''
        SELECT mood, last_rotation_date, last_rotation_number
        FROM rotation_meta ORDER BY mood
    ''')
    rows = c.fetchall()

    if not rows:
        print("No rotation history found.")
        return

    print("\nRotation History:")
    print("-" * 50)
    for mood, last_date, last_num in rows:
        date_str = last_date[:10] if last_date else "Never"
        print(f"  {mood}: Rotation #{last_num} on {date_str}")

def reset_history(conn, mood=None):
    """Reset rotation history."""
    c = conn.cursor()
    if mood:
        c.execute('DELETE FROM rotation_history WHERE mood = ?', (mood,))
        c.execute('DELETE FROM rotation_meta WHERE mood = ?', (mood,))
        print(f"Reset history for {mood}")
    else:
        c.execute('DELETE FROM rotation_history')
        c.execute('DELETE FROM rotation_meta')
        print("Reset all rotation history")
    conn.commit()

def main():
    parser = argparse.ArgumentParser(description='Spotify Fresh Playlist Rotation')
    parser.add_argument('command', nargs='?', default='rotate', help='Command: rotate, history, reset')
    parser.add_argument('--mood', '-m', help='Only rotate specific mood')
    parser.add_argument('--force', '-f', action='store_true', help='Force rotation even if not due')

    args = parser.parse_args()

    config = load_config()
    conn = init_db()

    if args.command == 'history':
        show_history(conn)
    elif args.command == 'reset':
        reset_history(conn, args.mood)
    else:  # rotate
        print("Connecting to Spotify...")
        sp = get_spotify_client(config)
        print(f"Logged in as: {sp.current_user()['display_name']}\n")
        print(f"Refreshing Fresh playlists ({config['rotation']['songs_per_playlist']} songs each)...\n")
        results = rotate_playlists(sp, config, conn, force=args.force, mood_filter=args.mood)
        if results:
            print(f"\nDone! Refreshed {len(results)} playlist(s)")
        else:
            print("\nNo playlists were refreshed (use --force to override timing)")

    conn.close()

if __name__ == '__main__':
    main()
