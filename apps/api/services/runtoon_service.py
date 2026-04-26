"""
Runtoon Service — prompt assembly + Gemini image generation.

Responsibilities:
    1. Assemble the 4-layer prompt (style anchor + athlete photos + activity
       data + coaching insight/caption)
    2. Call gemini-3.1-flash-image-preview via google.genai SDK
    3. Return raw image bytes + caption text + stats text

This service has NO database access and NO storage writes. The Celery task
(runtoon_tasks.py) handles all DB reads before calling this service and all
DB writes + R2 uploads after. This keeps session lifetimes clean and testable.

Model string: "gemini-3.1-flash-image-preview"
    Always use this exact API string. Never use the marketing name.

Follows the adaptation_narrator.py pattern:
    - GENAI_AVAILABLE guard for import-time resilience
    - Module-level genai alias for patch-ability in tests
    - Optional client injection for testability
"""

import base64
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Guard import — same pattern as adaptation_narrator.py
# ---------------------------------------------------------------------------

try:
    from google import genai as _genai_module
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    _genai_module = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

genai = _genai_module  # module-level alias for patch-ability in tests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUNTOON_MODEL = "gemini-3.1-flash-image-preview"
RUNTOON_TEMPERATURE = 0.9          # Higher temp = more creative/varied output
RUNTOON_TIMEOUT_SECONDS = 55       # Hard timeout before task soft_time_limit (60s)
RUNTOON_COST_USD_PER_IMAGE = 0.067  # 1K resolution estimate

CAPTION_MODEL = "gemini-2.5-flash"  # Text-only for caption generation
CAPTION_TEMPERATURE = 0.8
CAPTION_MAX_TOKENS = 80

# Blocklist for caption content guardrail
CAPTION_BLOCKLIST = frozenset([
    "fuck", "shit", "ass", "bitch", "cunt", "damn", "hell",
    "nigger", "faggot", "retard", "slut", "whore",
])

_STRAVA_AUTO_NAMES = frozenset({
    "morning run", "afternoon run", "evening run", "night run", "lunch run",
    "morning walk", "afternoon walk", "evening walk", "lunch walk",
    "morning ride", "afternoon ride", "evening ride", "lunch ride",
    "long run", "race",
})

_GARMIN_AUTO_SUFFIXES = (" Running", " Walking", " Cycling", " Hiking")


def _is_auto_generated_name(name: Optional[str], provider: Optional[str]) -> bool:
    """Return True if activity name is platform-generated, not athlete-authored."""
    if not name or not name.strip():
        return True
    if provider == "demo":
        return True
    if name.strip().lower() in _STRAVA_AUTO_NAMES:
        return True
    if provider == "garmin":
        for suffix in _GARMIN_AUTO_SUFFIXES:
            if name.endswith(suffix):
                return True
    return False


def _resolve_activity_title(activity) -> Optional[str]:
    """Local title resolver to avoid importing API routers inside worker tasks."""
    athlete_title = getattr(activity, "athlete_title", None)
    if athlete_title:
        return athlete_title

    name = getattr(activity, "name", None)
    sentence = getattr(activity, "shape_sentence", None)
    provider = getattr(activity, "provider", None) or ""
    is_race = (
        getattr(activity, "user_verified_race", False)
        or getattr(activity, "is_race_candidate", False)
    )

    if is_race and name:
        return name
    if name and not _is_auto_generated_name(name, provider):
        return name
    return sentence or name

# ---------------------------------------------------------------------------
# Style anchor (Layer 1) — hardcoded brand constant
# ---------------------------------------------------------------------------

