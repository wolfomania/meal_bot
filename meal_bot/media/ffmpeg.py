import asyncio
import os


async def extract_audio(input_path: str, output_path: str) -> None:
    """Extract 16kHz mono WAV audio from a video file."""
    proc = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', input_path,
        '-vn', '-ac', '1', '-ar', '16000', '-y', output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {stderr.decode()[-500:]}")


async def extract_frames(
    input_path: str,
    tmpdir: str,
    duration: float,
    n: int = 8,
) -> list[str]:
    """Extract n evenly-spaced JPEG keyframes from a video file.

    Returns a list of paths to successfully extracted frames.
    """
    timestamps = [duration * (i + 1) / (n + 1) for i in range(n)]
    paths: list[str] = []
    for i, ts in enumerate(timestamps):
        out = os.path.join(tmpdir, f"frame_{i:02d}.jpg")
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-ss', str(ts), '-i', input_path,
            '-frames:v', '1', '-q:v', '2', '-y', out,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0:
            paths.append(out)
    return paths
