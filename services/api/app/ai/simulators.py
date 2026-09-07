"""Deterministic AI pipeline simulators (spec §18.1, §18.2, §18.3).

These stand in for real ML extractors (vision, speech, NLP, EXIF). Each
function is seeded from a source's file name + context tags so results
are reproducible across runs, and returns the same shape a real
extractor would — which is what lets the confidence engine and the
conversation agent treat them as ground truth without any model weights.

Context tag conventions used by the family UI:
  structured:  "person:Ramesh"  "place:Shimla"  "date:1992"
               "date:1992-05"   "event:Wedding" "topic:family-trip"
  free text:   "his brother Ramesh"  "from the 1990s"
"""

import hashlib
import re

MODEL_VERSION = "remind-sim-1.0"

# Relationship words that hint a free-form tag names a person (§18.2).
RELATION_WORDS = {
    "brother", "sister", "mother", "father", "grandfather", "grandmother",
    "uncle", "aunt", "wife", "husband", "son", "daughter", "cousin",
    "friend", "neighbour", "neighbor", "colleague",
}

_SCENES = ["family gathering", "outdoor trip", "wedding", "holiday",
           "childhood home", "school", "celebration", "vacation"]
_OBJECTS = ["car", "house", "garden", "river", "temple", "piano",
            "bicycle", "cupboard", "marriage mandap", "trees"]


def _seed(*parts: str) -> float:
    """Stable 0-1 hash of the given strings (reproducible simulation)."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.md5(raw).hexdigest()[:8], 16) / 2**32


def _parse_tags(context_tags: list[str] | None) -> dict:
    """Split context tags into structured person/place/date/event/topic + free."""
    tags = context_tags or []
    structured: dict[str, list[str]] = {
        "person": [], "place": [], "date": [], "event": [], "topic": [],
    }
    free: list[str] = []
    for tag in tags:
        text = str(tag)
        key, _, value = text.partition(":")
        if key in structured and value.strip():
            structured[key].append(value.strip())
            continue
        free.append(text)
    return {"structured": structured, "free": free}


def _dates_from_tags(free_tags: list[str]) -> list[str]:
    """Pull years / year-month / full dates out of free-form tags."""
    dates: list[str] = []
    for text in free_tags:
        for match in re.finditer(r"\b(19\d{2}|20\d{2})(?:-(\d{1,2}))?(?:-(\d{1,2}))?\b", text):
            dates.append(match.group(0))
    return dates


def _people_from_free_tags(free_tags: list[str]) -> list[str]:
    """Names from free tags like 'his brother Ramesh' via relation words."""
    names: list[str] = []
    for text in free_tags:
        lowered = text.lower()
        for word in RELATION_WORDS:
            pattern = re.compile(rf"\b{word}\s+([A-Z][a-z]+)", re.IGNORECASE)
            match = pattern.search(lowered if False else text)
            if match:
                names.append(match.group(1))
                break
    return names


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def extract_vision(source, context_tags: list[str] | None = None) -> dict:
    """Photo/video frames -> faces + scene + objects (spec §18.2)."""
    seed = _seed(source.file_name, "vision")
    face_count = 1 + int(seed * 3) % 3  # 1-3 faces
    faces = []
    for i in range(face_count):
        fseed = _seed(source.file_name, "face", i)
        confidence = round(0.55 + fseed * 0.42, 2)  # 0.55-0.97
        if confidence > 0.85:
            state = "LIKELY_MATCH"
        elif confidence > 0.60:
            state = "POSSIBLE_MATCH"
        else:
            state = "UNIDENTIFIED"
        faces.append({
            "region_id": f"face_{i}",
            "confidence": confidence,
            "face_match_state": state,
        })
    return {
        "faces": faces,
        "scene": _SCENES[int(seed * len(_SCENES)) % len(_SCENES)],
        "objects": _pick(_OBJECTS, source.file_name, 3),
    }


def extract_speech(source, context_tags: list[str] | None = None) -> dict:
    """Audio -> transcript (simulated) + duration (spec §18.3)."""
    seed = _seed(source.file_name, "speech")
    _, free = _parse_tags(context_tags)
    transcript = (
        " ".join(free[:3])
        if free
        else "Family recording: a short conversation about old times."
    )
    return {
        "transcript": transcript,
        "duration_s": 60 + int(seed * 240),
        "speaker_count": 1 + int(seed * 3) % 3,
    }


def extract_nlp(
    source,
    context_tags: list[str] | None = None,
    transcript: str | None = None,
) -> dict:
    """Documents/messages -> people, places, dates, topics (§18.3)."""
    parsed = _parse_tags(context_tags)
    structured = parsed["structured"]
    free = parsed["free"]

    people = list(structured["person"])
    people += _people_from_free_tags(free)
    places = list(structured["place"])
    dates = list(structured["date"]) + _dates_from_tags(free)

    if transcript:
        found = re.findall(r"\b[A-Z][a-z]+\b", transcript)
        people += [w for w in found if w.lower() not in RELATION_WORDS][:2]

    # de-dup, keep order
    seen: set[str] = set()
    people = [p for p in people if not (p in seen or seen.add(p))]
    places = [p for p in places if not (p in seen or seen.add(p))]
    dates = [d for d in dates if not (d in seen or seen.add(d))]

    return {
        "people": people,
        "places": places,
        "dates": dates,
        "topics": list(structured["topic"]),
    }


def extract_location(source, context_tags: list[str] | None = None) -> dict:
    """EXIF-style location signal. Deterministic: has GPS iff seed > 0.5."""
    seed = _seed(source.file_name, "location")
    has_exif = seed > 0.5
    parsed = _parse_tags(context_tags)
    places = parsed["structured"]["place"]
    return {
        "has_exif": has_exif,
        "has_context_place": bool(places),
        "gps": {"lat": round(28.6 + seed, 4), "lon": round(77.2 - seed * 0.3, 4)}
        if has_exif else None,
        "place_name": places[0] if places else None,
    }


def _pick(options: list[str], seed_key: str, count: int) -> list[str]:
    seed = _seed(seed_key, "pick")
    step = int(seed * 31) + 1
    picked = []
    for i in range(count):
        picked.append(options[int(seed * len(options) + i * step) % len(options)])
    return picked


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_FILE_TYPE_PIPELINE = {
    "photo": ["vision", "nlp", "location"],
    "video": ["vision", "speech", "nlp"],
    "audio": ["speech", "nlp"],
    "document": ["nlp"],
    "message_export": ["nlp"],
}


def extractors_for(file_type: str) -> list[str]:
    return _FILE_TYPE_PIPELINE.get(file_type, ["nlp"])


def run_all_extractors(source, context_tags: list[str] | None = None) -> dict:
    """Run every extractor a file type needs; returns the pipeline_result.

    This is what real `process_source` code will replace with calls to
    remote model services — the shape stays the same.
    """
    tags = context_tags or []
    results: dict = {"model_version": MODEL_VERSION}
    transcript = None

    for stage in extractors_for(source.file_type or "document"):
        if stage == "vision":
            results["vision"] = extract_vision(source, tags)
        elif stage == "speech":
            results["speech"] = extract_speech(source, tags)
            transcript = results["speech"]["transcript"]
        elif stage == "nlp":
            results["nlp"] = extract_nlp(source, tags, transcript=transcript)
        elif stage == "location":
            results["location"] = extract_location(source, tags)

    return results
