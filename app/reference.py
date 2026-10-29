"""Place a separately supplied face photograph on an output-sized gray canvas."""

from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

GRAY = (128, 128, 128)


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    def validate(self, width: int, height: int) -> "BBox":
        if any(isinstance(v, bool) or not isinstance(v, int) for v in asdict(self).values()):
            raise ValueError("Face coordinates must be integer pixels")
        if self.width < 2 or self.height < 2:
            raise ValueError("Face selection must be at least 2 by 2 pixels")
        if self.x < 0 or self.y < 0 or self.x + self.width > width or self.y + self.height > height:
            raise ValueError("Face selection must fit inside the image")
        return self

    @property
    def corners(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.width, self.y + self.height

    def expanded(self, factor: float, width: int, height: int) -> "BBox":
        """Grow around the centre by `factor`, clipped to the image."""
        if factor == 1.0:
            return self
        cx, cy = self.x + self.width / 2, self.y + self.height / 2
        w, h = self.width * factor, self.height * factor
        x0, y0 = int(max(0, cx - w / 2)), int(max(0, cy - h / 2))
        x1, y1 = int(min(width, cx + w / 2)), int(min(height, cy + h / 2))
        return BBox(x0, y0, x1 - x0, y1 - y0)


@dataclass(frozen=True)
class CanvasResult:
    path: Path
    target_bbox: BBox
    photo_bbox: BBox
    crop_method: str
    frame_idx: int = -1


def read_photo(path: Path) -> Image.Image:
    with Image.open(path) as image:
        if image.width * image.height > 25_000_000:
            raise ValueError("Photo exceeds 25 megapixels; resize it before uploading")
        return ImageOps.exif_transpose(image).convert("RGB")


def detect_faces(image: Image.Image) -> list[BBox]:
    """Local Haar proposal, with manual selection available for difficult old footage."""
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if detector.empty():
        return []
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    scale = min(1.0, 1280 / max(image.size))
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    boxes = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
    result = []
    for x, y, w, h in boxes:
        x, y = max(0, round(x / scale)), max(0, round(y / scale))
        w, h = min(round(w / scale), image.width - x), min(round(h / scale), image.height - y)
        result.append(BBox(x, y, w, h))
    return sorted(result, key=lambda b: b.width * b.height, reverse=True)


def build_reference_canvas(
    photo: Path, output: Path, bbox: BBox, width: int, height: int,
    photo_bbox: BBox | None = None, expand: float = 1.0,
) -> CanvasResult:
    """`expand` > 1 grows both the photo crop and the pasted area around their centres, so hair, jaw
    and ears from the photo reach the model too (1.4 measured best in the strong-damage sweep)."""
    if not 1.0 <= expand <= 3.0:
        raise ValueError("Reference expand must be between 1.0 and 3.0")
    if width < 2 or height < 2 or width * height > 8_000_000:
        raise ValueError("Invalid canvas dimensions")
    bbox.validate(width, height)
    image = read_photo(photo)
    if photo_bbox is not None:
        crop = photo_bbox.validate(image.width, image.height)
        crop_method = "manual"
    else:
        faces = detect_faces(image)
        if len(faces) > 1:
            raise ValueError("Multiple faces in the photo. Select the reference face first.")
        if faces:
            crop = faces[0]
            crop_method = "detected"
        else:
            # Visible UI preview permits correction; this is never a verified face detection.
            size = min(image.size)
            crop = BBox((image.width - size) // 2, (image.height - size) // 2, size, size)
            crop_method = "center_fallback"
    canvas = Image.new("RGB", (width, height), GRAY)
    source, target = crop.expanded(expand, image.width, image.height), bbox.expanded(expand, width, height)
    face = ImageOps.fit(image.crop(source.corners), (target.width, target.height), method=Image.Resampling.LANCZOS)
    canvas.paste(face, (target.x, target.y))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG")
    return CanvasResult(output, bbox, crop, crop_method)
