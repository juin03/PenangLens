"""
Auto-enrich spots: coordinates, images, AI content.

Usage:
  python scripts/auto_enrich.py                    # enrich all spots
  python scripts/auto_enrich.py --skip "Kek Lok Si Temple,Fort Cornwallis"  # skip specific ones
  python scripts/auto_enrich.py --only-missing     # only spots without content
  python scripts/auto_enrich.py --dry-run          # preview without changes
"""

import os, sys, json, time, argparse, requests
from pathlib import Path

# Config
ADMIN_URL = os.getenv("ADMIN_URL", "http://localhost:3000")
MAPS_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
if not MAPS_KEY:
    sys.exit("GOOGLE_MAPS_API_KEY is not set — export it or add it to Agent/.env")
PLACES_BASE = "https://places.googleapis.com/v1"

def find_place(name: str) -> dict | None:
    """Google Find Place → get place_id, lat/lng."""
    url = f"{PLACES_BASE}/places:searchText"
    headers = {
        "X-Goog-Api-Key": MAPS_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.photos",
        "Content-Type": "application/json",
    }
    body = {"textQuery": f"{name}, Penang, Malaysia", "maxResultCount": 1}
    r = requests.post(url, json=body, headers=headers, timeout=10)
    places = r.json().get("places", [])
    if not places:
        return None
    p = places[0]
    return {
        "name": p.get("displayName", {}).get("text", ""),
        "lat": p.get("location", {}).get("latitude"),
        "lng": p.get("location", {}).get("longitude"),
        "place_id": p.get("id"),
        "photos": [ph.get("name") for ph in p.get("photos", [])[:3]],  # up to 3 photos
    }


def download_photo(photo_ref: str) -> bytes | None:
    """Download a photo from Google Places API."""
    url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&key={MAPS_KEY}"
    r = requests.get(url, timeout=15)
    if r.status_code == 200 and len(r.content) > 1000:
        return r.content
    return None


def update_spot_location(spot_id: str, lat: float, lng: float, token: str = "") -> bool:
    """Update spot coordinates via admin API."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # First get current spot data
    r = requests.get(f"{ADMIN_URL}/api/admin/spots/{spot_id}", headers=headers, timeout=10)
    if not r.ok:
        return False
    spot = r.json().get("spot", {})
    
    # Update with new location
    r2 = requests.patch(f"{ADMIN_URL}/api/admin/spots/{spot_id}", headers=headers, json={
        "name": spot.get("name"),
        "description": spot.get("description"),
        "location": f"{lat:.6f},{lng:.6f}",
        "status": spot.get("status", "published"),
        "content": spot.get("content"),
        "type": spot.get("type", "landmark"),
    }, timeout=10)
    return r2.ok


def upload_image(spot_id: str, photo_bytes: bytes, filename: str, token: str = "") -> bool:
    """Upload image to spot via admin API."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    files = {"image": (filename, photo_bytes, "image/jpeg")}
    r = requests.post(f"{ADMIN_URL}/api/admin/spots/{spot_id}/images", headers=headers, files=files, timeout=30)
    return r.ok


def trigger_ai_curate(spot_id: str, token: str = "") -> bool:
    """Trigger AI content curation for a spot."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{ADMIN_URL}/api/admin/spots/{spot_id}/curate", headers=headers, 
                       json={"instructions": ""}, timeout=60)
    return r.ok


def main():
    parser = argparse.ArgumentParser(description="Auto-enrich spots")
    parser.add_argument("--skip", type=str, default="", help="Comma-separated spot names to skip")
    parser.add_argument("--only-missing", action="store_true", help="Only enrich spots without content")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--no-images", action="store_true", help="Skip image upload")
    parser.add_argument("--no-curate", action="store_true", help="Skip AI curation")
    parser.add_argument("--no-location", action="store_true", help="Skip location update")
    parser.add_argument("--token", type=str, default="", help="Admin auth token")
    args = parser.parse_args()

    skip_names = set(s.strip() for s in args.skip.split(",") if s.strip())

    # Get all spots
    print("Fetching spots from admin portal...")
    r = requests.get(f"{ADMIN_URL}/api/spots/map", timeout=10)
    spots = r.json().get("spots", [])
    print(f"Found {len(spots)} spots\n")

    # Get detailed info for each
    enriched = 0
    skipped = 0
    errors = 0

    for spot in spots:
        name = spot.get("name", "")
        spot_id = spot.get("id", "")
        spot_type = spot.get("type", "landmark")

        if name in skip_names:
            print(f"⏭️  {name} — skipped (in skip list)")
            skipped += 1
            continue

        if args.only_missing:
            # Check if spot has content
            detail_r = requests.get(f"{ADMIN_URL}/api/admin/spots/{spot_id}", timeout=10)
            if detail_r.ok:
                detail = detail_r.json().get("spot", {})
                content = detail.get("content") or {}
                if content.get("overview"):
                    print(f"⏭️  {name} — skipped (has content)")
                    skipped += 1
                    continue

        print(f"\n{'='*60}")
        print(f"📍 {name} (id={spot_id[:8]}...)")

        # Step 1: Google Find Place → correct coordinates
        google_data = find_place(name)
        if not google_data:
            print(f"  ❌ Not found on Google Maps")
            errors += 1
            continue

        print(f"  Google: {google_data['name']} ({google_data['lat']:.4f}, {google_data['lng']:.4f})")
        print(f"  Photos available: {len(google_data['photos'])}")

        if args.dry_run:
            print(f"  [DRY RUN] Would update location, upload {len(google_data['photos'])} photos, curate content")
            enriched += 1
            continue

        # Step 2: Update coordinates
        if not args.no_location:
            ok = update_spot_location(spot_id, google_data["lat"], google_data["lng"], args.token)
            print(f"  📍 Location: {'✅ updated' if ok else '❌ failed'}")
        
        # Step 3: Download and upload photos
        if not args.no_images and google_data["photos"]:
            for i, photo_ref in enumerate(google_data["photos"][:2]):  # max 2 photos
                photo_bytes = download_photo(photo_ref)
                if photo_bytes:
                    ok = upload_image(spot_id, photo_bytes, f"{spot_id}_{i}.jpg", args.token)
                    print(f"  📸 Photo {i+1}: {'✅ uploaded' if ok else '❌ failed'}")
                else:
                    print(f"  📸 Photo {i+1}: ❌ download failed")
                time.sleep(0.5)  # rate limit

        # Step 4: AI curate content
        if not args.no_curate:
            print(f"  ✨ AI curating content...", end=" ", flush=True)
            ok = trigger_ai_curate(spot_id, args.token)
            print(f"{'✅ done' if ok else '❌ failed'}")

        enriched += 1
        time.sleep(1)  # rate limit between spots

    print(f"\n{'='*60}")
    print(f"Done: {enriched} enriched, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