STYLE_ANCHOR = """Bold, vibrant caricature/comic style. NOT photorealistic.
The runner is the HERO. Accurate to their real body from reference photos.
Depict them honestly — do not idealize or alter their body type.
Make them look GOOD — flattering, aspirational, someone who'd want to share this.
Fully clothed in appropriate running gear. PG-safe always. No nudity, no suggestive content.
GPS watch on wrist.

CRITICAL — EXPRESSION MUST MATCH EFFORT LEVEL:
- Easy runs: relaxed, comfortable, enjoying the moment — NOT grimacing, straining, or angry
- Moderate runs: focused but comfortable, confident
- Hard runs: determined, intense, powerful — grit is appropriate here
- Race/max effort: fierce, heroic, all-out — suffering is real and earned
The expression should feel HONEST to the effort. Easy runs are easy. Hard runs are hard.

THE IMAGE MUST BE FUNNY — situational humor, visual gags, unexpected elements
in the scene. The runner should look like THEMSELVES at that effort level.

DO NOT include any text, words, letters, numbers, signs, labels, speech bubbles,
thought bubbles, comic sound effects, captions, watermarks, or any form of writing
anywhere in the image. No text on clothing, no text on signs, no text on buildings,
no text on objects. The image must be PURELY VISUAL — zero readable characters.
The humor comes from the scene composition, expressions, and situational comedy only.

ASPECT RATIO: 1:1 square. Fill the entire frame with the caricature scene.

Do not include any real brand logos, trademarked imagery, or copyrighted material."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RuntoonResult:
    image_bytes: bytes = field(default_factory=bytes)
    caption_text: str = ""
    stats_text: str = ""
    prompt_hash: str = ""
    generation_time_ms: int = 0
    cost_usd: float = RUNTOON_COST_USD_PER_IMAGE
    model_version: str = RUNTOON_MODEL
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt assembly helpers
# ---------------------------------------------------------------------------

def _format_stats_text(activity) -> str:
    """
    Format the stats line baked into the image and stored for 9:16 recompose.
    e.g., "13.0 mi  •  7:28/mi  •  1:37:00  •  153 bpm"
    """
    parts = []

    # Distance
    if activity.distance_meters:
        miles = activity.distance_meters / 1609.344
        parts.append(f"{miles:.1f} mi")

    # Pace (from moving_time_s + distance)
    if activity.distance_meters and activity.moving_time_s:
        pace_spm = activity.moving_time_s / (activity.distance_meters / 1609.344)  # sec/mile
        pace_min = int(pace_spm // 60)
        pace_sec = int(pace_spm % 60)
        parts.append(f"{pace_min}:{pace_sec:02d}/mi")

    # Duration
    if activity.moving_time_s:
        h = int(activity.moving_time_s // 3600)
        m = int((activity.moving_time_s % 3600) // 60)
        s = int(activity.moving_time_s % 60)
        if h > 0:
            parts.append(f"{h}:{m:02d}:{s:02d}")
        else:
            parts.append(f"{m}:{s:02d}")

    # Heart rate
    if activity.average_hr:
        parts.append(f"{int(activity.average_hr)} bpm")

    # Date — cross-platform (%-d is POSIX-only; use lstrip instead)
    if activity.start_time:
        dt = activity.start_time
        if hasattr(dt, 'strftime'):
            parts.append(f"{dt.strftime('%b')} {dt.day}, {dt.year}")
        else:
            parts.append(str(dt)[:10])

    return "  •  ".join(parts) if parts else ""


def _format_activity_context(activity, training_context: Optional[dict] = None) -> str:
    """Describe the run conditions and training context for the scene direction layer."""
    lines = []
    tc = training_context or {}

    if activity.start_time:
        dt = activity.start_time
        hour = dt.hour if hasattr(dt, 'hour') else 12
        if hour < 6:
            time_label = "pre-dawn darkness"
        elif hour < 9:
            time_label = "early morning"
        elif hour < 12:
            time_label = "mid-morning"
        elif hour < 15:
            time_label = "midday"
        elif hour < 18:
            time_label = "afternoon"
        elif hour < 21:
            time_label = "evening"
        else:
            time_label = "night"
        lines.append(f"Time of run: {time_label} ({dt.strftime('%H:%M') if hasattr(dt, 'strftime') else ''})")

    miles = 0.0
    if activity.distance_meters:
        miles = activity.distance_meters / 1609.344
        lines.append(f"Distance: {miles:.1f} miles")

    if activity.moving_time_s and activity.distance_meters:
        pace_spm = activity.moving_time_s / (activity.distance_meters / 1609.344)
        pace_min = int(pace_spm // 60)
        pace_sec = int(pace_spm % 60)
        lines.append(f"Pace: {pace_min}:{pace_sec:02d}/mi")

    elev_gain_m = getattr(activity, 'total_elevation_gain', None)
    if elev_gain_m and float(elev_gain_m) > 30:
        elev_ft = float(elev_gain_m) * 3.28084
        lines.append(f"Elevation gain: {elev_ft:.0f} feet")
        ft_per_mile = elev_ft / miles if miles > 0 else 0
        if ft_per_mile > 100:
            lines.append("Terrain: VERY HILLY — steep climbs and descents, mountain-style trails or roads")
        elif ft_per_mile > 60:
            lines.append("Terrain: HILLY — rolling hills with significant climbing")
        elif ft_per_mile > 30:
            lines.append("Terrain: MODERATE HILLS — undulating terrain with some climbs")

    if activity.workout_type:
        lines.append(f"Workout type: {activity.workout_type}")

    resolved = _resolve_activity_title(activity)
    if resolved:
        lines.append(f"Activity name: {resolved}")

    is_race = getattr(activity, 'is_race_candidate', False)
    if is_race:
        lines.append("Context: RACE DAY — celebration and achievement")
    else:
        lines.append("Context: This is a TRAINING RUN, not a race. No race bibs, no finish lines, no race crowds.")

    if activity.average_hr:
        hr = int(activity.average_hr)
        if hr > 170:
            effort = "maximum effort — suffering and triumph"
        elif hr > 155:
            effort = "hard effort — focused intensity"
        elif hr > 140:
            effort = "moderate effort — strong and steady"
        else:
            effort = "easy effort — relaxed and flowing"
        lines.append(f"Effort level: {effort} (avg HR {hr} bpm)")

    # Training context
    if tc.get("weekly_miles") and tc["weekly_miles"] > 0:
        lines.append(f"Weekly mileage so far: {tc['weekly_miles']:.0f} miles this week")
    if tc.get("race_name") and tc.get("days_to_race") is not None:
        lines.append(f"Upcoming race: {tc['race_name']} in {tc['days_to_race']} days")
    if tc.get("training_phase"):
        lines.append(f"Training phase: {tc['training_phase']}")

    return "\n".join(lines)


def _check_caption_blocklist(text: str) -> bool:
    """Return True if caption is safe (no blocked words)."""
    lowered = text.lower()
    return not any(word in lowered for word in CAPTION_BLOCKLIST)


def _generate_caption(
    activity,
    insight_narrative: Optional[str],
    client,
    training_context: Optional[dict] = None,
) -> str:
    """
    Generate a witty, contextual caption for the Runtoon.

    Quality bar: the caption must reference at least one specific detail
    from the athlete's actual run or training week. Generic one-word
    responses are rejected and regenerated.

    Priority:
    1. Generate via text-only Gemini call with full training context
    2. Use InsightLog narrative if Gemini unavailable
    3. Fallback to a contextual but safe line
    """
    tc = training_context or {}

    if client is None or not GENAI_AVAILABLE:
        if insight_narrative and len(insight_narrative.strip()) >= 20:
            return insight_narrative.strip()[:120]
        return _fallback_caption(activity, tc)

    miles = (activity.distance_meters / 1609.344) if activity.distance_meters else 0
    pace_str = ""
    if activity.distance_meters and activity.moving_time_s:
        pace_spm = activity.moving_time_s / (activity.distance_meters / 1609.344)
        pace_min = int(pace_spm // 60)
        pace_sec = int(pace_spm % 60)
        pace_str = f"{pace_min}:{pace_sec:02d}/mi"

    # Build rich context block
    context_lines = [
        f"- Distance: {miles:.1f} miles",
        f"- Pace: {pace_str or 'unknown'}",
        f"- Avg HR: {activity.average_hr or 'unknown'} bpm",
        f"- Workout type: {activity.workout_type or 'run'}",
    ]
    if tc.get("weekly_miles") and tc["weekly_miles"] > 0:
        context_lines.append(f"- Weekly mileage: {tc['weekly_miles']:.0f} miles this week")
    if tc.get("race_name") and tc.get("days_to_race") is not None:
        context_lines.append(f"- Upcoming race: {tc['race_name']} in {tc['days_to_race']} days")
    if tc.get("training_phase"):
        context_lines.append(f"- Training phase: {tc['training_phase']}")
    if insight_narrative and len(insight_narrative.strip()) >= 15:
        context_lines.append(f"- Coach's take: {insight_narrative.strip()[:200]}")

    context_block = "\n".join(context_lines)

    prompt = (
        f"You are writing the caption for a shareable post-run image. "
        f"The athlete just finished this run:\n{context_block}\n\n"
        f"Write ONE caption (1-2 sentences, max 120 characters) that is:\n"
        f"- GENUINELY FUNNY — like a witty friend who runs, not a coach\n"
        f"- SPECIFIC to this exact run — reference the distance, pace, weekly load, "
        f"or upcoming race\n"
        f"- Self-deprecating humor preferred over motivational\n"
        f"- No exclamation points, no hashtags, no emoji\n\n"
        f"GOOD examples of the tone we want:\n"
        f'- "63-mile week and your brain said lets see how marathon pace feels. It felt like marathon pace."\n'
        f'- "7:28 pace at 153 bpm means the engine is willing but the chassis has concerns."\n'
        f'- "13 miles of taper denial. The race is in two weeks, not today."\n\n'
        f"BAD examples (do NOT write these):\n"
        f'- "Half" (too short, meaningless)\n'
        f'- "Great run today" (generic, boring)\n'
        f'- "You crushed it!" (motivational coaching speak)\n'
        f'- "Thirteen" (single word, no context)\n\n'
        f"Return ONLY the caption text, nothing else."
    )

    try:
        response = client.models.generate_content(
            model=CAPTION_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=CAPTION_TEMPERATURE,
                max_output_tokens=CAPTION_MAX_TOKENS,
            ),
        )
        raw = response.text.strip().strip('"').strip("'")

        # Quality gate: reject captions under 20 chars or single words
        if len(raw) < 20 or " " not in raw:
            logger.warning("Caption too short or single-word (%r), retrying", raw)
            response2 = client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt + "\nYour previous attempt was rejected for being too short. Write a FULL SENTENCE.",
                config=genai_types.GenerateContentConfig(temperature=0.7),
            )
            raw = response2.text.strip().strip('"').strip("'")

        if not _check_caption_blocklist(raw):
            logger.warning("Caption blocklist hit, regenerating")
            response3 = client.models.generate_content(
                model=CAPTION_MODEL,
                contents=prompt + "\nIMPORTANT: Keep it clean and family-friendly.",
                config=genai_types.GenerateContentConfig(temperature=0.5),
            )
            raw = response3.text.strip().strip('"').strip("'")

        if raw and len(raw) >= 15 and _check_caption_blocklist(raw):
            return raw[:140]
    except Exception as e:
        logger.warning("Caption generation failed, using fallback: %s", e)

    # Fallback to insight narrative if available
    if insight_narrative and len(insight_narrative.strip()) >= 20:
        return insight_narrative.strip()[:120]

    return _fallback_caption(activity, tc)


def _fallback_caption(activity, training_context: Optional[dict] = None) -> str:
    """Contextual fallback caption when generation fails."""
    tc = training_context or {}
    miles = (activity.distance_meters / 1609.344) if activity.distance_meters else 0

    if getattr(activity, 'is_race_candidate', False):
        return "Race day. Everything hurt. Worth it."

    if tc.get("race_name") and tc.get("days_to_race") is not None:
        d = tc["days_to_race"]
        if d <= 14:
            return f"{miles:.0f} miles of taper denial. {tc['race_name']} is in {d} days."
        return f"{miles:.0f} miles in the bank. {tc['race_name']} in {d} days."

    if tc.get("weekly_miles") and tc["weekly_miles"] > 40:
        return f"{tc['weekly_miles']:.0f}-mile week and still going. The legs have opinions."

    if miles >= 15:
        return f"The last {miles:.0f} miles are mostly stubbornness."
    elif miles >= 10:
        return "Long enough to reconsider every decision that led to this."
    else:
        return f"{miles:.1f} miles. Another day of convincing the body this is fun."


def _hash_prompt(parts_text: str) -> str:
    """SHA-256 hash of the assembled prompt for debugging."""
    return hashlib.sha256(parts_text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_runtoon(
    activity,
    athlete_photos: List[Tuple[bytes, str]],  # List of (photo_bytes, mime_type)
    insight_narrative: Optional[str],
    training_context: Optional[dict] = None,
    gemini_client=None,
) -> RuntoonResult:
    """
    Generate a Runtoon image for the given activity.

    This function is intentionally stateless — it receives pure data and returns
    a RuntoonResult. The Celery task handles all DB reads before calling this
    and all DB writes + R2 uploads after.

    Args:
        activity:          Activity proxy (read-only, no lazy loads needed)
        athlete_photos:    List of (bytes, mime_type) tuples for reference photos
        insight_narrative: Coaching insight text from InsightLog (or None)
        training_context:  Dict with weekly_miles, race_name, days_to_race, training_phase
        gemini_client:     google.genai.Client (None = dry-run, returns placeholder)

    Returns:
        RuntoonResult with image_bytes and metadata, or error set if failed.
    """
    result = RuntoonResult()
    start_time = time.time()

    if not GENAI_AVAILABLE or gemini_client is None:
        result.error = "Gemini not available (dry-run mode)"
        logger.warning("generate_runtoon: dry-run mode (no Gemini client)")
        return result

    if len(athlete_photos) < 3:
        result.error = f"Insufficient photos: {len(athlete_photos)} provided, 3 required"
        logger.warning("generate_runtoon: %s", result.error)
        return result

    try:
        # Build stats + caption text (stored separately for 9:16 recompose)
        stats_text = _format_stats_text(activity)
        caption_text = _generate_caption(activity, insight_narrative, gemini_client, training_context)
        activity_context = _format_activity_context(activity, training_context)

        result.stats_text = stats_text
        result.caption_text = caption_text

        # Assemble scene direction — the scene must reflect the actual run
        tc = training_context or {}
        is_race = getattr(activity, 'is_race_candidate', False)
        miles = (activity.distance_meters / 1609.344) if activity.distance_meters else 0
        elev_gain_m = float(getattr(activity, 'total_elevation_gain', 0) or 0)
        elev_ft = elev_gain_m * 3.28084
        ft_per_mile = elev_ft / miles if miles > 0 else 0

        # Time of day for lighting
        time_part = "daylight"
        if activity.start_time and hasattr(activity.start_time, 'hour'):
            hour = activity.start_time.hour
            if hour < 6:
                time_part = "pre-dawn darkness, headlamp light, stars"
            elif hour < 9:
                time_part = "golden morning light, long shadows"
            elif hour < 15:
                time_part = "bright daylight"
            elif hour < 18:
                time_part = "warm afternoon light"
            elif hour < 21:
                time_part = "sunset/dusk light"
            else:
                time_part = "night running, street lights or headlamp"

        scene_direction_parts = [f"Lighting: {time_part}"]

        # Terrain — this is the critical missing piece
        if ft_per_mile > 100:
            scene_direction_parts.append(
                "TERRAIN IS THE STORY: steep mountain trails or hilly back roads "
                "with dramatic elevation. Show hills, climbs, switchbacks, or "
                "ridgelines. The runner is conquering serious elevation."
            )
        elif ft_per_mile > 60:
            scene_direction_parts.append(
                "Terrain: rolling hills with visible climbs and descents. "
                "Show the runner on a hilly road or trail with hills in the background."
            )
        elif ft_per_mile > 30:
            scene_direction_parts.append("Terrain: gentle hills, undulating road or trail")
        else:
            scene_direction_parts.append("Terrain: flat road, track, or path")

        # Distance character
        if miles >= 18:
            scene_direction_parts.append(
                "This is an ULTRA-DISTANCE training run. Show epic scale, "
                "the enormity of the distance, the runner deep into the effort."
            )
        elif miles >= 13:
            scene_direction_parts.append(
                "This is a LONG RUN. Show the runner well into a serious effort — "
                "determined, grinding, earning every mile."
            )
        elif miles >= 8:
            scene_direction_parts.append("Solid training run — show steady effort and focus")

        # Race vs training
        if is_race:
            scene_direction_parts.append("This is a RACE — show triumph, celebration, finish line")
        else:
            scene_direction_parts.append(
                "This is a TRAINING RUN — show the runner on a road or trail, "
                "no race bibs, no finish lines, no race crowds"
            )
            if tc.get("race_name") and tc.get("days_to_race") is not None:
                scene_direction_parts.append(
                    f"Training for {tc['race_name']} in {tc['days_to_race']} days — "
                    f"show determination and preparation, NOT race day"
                )

        # Effort level for expression
        avg_hr = getattr(activity, 'average_hr', None)
        if avg_hr:
            hr = int(avg_hr)
            if hr > 170:
                scene_direction_parts.append("Expression: INTENSE suffering, all-out effort, grit")
            elif hr > 155:
                scene_direction_parts.append("Expression: focused and determined, working hard")
            elif hr > 140:
                scene_direction_parts.append("Expression: confident and strong, steady effort")
            else:
                scene_direction_parts.append("Expression: relaxed, comfortable, enjoying the run")

        scene_direction = ". ".join(scene_direction_parts)

        # Assemble full text prompt
        text_prompt = f"""{STYLE_ANCHOR}

