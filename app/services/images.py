import io
import uuid
from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError


def validate_image(file_bytes: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def looks_like_pdf(file_bytes: bytes) -> bool:
    return file_bytes.startswith(b"%PDF-")


class InvalidPdfError(ValueError):
    """Raised when uploaded bytes look like a PDF but can't be used as a page."""

    def __init__(self, reason: str):
        self.reason = reason  # "corrupt" | "multi_page" | "encrypted"
        super().__init__(reason)


def rasterize_pdf_page(file_bytes: bytes, dpi: int = 200) -> Image.Image:
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise InvalidPdfError("corrupt") from exc
    try:
        if doc.needs_pass:
            raise InvalidPdfError("encrypted")
        if doc.page_count != 1:
            raise InvalidPdfError("multi_page")
        pix = doc[0].get_pixmap(dpi=dpi)
        mode = "RGBA" if pix.alpha else "RGB"
        return Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    finally:
        doc.close()


def flatten_to_white(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _new_filename() -> str:
    return f"{uuid.uuid4().hex}.jpg"


def _save_resized(img: Image.Image, dest_path: Path, max_size: int) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    flattened = flatten_to_white(img)
    flattened.thumbnail((max_size, max_size))
    flattened.save(dest_path, format="JPEG", quality=85)


def save_resized_image(file_bytes: bytes, dest_path: Path, max_size: int) -> None:
    with Image.open(io.BytesIO(file_bytes)) as img:
        _save_resized(img, dest_path, max_size)


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


def save_page_images_from_image(img: Image.Image, images_dir: Path) -> tuple[str, str]:
    """Same as save_page_images, but from an already-decoded PIL Image
    (used for PDF uploads, where the image is a rasterized page rather
    than raw uploaded bytes)."""
    filename = _new_filename()
    full_relative = f"pages/full/{filename}"
    thumb_relative = f"pages/thumb/{filename}"
    _save_resized(img, images_dir / full_relative, max_size=2000)
    _save_resized(img, images_dir / thumb_relative, max_size=300)
    return full_relative, thumb_relative


def save_page_pdf(file_bytes: bytes, images_dir: Path) -> str:
    """Save the original uploaded PDF bytes verbatim for printing; returns
    its path relative to images_dir."""
    relative_path = f"pages/print_pdf/{uuid.uuid4().hex}.pdf"
    dest_path = images_dir / relative_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(file_bytes)
    return relative_path
