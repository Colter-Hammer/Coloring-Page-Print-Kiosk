import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def validate_image(file_bytes: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def _flatten_to_white(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _new_filename() -> str:
    return f"{uuid.uuid4().hex}.jpg"


def save_resized_image(file_bytes: bytes, dest_path: Path, max_size: int) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(file_bytes)) as img:
        flattened = _flatten_to_white(img)
        flattened.thumbnail((max_size, max_size))
        flattened.save(dest_path, format="JPEG", quality=85)


def save_category_icon(file_bytes: bytes, images_dir: Path) -> str:
    """Save a resized category tile icon; returns its path relative to images_dir."""
    relative_path = f"category_icons/{_new_filename()}"
    save_resized_image(file_bytes, images_dir / relative_path, max_size=400)
    return relative_path


def save_page_images(file_bytes: bytes, images_dir: Path) -> tuple[str, str]:
    """Save a full-res page image plus its thumbnail; returns (image_path, thumb_path),
    both relative to images_dir."""
    filename = _new_filename()
    full_relative = f"pages/full/{filename}"
    thumb_relative = f"pages/thumb/{filename}"
    save_resized_image(file_bytes, images_dir / full_relative, max_size=2000)
    save_resized_image(file_bytes, images_dir / thumb_relative, max_size=300)
    return full_relative, thumb_relative