RUN CONTEXT:
{activity_context}

VISUAL DIRECTION:
{scene_direction}

Create a flattering, humorous caricature using the reference photos provided.
Their expression MUST match the effort level described above.
Make it funny. Make it theirs. Make it share-worthy.
Remember: absolutely NO text, words, or letters anywhere in the image."""

        result.prompt_hash = _hash_prompt(text_prompt)

        # Build multi-part content: photos first, then text prompt
        parts = []
        for photo_bytes, mime_type in athlete_photos:
            parts.append(
                genai_types.Part.from_bytes(data=photo_bytes, mime_type=mime_type)
            )
        parts.append(genai_types.Part.from_text(text=text_prompt))

        content = genai_types.Content(parts=parts)

        # Call the model
        logger.info(
            "generate_runtoon: calling %s with %d photos, activity=%s",
            RUNTOON_MODEL,
            len(athlete_photos),
            getattr(activity, 'id', 'unknown'),
        )

        response = gemini_client.models.generate_content(
            model=RUNTOON_MODEL,
            contents=content,
            config=genai_types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
                temperature=RUNTOON_TEMPERATURE,
            ),
        )

        # Extract image bytes from response
        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                raw = part.inline_data.data
                # Decode base64 if it came back as a string
                if isinstance(raw, str):
                    image_bytes = base64.b64decode(raw)
                elif isinstance(raw, bytes):
                    # Some SDK versions return already-decoded bytes
                    # Detect by checking PNG/JPEG magic bytes
                    if raw[:4] == b'\x89PNG' or raw[:2] == b'\xff\xd8':
                        image_bytes = raw
                    else:
                        image_bytes = base64.b64decode(raw)
                break

        if not image_bytes:
            result.error = "Model returned no image data"
            logger.error("generate_runtoon: no image in response for activity %s", getattr(activity, 'id', '?'))
            return result

        result.image_bytes = image_bytes
        result.generation_time_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "generate_runtoon: success activity=%s size=%d bytes latency=%dms",
            getattr(activity, 'id', '?'),
            len(image_bytes),
            result.generation_time_ms,
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error("generate_runtoon: failed activity=%s error=%s", getattr(activity, 'id', '?'), e)

    return result


# ---------------------------------------------------------------------------
# 1:1 Pillow overlay (stats + caption + watermark on the square image)
# ---------------------------------------------------------------------------

def overlay_stats_1x1(
    source_image_bytes: bytes,
    stats_text: str,
    caption_text: str,
) -> bytes:
    """
    Overlay stats line, caption, and watermark onto the 1:1 Runtoon image.

    Uses a semi-transparent dark gradient at the bottom of the image so
    white text is readable over any background. This is the image the
    athlete sees on the activity page and downloads as 1:1.

    Args:
        source_image_bytes: Raw bytes of the AI-generated 1:1 image
        stats_text:         Formatted stats line
        caption_text:       AI-generated caption

    Returns:
        PNG bytes of the overlaid 1:1 image.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
    except ImportError:
        raise ImportError("Pillow is not installed.")

    source = Image.open(io.BytesIO(source_image_bytes)).convert("RGBA")
    w, h = source.size

    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad_draw = ImageDraw.Draw(gradient)
    grad_top = int(h * 0.65)
    for y in range(grad_top, h):
        alpha = int(180 * ((y - grad_top) / (h - grad_top)) ** 1.5)
        grad_draw.line([(0, y), (w, y)], fill=(0, 0, 0, min(alpha, 200)))
    source = Image.alpha_composite(source, gradient)

    draw = ImageDraw.Draw(source)

    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    scale = w / 1080.0
    font_stats = _load_font(max(14, int(28 * scale)))
    font_caption = _load_font(max(12, int(22 * scale)))
    font_watermark = _load_font(max(10, int(18 * scale)))

    TEXT_COLOR = (255, 255, 255, 255)
    CAPTION_COLOR = (220, 220, 220, 230)
    WATERMARK_COLOR = (180, 180, 180, 180)

    padding = int(20 * scale)
    text_y = h - padding

    # Build from bottom up: watermark, then caption, then stats
    # Watermark
    wm_text = "strideiq.run"
    draw.text((w // 2, text_y), wm_text, fill=WATERMARK_COLOR, font=font_watermark, anchor="mb")
    text_y -= int(30 * scale)

    # Caption (word-wrapped)
    if caption_text:
        max_text_w = w - int(60 * scale)
        words = caption_text.split()
        lines = []
        current_line = ""
        for word in words:
            test = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font_caption)
            if bbox[2] - bbox[0] <= max_text_w:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in reversed(lines):
            draw.text((w // 2, text_y), line, fill=CAPTION_COLOR, font=font_caption, anchor="mb")
            text_y -= int(28 * scale)
        text_y -= int(8 * scale)

    # Stats line
    if stats_text:
        draw.text((w // 2, text_y), stats_text, fill=TEXT_COLOR, font=font_stats, anchor="mb")

    output = io.BytesIO()
    source.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()


# ---------------------------------------------------------------------------
# 9:16 Pillow recompose (Stories format)
# ---------------------------------------------------------------------------

def recompose_stories(
    source_image_bytes: bytes,
    stats_text: str,
    caption_text: str,
) -> bytes:
    """
    Deterministic server-side recompose from 1:1 to 9:16 (1080x1920) for Instagram Stories.

    No second API call. Uses Pillow to:
    1. Create a 1080x1920 dark canvas (#1e293b — matches the Runtoon banner)
    2. Place the 1:1 image (scaled to 1080px wide) in the top portion
    3. Render stats line and caption in the extended bottom space
    4. Add strideiq.run watermark

    Args:
        source_image_bytes: Raw bytes of the 1:1 Runtoon image
        stats_text:         Formatted stats line (from RuntoonImage.stats_text)
        caption_text:       AI-generated caption (from RuntoonImage.caption_text)

    Returns:
        PNG bytes of the 9:16 recomposed image.

    Raises:
        ImportError: If Pillow is not installed.
        Exception:   If recomposition fails.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
    except ImportError:
        raise ImportError("Pillow is not installed. Add it to requirements.txt.")

    CANVAS_W, CANVAS_H = 1080, 1920
    BG_COLOR = (30, 41, 59)      # #1e293b — slate-800 dark
    TEXT_COLOR = (226, 232, 240)  # slate-200
    MUTED_COLOR = (148, 163, 184) # slate-400
    WATERMARK_COLOR = (100, 116, 139) # slate-500

    source = Image.open(io.BytesIO(source_image_bytes)).convert("RGBA")
    scale = CANVAS_W / source.width
    new_h = int(source.height * scale)
    source = source.resize((CANVAS_W, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), BG_COLOR + (255,))

    # Place the caricature in the upper portion, leaving room for text below
    text_zone_h = 340
    available_h = CANVAS_H - text_zone_h
    y_offset = max(0, (available_h - new_h) // 2)
    canvas.paste(source, (0, y_offset), source)

    draw = ImageDraw.Draw(canvas)

    def _load_font(size: int) -> ImageFont.FreeTypeFont:
        for path in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                continue
        return ImageFont.load_default()

    font_stats = _load_font(32)
    font_caption = _load_font(28)
    font_watermark = _load_font(24)

    text_y = CANVAS_H - text_zone_h + 40

    # Stats line
    if stats_text:
        draw.text(
            (CANVAS_W // 2, text_y),
            stats_text,
            fill=TEXT_COLOR,
            font=font_stats,
            anchor="mt",
        )
        text_y += 60

    # Caption (word-wrap to fit canvas width with padding)
    if caption_text:
        max_text_w = CANVAS_W - 120
        words = caption_text.split()
        lines = []
        current_line = ""
        for word in words:
            test = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font_caption)
            if bbox[2] - bbox[0] <= max_text_w:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in lines:
            draw.text(
                (CANVAS_W // 2, text_y),
                line,
                fill=MUTED_COLOR,
                font=font_caption,
                anchor="mt",
            )
            text_y += 42

    # Watermark
    draw.text(
        (CANVAS_W // 2, CANVAS_H - 40),
        "── strideiq.run ──",
        fill=WATERMARK_COLOR,
        font=font_watermark,
        anchor="mm",
    )

    output = io.BytesIO()
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
